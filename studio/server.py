import signal
from .lifecycle import stop_existing,bind_server,identity
import argparse,fcntl,json,logging,math,os,secrets,sys,threading,time,subprocess,urllib.parse
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from .manager import Manager,ROOT,engine
from .schema import training
from .analysis import analyze

def clean(obj):
    if isinstance(obj,float) and not math.isfinite(obj):return None
    if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):return [clean(v) for v in obj]
    return obj

def make_handler(manager,token,hosts):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):logging.info('%s %s',self.client_address[0],fmt%args)
        def send(self,data,code=200,ctype='application/json'):
            if ctype=='application/json':data=json.dumps(clean(data),allow_nan=False).encode()
            elif isinstance(data,str):data=data.encode()
            self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        def authorized(self,mutating=False):
            host=self.headers.get('Host','').split(':')[0].lower()
            if host not in hosts:raise PermissionError('Unrecognized host; use the printed localhost URL or SSH forwarding')
            if mutating and not secrets.compare_digest(self.headers.get('X-Studio-Token',''),token):raise PermissionError('Refresh this page to reconnect to Studio')
            origin=self.headers.get('Origin')
            if mutating and origin and urllib.parse.urlparse(origin).netloc!=self.headers.get('Host'):raise PermissionError('Cross-origin request blocked')
        def do_GET(self):
            try:
                self.authorized();parsed=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(parsed.query);path=parsed.path
                if path=='/health':return self.send({'app':'myduck-studio','version':'3.0.0'})
                if path in ('/','/index.html','/app.js','/style.css'):
                    name='index.html' if path=='/' else path[1:];content=(ROOT/'web'/name).read_text().replace('__STUDIO_TOKEN__',token)
                    return self.send(content,ctype={'index.html':'text/html; charset=utf-8','app.js':'application/javascript','style.css':'text/css'}[name])
                self.authorized(True)
                if path=='/api/state':return self.send(manager.state())
                if path=='/api/audit':return self.send(manager.store.rows('SELECT * FROM audit ORDER BY at DESC LIMIT 500'))
                if path=='/api/telemetry':return self.send([{'at':r['at'],**json.loads(r['data'])} for r in manager.store.rows('SELECT * FROM telemetry ORDER BY at DESC LIMIT 1000')][::-1])
                if path=='/api/log':
                    directory=manager.jobdir(query.get('id',[''])[0]);pieces=[]
                    paths=list(directory.glob('*.log'))
                    for p in (engine.REPORTS/'train').glob('*studio-'+directory.name+'*.log'):paths.append(p)
                    for p in paths[-8:]:
                        with p.open('rb') as fd:fd.seek(max(0,p.stat().st_size-64000));pieces.append('=== '+p.name+' ===\n'+fd.read(64000).decode('utf-8','replace'))
                    return self.send({'text':'\n'.join(pieces) or 'No log output yet.'})
                if path in ('/api/evidence','/api/onnx'):
                    name='policy.onnx' if path=='/api/onnx' else 'training-evidence.zip'
                    file=manager.jobdir(query.get('id',[''])[0])/name
                    if not file.is_file():raise ValueError('Evidence bundle is not ready')
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(file.stat().st_size));self.send_header('Content-Disposition','attachment; filename="'+name+'"');self.end_headers()
                    with file.open('rb') as fd:
                        while chunk:=fd.read(1024*1024):self.wfile.write(chunk)
                    return
                return self.send({'error':'Not found'},404)
            except PermissionError as exc:self.send({'error':str(exc)},403)
            except (ValueError,OSError) as exc:self.send({'error':str(exc)},400)
            except Exception:logging.exception('GET failed');self.send({'error':'Server error; see studio.log'},500)
        def do_POST(self):
            try:
                self.authorized(True);length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024*1024:raise ValueError('Invalid request length')
                body=json.loads(self.rfile.read(length));path=urllib.parse.urlparse(self.path).path
                if not isinstance(body,dict):raise ValueError('Expected a JSON object')
                if path=='/api/analysis':return self.send(analyze(body))
                if path=='/api/jobs':return self.send({'id':manager.enqueue(body.get('kind'),body.get('config',{}))},201)
                if path=='/api/service-stop':manager.stop_service(body.get('kind'));return self.send({'ok':True})
                if path=='/api/stop':manager.stop(body.get('id'));return self.send({'ok':True})
                if path=='/api/reset':
                    if body.get('confirm')!='DELETE':raise ValueError('Reset requires explicit confirmation')
                    return self.send({'id':manager.reset()})
                if path=='/api/models/delete':return self.send(manager.delete(body.get('ids'),body.get('confirm') is True))
                if path=='/api/models/update':manager.annotate(body.get('id'),body.get('changes',{}));return self.send({'ok':True})
                if path=='/api/presets':
                    spec=training(body.get('config'));name=spec['name']
                    manager.store.write('INSERT INTO presets VALUES(?,?) ON CONFLICT(name) DO UPDATE SET spec=excluded.spec',(name,json.dumps(spec)))
                    return self.send({'ok':True})
                if path=='/api/scalars':
                    ids=body.get('ids',[])
                    if not isinstance(ids,list) or not 1<=len(ids)<=6:raise ValueError('Select up to 6 checkpoints')
                    runs=sorted({str(manager.model(mid)[1].parent) for mid in ids});python=engine.REPO/'.venv/bin/python'
                    if not python.exists():raise ValueError('Training environment is not installed yet')
                    tag=body.get('tag','')
                    if not isinstance(tag,str) or len(tag)>300:raise ValueError('Invalid metric tag')
                    result=subprocess.run([str(python),str(ROOT/'scripts/scalar_reader.py')],input=json.dumps({'runs':runs,'tag':tag,'all':body.get('all') is True}),capture_output=True,text=True,timeout=30)
                    if result.returncode:raise ValueError('TensorBoard event reader failed: '+result.stderr[-600:])
                    return self.send(json.loads(result.stdout))
                return self.send({'error':'Not found'},404)
            except PermissionError as exc:self.send({'error':str(exc)},403)
            except (ValueError,TypeError,OSError,subprocess.TimeoutExpired) as exc:self.send({'error':str(exc)},400)
            except Exception:logging.exception('POST failed');self.send({'error':'Server error; see studio.log'},500)
    return Handler

