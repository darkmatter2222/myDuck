#!/usr/bin/env python3
"""Snapshot training evidence without loading pickled checkpoints or changing a run."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

MAX_TOTAL=2*1024**3
MAX_FILE=512*1024**2
LOG_TAIL=16*1024**2

def scalar_csv(root, output):
    # Raw EventFileLoader preserves repeated steps/restarts; no reservoir sampling.
    from tensorboard.backend.event_processing.event_file_loader import EventFileLoader
    from tensorboard.util import tensor_util
    warnings=[];count=0
    with Path(output).open('w',newline='',encoding='utf-8') as fd:
        writer=csv.writer(fd);writer.writerow(['event_file','run','tag','step','wall_time','value'])
        for path in sorted(Path(root).rglob('events.out.tfevents.*')):
            try:
                for event in EventFileLoader(str(path)).Load():
                    for value in event.summary.value:
                        if value.HasField('simple_value'):number=value.simple_value
                        elif value.HasField('tensor'):
                            array=tensor_util.make_ndarray(value.tensor)
                            if array.size!=1 or array.dtype.kind not in 'biuf':continue
                            number=array.item()
                        else:continue
                        writer.writerow([str(path.relative_to(root)),path.parent.name,value.tag,event.step,event.wall_time,number]);count+=1
                        if count%10000==0 and fd.tell()>MAX_TOTAL:
                            raise RuntimeError('Scalar CSV reached 2 GiB cap')
            except Exception as exc:warnings.append(str(path)+': '+str(exc))
    print(json.dumps({'rows':count,'warnings':warnings}))
    return 0

def export_training(base, source, output, max_total=MAX_TOTAL):
    base=Path(base).resolve();source=Path(source).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError('Export already exists: '+str(output))
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest={'schema':1,'created_unix':time.time(),'files':[],'warnings':[],
              'live_snapshot':True,'checkpoint_weights_included':False,'bytes':0}
    runs=base/'xgoduck_rl/logs/rsl_rl/xgoduck_velocity'
    with tempfile.TemporaryDirectory(prefix='myduck-evidence-') as tmp:
        stage=Path(tmp)
        def capture(path, name):
            if path.is_symlink() or not path.is_file():return
            # Never follow symlinked parent directories outside intended roots.
            allowed=source if str(name).startswith(('source/','windows/')) else base
            if not path.resolve().is_relative_to(allowed):
                manifest['warnings'].append('Skipped outside-root path: '+str(path));return
            stat=path.stat();size=stat.st_size
            limit=LOG_TAIL if path.suffix=='.log' else MAX_FILE
            start=max(0,size-limit) if path.suffix=='.log' else 0
            take=size-start
            if take>limit or manifest['bytes']+take>max_total:
                manifest['warnings'].append('Size cap: omitted '+str(name));return
            if shutil.disk_usage(stage).free < take+64*1024**2:
                manifest['warnings'].append('Low disk: omitted '+str(name));return
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256();copied=0
            try:
                with path.open('rb') as src,target.open('wb') as dst:
                    src.seek(start)
                    while copied<take:
                        chunk=src.read(min(1024*1024,take-copied))
                        if not chunk:break
                        dst.write(chunk);digest.update(chunk);copied+=len(chunk)
                changed=path.stat().st_size!=size or path.stat().st_mtime_ns!=stat.st_mtime_ns
                manifest['files'].append(dict(path=str(name),bytes=copied,original_bytes=size,
                    tail_only=bool(start),changed_during_copy=changed,sha256=digest.hexdigest()))
                manifest['bytes']+=copied
                if copied!=take:manifest['warnings'].append('File shortened during snapshot: '+str(name))
            except OSError as exc:manifest['warnings'].append(str(name)+': '+str(exc))
        capture(base/'state.json',Path('state.json'))
        if (base/'reports').exists():
            for path in sorted((base/'reports').rglob('*')):
                if path.suffix in ('.json','.csv','.log'):capture(path,path.relative_to(base))
        if runs.exists():
            for path in sorted(runs.rglob('*')):
                if path.name.startswith('events.out.tfevents.') or (path.suffix in ('.yaml','.yml','.json') and 'params' in path.parts):
                    capture(path,Path('training')/path.relative_to(runs))
        for name in ('pyproject.toml','uv.lock'):
            capture(base/'xgoduck_rl'/name,Path('upstream')/name)
        for path in sorted(source.glob('*.ps1')):capture(path,Path('source')/path.name)
        for path in sorted((source/'scripts').glob('*')):
            if path.suffix in ('.py','.sh','.ps1'):capture(path,Path('source/scripts')/path.name)
        for path in sorted((source/'launcher-logs').glob('*.log')):capture(path,Path('windows')/path.name)
        inventory=[]
        if runs.exists():
            for path in sorted(runs.rglob('model_*.pt')):
                if path.is_file() and not path.is_symlink():
                    stat=path.stat();inventory.append(dict(path=str(path.relative_to(base)),bytes=stat.st_size,mtime=stat.st_mtime))
        (stage/'checkpoint_inventory.json').write_text(json.dumps(inventory,indent=2))
        # Include an immutable header independently of tail truncation on large logs.
        headers=[]
        for path in sorted((base/'reports/train').glob('*.log')):
            if path.is_symlink() or not path.resolve().is_relative_to(base):continue
            with path.open('rb') as fd:head=fd.read(65536).decode('utf-8','replace')
            match=re.search(r'START training parent=(.*?) profile=(\S+) envs=(\d+) updates=(\d+) tag=(\S+)',head)
            if match:headers.append(dict(zip(['parent','profile','envs','updates','tag'],match.groups())))
        (stage/'lineage.json').write_text(json.dumps(headers,indent=2))
        groups={}
        for row in headers:
            key=(row['parent'],row['profile']);groups.setdefault(key,[]).append(row['tag'])
        repeats=[dict(parent=k[0],profile=k[1],attempts=v) for k,v in groups.items() if len(v)>=3 and k[0]!='RANDOM']
        (stage/'repeated_branches.json').write_text(json.dumps(repeats,indent=2))
        scalar_output=stage/'scalars.csv'
        python=base/'xgoduck_rl/.venv/bin/python'
        if python.is_file():
            try:
                result=subprocess.run([str(python),str(Path(__file__).resolve()),'scalars','--root',str(stage/'training'),'--output',str(scalar_output)],capture_output=True,text=True,timeout=600)
                (stage/'scalar_export.log').write_text(result.stdout+'\n'+result.stderr)
                if result.returncode:manifest['warnings'].append('Scalar conversion failed; raw event files are included.')
                else:
                    try:manifest['warnings'].extend(json.loads(result.stdout.strip().splitlines()[-1]).get('warnings',[]))
                    except (ValueError,IndexError):manifest['warnings'].append('Scalar converter did not return its summary.')
            except (OSError,subprocess.TimeoutExpired) as exc:manifest['warnings'].append('Scalar conversion: '+str(exc))
        else:manifest['warnings'].append('Training Python unavailable: raw events included, scalar conversion skipped.')
        for command in (['git','-C',str(source),'rev-parse','HEAD'],['git','-C',str(base/'xgoduck_rl'),'rev-parse','HEAD']):
            try:
                result=subprocess.run(command,capture_output=True,text=True,timeout=10)
                manifest.setdefault('revisions',[]).append(dict(command=command,exit=result.returncode,stdout=result.stdout.strip(),stderr=result.stderr.strip()))
            except Exception as exc:manifest['warnings'].append(str(exc))
        (stage/'README.txt').write_text('Training evidence snapshot. No model weights are collected. Review logs and configs before sharing; they may contain sensitive local information. Includes raw TensorBoard events, unsampled scalar CSV when available, configs, evaluations, logs, state, lineage and checkpoint inventory. Read manifest.json for omissions, tails and files changed during capture. Stop training before export for a consistent snapshot. This does not delete or reset training. Paths and usernames may be present.\n')
        (stage/'manifest.json').write_text(json.dumps(manifest,indent=2))
        partial=output.with_suffix(output.suffix+'.partial')
        try:
            with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                for path in sorted(stage.rglob('*')):
                    if path.is_file():archive.write(path,str(path.relative_to(stage)))
            partial.replace(output)
        finally:partial.unlink(missing_ok=True)
    print('TRAINING EXPORT READY:',output,flush=True)
    for warning in manifest['warnings']:print('EXPORT WARNING:',warning,flush=True)
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('scalars');p.add_argument('--root',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('bundle');p.add_argument('--base',required=True);p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.action=='scalars':sys.exit(scalar_csv(args.root,args.output))
    export_training(args.base,args.source,args.output)
