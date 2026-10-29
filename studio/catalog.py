import hashlib,json,re
from pathlib import Path

def identifier(path):return hashlib.sha256(str(path).encode()).hexdigest()[:24]
def safe_model(root,relative):
    root=Path(root).resolve();path=root/relative
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not re.fullmatch(r'model_\d+\.pt',path.name):raise ValueError('Invalid checkpoint path')
    if not path.is_file():raise ValueError('Checkpoint is no longer on disk')
    return path

def scan(store,run_root,reports):
    root=Path(run_root);known=set();parents={}
    for log in (Path(reports)/'train').glob('*.log'):
        try:
            with log.open(errors='replace') as fd:header=fd.read(65536)
            m=re.search(r'START training parent=(.*?) profile=\S+ envs=\d+ updates=\d+ tag=(\S+)',header)
            if m:parents[m[2]]=m[1]
        except OSError:pass
    jobs=store.jobs()
    for directory in sorted(root.glob('*')):
        if not directory.is_dir() or directory.is_symlink():continue
        parent=None
        for tag,path in parents.items():
            if directory.name.endswith(tag) and path!='RANDOM':
                try:parent=identifier(str(Path(path).relative_to(root)))
                except ValueError:pass
        job=next((j['id'] for j in jobs if ('studio-'+j['id']) in directory.name),None)
        for p in sorted(directory.glob('model_*.pt'),key=lambda p:int(re.search(r'model_(\d+)',p.name)[1]) if re.search(r'model_(\d+)',p.name) else -1):
            try:
                rel=str(p.relative_to(root));safe_model(root,rel);stat=p.stat();mid=identifier(rel);known.add(mid)
                store.write('''INSERT INTO models(id,path,parent,run,step,bytes,modified,job) VALUES(?,?,?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET bytes=excluded.bytes,modified=excluded.modified,deleted=0,job=excluded.job,parent=COALESCE(models.parent,excluded.parent)''',
                 (mid,rel,parent,directory.name,int(re.search(r'model_(\d+)',p.name)[1]),stat.st_size,stat.st_mtime,job))
                parent=mid
            except (OSError,ValueError):continue
    for row in store.rows('SELECT id,path FROM models WHERE deleted=0'):
        if row['id'] not in known:store.write('UPDATE models SET deleted=1 WHERE id=?',(row['id'],))

def evaluations(reports):
    results=[]
    for p in (Path(reports)/'eval').glob('*.json'):
        try:
            row=json.loads(p.read_text());row['file']=p.name
            if isinstance(row,dict) and 'checkpoint' in row:results.append(row)
        except (OSError,ValueError):pass
    return sorted(results,key=lambda x:x.get('created',''))