def main():
    parser=argparse.ArgumentParser(description='myDuck Studio local web utility')
    parser.add_argument('--stop',action='store_true',help='Stop only the Studio web server; running workers continue')
    parser.add_argument('--port',type=int,default=8765);parser.add_argument('--state-dir',type=Path);parser.add_argument('--allow-host',action='append',default=[])
    args=parser.parse_args();manager=Manager(args.state_dir)
    logging.basicConfig(filename=manager.root/'studio.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    record=manager.root/'server.json'
    if args.stop:
        print('Studio web server stopped; running workers are preserved.' if stop_existing(record) else 'No verified Studio instance is running for this workspace.')
        return
    stop_existing(record)
    lock=(manager.root/'server.lock').open('a+')
    for attempt in range(40):
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            if attempt==39:raise SystemExit('Studio is already running but cannot be safely identified. Stop it with Ctrl+C in its terminal, then retry.')
            time.sleep(.05)
    token=secrets.token_urlsafe(32)
    try:server=bind_server(args.port,make_handler(manager,token,{'localhost','127.0.0.1',*args.allow_host}))
    except (OSError,ValueError) as exc:raise SystemExit('Cannot start Studio: '+str(exc))
    args.port=server.server_address[1]
    record.write_text(json.dumps({'pid':os.getpid(),'identity':identity(os.getpid()),'port':args.port}))
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    def monitor():
        while True:
            try:manager.tick()
            except Exception:logging.exception('Monitor failed')
            time.sleep(2)
    threading.Thread(target=monitor,daemon=True).start()
    print(f'\nmyDuck Studio 3.0\nOpen in your Windows browser: http://localhost:{args.port}\nHost: {os.uname().nodename}\nLogs: {manager.root}/studio.log\nCtrl+C stops the web server. Queued work pauses; running jobs retain their own processes.\n',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:print('Studio stopped. Restart this command to reconnect to running jobs.')
    finally:
        server.server_close();record.unlink(missing_ok=True);lock.close()
if __name__=='__main__':main()
