import json,os,shutil,signal,subprocess,sys,threading,time,uuid,urllib.request
from pathlib import Path
from .store import Store
from .schema import training
from .catalog import scan,safe_model,evaluations
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import xgoduck_engine as engine
ACTIVE={'starting','running','stopping'}
TERMINAL={'completed','failed','stopped','paused','interrupted','cancelled'}

class Manager:
    def __init__(self,root=None):
        self.store=Store(root or Path.home()/'.local/share/myduck-studio')
        self.root=self.store.root;self.lock=threading.RLock();self.processes={};self.hardware={};self.last_scan=0;self.last_hardware=0
    def jobdir(self,jid):
        if not isinstance(jid,str) or len(jid)!=16 or any(c not in '0123456789abcdef' for c in jid):raise ValueError('Invalid job ID')
        return self.root/'jobs'/jid
    def model(self,mid):
        rows=self.store.rows('SELECT * FROM models WHERE id=? AND deleted=0',(mid,))
        if not rows:raise ValueError('Checkpoint not found')
        row=rows[0];return row,safe_model(engine.RUN_ROOT,row['path'])
    def enqueue(self,kind,config):
        with self.lock:
            if not isinstance(config,dict):raise ValueError('Configuration must be an object')
            if kind not in {'train','setup','evaluate','export','reset','viewer','tensorboard','onnx'}:raise ValueError('Unknown action')
            if any(j['kind']=='reset' and j['status'] in ACTIVE|{'queued'} for j in self.store.jobs()):raise ValueError('Reset is pending; wait until it completes')
            if kind=='train':
                config=training(config)
                if config['parent']:config['checkpoint']=str(self.model(config['parent'])[1])
            elif kind in {'viewer','evaluate','onnx'}:
                mid=config.get('model');_,path=self.model(mid)
                config={'model':mid,'checkpoint':str(path)}
                if kind=='evaluate':config.update(eval_envs=2,eval_seeds=2,eval_seconds=10)
            elif kind in {'setup','export','tensorboard','reset'}:config={}
            if kind in {'viewer','tensorboard'} and any(j['kind']==kind and j['status'] in ACTIVE|{'queued'} for j in self.store.jobs()):raise ValueError('Service already starting/running. Stop it to select a different checkpoint.')
            jid=uuid.uuid4().hex[:16];directory=self.jobdir(jid);directory.mkdir(parents=True)
            spec=dict(id=jid,kind=kind,config=config,created=time.time(),provenance={'engine_version':engine.VERSION,'upstream_pin':'725ed0c','profile_defaults':engine.PROFILES})
            (directory/'spec.json').write_text(json.dumps(spec,indent=2))
            self.store.write('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,kind,json.dumps(config),'queued',time.time(),None,'{}'))
            self.store.audit('queued',spec);return jid
    def alive(self,j):
        pid=j.get('pid')
        if not pid:return False
        if pid in self.processes:return self.processes[pid].poll() is None
        try:
            args=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode().split('\0')
            if j['kind'] in {'viewer','tensorboard'}:return str(ROOT/'scripts/xgoduck_engine.py') in args and j['kind'] in args
            return str(ROOT/'studio/worker.py') in args and str(self.jobdir(j['id'])) in args
        except OSError:return False
    def stop(self,jid):
        with self.lock:
            jobs=[j for j in self.store.jobs() if j['id']==jid]
            if not jobs:raise ValueError('Job not found')
            j=jobs[0]
            if j['status']=='queued':self.store.write('UPDATE jobs SET status=? WHERE id=?',('cancelled',jid))
            elif self.alive(j):
                os.kill(j['pid'],signal.SIGINT)
                self.store.write('UPDATE jobs SET status=? WHERE id=?',('stopping',jid))
            self.store.audit('stop',{'id':jid})
    def reset(self):
        with self.lock:
            for job in self.store.jobs():
                if job['status'] in ACTIVE|{'queued'}:self.stop(job['id'])
            return self.enqueue('reset',{})
    def stop_service(self,kind):
        if kind not in {'viewer','tensorboard'}:raise ValueError('Unknown service')
        with self.lock:
            for job in self.store.jobs():
                if job['kind']==kind and job['status'] in ACTIVE|{'queued'}:self.stop(job['id'])
            for pid,role in engine.existing_viewer_or_worker():
                try:
                    args=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode().split('\0')
                    matches=(kind in args) or any(('/bin/play' in a if kind=='viewer' else '/bin/tensorboard' in a) for a in args)
                    if matches:os.kill(pid,signal.SIGINT)
                except ProcessLookupError:pass
            self.store.audit('service_stop',{'kind':kind})

    def protected(self):
        ids={r['id'] for r in self.store.rows('SELECT id FROM models WHERE pinned=1')}
        runs=set()
        for job in self.store.jobs():
            if job['status'] in ACTIVE|{'queued'}:
                if job['kind']=='train':runs.add('studio-'+job['id'])
                for key in ('parent','model'):
                    if job['spec'].get(key):ids.add(job['spec'][key])
        for m in self.store.rows('SELECT id,run FROM models WHERE deleted=0'):
            if any(tag in m['run'] for tag in runs):ids.add(m['id'])
        return ids
    def delete(self,ids,confirm=False):
        with self.lock:
            if not isinstance(ids,list) or not ids or len(ids)>1000 or len(set(ids))!=len(ids):raise ValueError('Select 1–1000 unique checkpoints')
            if engine.known_controller_pid():raise ValueError('Stop the legacy controller before deleting checkpoint files')
            protected=self.protected();models=[]
            for mid in ids:
                row,path=self.model(mid)
                if mid in protected:raise ValueError('A selected checkpoint is pinned or needed by a pending/active job')
                models.append((row,path))
            plan={'count':len(models),'bytes':sum(r['bytes'] for r,p in models),'models':[r['path'] for r,p in models]}
            if confirm:
                for row,path in models:
                    path.unlink();self.store.write('UPDATE models SET deleted=1 WHERE id=?',(row['id'],))
                    self.store.audit('checkpoint_deleted',{'id':row['id'],'path':row['path']})
            return plan
    def annotate(self,mid,body):
        with self.lock:
            self.model(mid)
            if set(body)-{'label','collection','pinned'}:raise ValueError('Unknown model field')
            for field in ('label','collection'):
                if field in body and (not isinstance(body[field],str) or len(body[field])>100):raise ValueError('Labels must be at most 100 characters')
            if 'pinned' in body and not isinstance(body['pinned'],bool):raise ValueError('pinned must be Boolean')
            for field,value in body.items():self.store.write('UPDATE models SET '+field+'=? WHERE id=?',(value,mid))
            self.store.audit('model_metadata',dict(id=mid,**body))
    def launch(self,j):
        directory=self.jobdir(j['id']);kind=j['kind']
        if kind in {'viewer','tensorboard'}:
            if kind=='viewer':self.model(j['spec']['model'])
            cmd=[sys.executable,'-u',str(ROOT/'scripts/xgoduck_engine.py'),kind]
            if kind=='viewer':cmd+=['--checkpoint',j['spec']['checkpoint'],'--device','cpu']
        else:cmd=[sys.executable,'-u',str(ROOT/'studio/worker.py'),str(directory)]
        with (directory/'console.log').open('ab') as log:
            process=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        self.processes[process.pid]=process
        self.store.write('UPDATE jobs SET status=?,pid=? WHERE id=?',('starting',process.pid,j['id']))
    def tick(self):
        with self.lock:
            for j in self.store.jobs():
                if j['status'] not in ACTIVE:continue
                directory=self.jobdir(j['id']);result={};alive=self.alive(j)
                try:result=json.loads((directory/'result.json').read_text())
                except (OSError,ValueError):pass
                if j['kind'] in {'viewer','tensorboard'}:
                    port=8080 if j['kind']=='viewer' else 6007;ready=False
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}',timeout=.25) as r:ready=r.status==200
                    except Exception:pass
                    owned=engine.owned_listener(port) if ready else False
                    result={'status':'running' if ready and owned else 'starting','ready':ready and owned,'port':port}
                    if not alive:
                        result['status']='completed' if ready and owned else ('stopped' if j['status']=='stopping' else 'failed')
                        result['message']='Service available' if ready and owned else 'Service stopped or failed; inspect its log'
                elif not alive and result.get('status') not in TERMINAL:result={'status':'interrupted','message':'Worker exited without a final result. Check logs and resume from a saved checkpoint.'}
                elif not result:result={'status':'starting'}
                if j['kind']=='train' and alive:
                    try:
                        import re
                        with (directory/'console.log').open('rb') as fd:
                            fd.seek(max(0,(directory/'console.log').stat().st_size-16000));tail=fd.read().decode('utf-8','replace')
                        iterations=re.findall(r'Iteration (\d+)/(\d+)',tail)
                        if iterations:result['iteration'],result['iteration_target']=map(int,iterations[-1])
                    except OSError:pass
                status='stopping' if alive and j['status']=='stopping' else result.get('status','running')
                # Do not start another GPU task until the old worker has released its lock.
                if alive and status in TERMINAL:status='running'
                self.store.write('UPDATE jobs SET status=?,result=? WHERE id=?',(status,json.dumps(result),j['id']))
            jobs=self.store.jobs();busy=any(j['kind'] not in {'viewer','tensorboard'} and j['status'] in ACTIVE for j in jobs)
            for job in reversed(jobs):
                if job['status']!='queued':continue
                if job['kind'] not in {'viewer','tensorboard'} and busy:continue
                if job['kind']=='reset' and any(j['status'] in ACTIVE for j in jobs):continue
                try:self.launch(job)
                except Exception as exc:self.store.write('UPDATE jobs SET status=?,result=? WHERE id=?',('failed',json.dumps({'message':str(exc)}),job['id']))
                if job['kind'] not in {'viewer','tensorboard'}:busy=True
            if time.time()-self.last_scan>8:
                scan(self.store,engine.RUN_ROOT,engine.REPORTS);self.last_scan=time.time()
        if time.time()-self.last_hardware>5:
            self.last_hardware=time.time();data={'host':os.uname().nodename,'platform':'WSL' if 'microsoft' in os.uname().release.lower() else 'Linux','kernel':os.uname().release,'load':os.getloadavg(),'disk_free':shutil.disk_usage(self.root).free,'gpus':[]}
            smi=shutil.which('nvidia-smi') or '/usr/lib/wsl/lib/nvidia-smi'
            try:
                r=subprocess.run([smi,'--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
                for line in r.stdout.splitlines():
                    fields=[v.strip() for v in line.split(',')]
                    if len(fields)==5:data['gpus'].append(dict(zip(['name','used','total','utilization','temperature'],fields)))
                if r.returncode:data['gpu_error']=r.stderr[-500:]
            except (OSError,subprocess.TimeoutExpired):data['gpu_error']='NVIDIA interface not available yet'
            self.hardware=data;self.store.write('INSERT INTO telemetry VALUES(?,?)',(time.time(),json.dumps(data)))
            self.store.write('DELETE FROM telemetry WHERE at < ?',(time.time()-86400*7,))
    def state(self):
        with self.lock:
            models=self.store.rows('SELECT * FROM models ORDER BY modified DESC');protected=self.protected()
            for m in models:m['protected']=m['id'] in protected
            services={}
            for kind,port in [('viewer',8080),('tensorboard',6007)]:
                ready=False
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}',timeout=.2) as response:ready=response.status==200 and engine.owned_listener(port)
                except Exception:pass
                services[kind]={'ready':ready,'port':port,'state':'ready' if ready else 'not serving'}
            return {'version':'3.0.0','jobs':self.store.jobs(),'models':models,'evaluations':evaluations(engine.REPORTS),'hardware':self.hardware,
              'services':services,'environment_ready':(engine.REPO/'.venv/bin/python').is_file(),
              'paths':{'runtime':str(engine.BASE),'studio':str(self.root)},'processes':engine.existing_viewer_or_worker(),
              'presets':[{**r,'spec':json.loads(r['spec'])} for r in self.store.rows('SELECT * FROM presets ORDER BY name')]}
