import json,os,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.lifecycle import stop_existing,bind_server
from http.server import BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[1]
class LifecycleTests(unittest.TestCase):
    def test_busy_port_is_preserved(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));sock.listen();port=sock.getsockname()[1]
            server=bind_server(port,BaseHTTPRequestHandler)
            try:self.assertNotEqual(server.server_address[1],port)
            finally:server.server_close()
    def test_unverified_process_is_not_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            record=Path(tmp)/'server.json';record.write_text(json.dumps({'pid':os.getpid(),'identity':'wrong'}))
            self.assertFalse(stop_existing(record))
    def test_restart_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            cmd=[sys.executable,'-m','studio.server','--state-dir',tmp,'--port',str(port)]
            processes=[]
            def launch():
                p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);processes.append(p)
                for _ in range(100):
                    try:
                        record=json.loads((Path(tmp)/'server.json').read_text())
                        if record['pid']==p.pid:return p
                    except (OSError,ValueError):pass
                    if p.poll() is not None:self.fail(p.stderr.read().decode())
                    time.sleep(.05)
                self.fail('startup timeout')
            try:
                first=launch()
                if not json.loads((Path(tmp)/'server.json').read_text())['identity']:
                    self.skipTest('Execution host /proc does not expose the child PID namespace')
                second=launch();first.wait(timeout=5)
                self.assertIsNone(second.poll())
                result=subprocess.run(cmd+['--stop'],cwd=ROOT,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr);second.wait(timeout=5)
                self.assertFalse((Path(tmp)/'server.json').exists())
            finally:
                for p in processes:
                    if p.poll() is None:p.terminate();p.wait(timeout=5)
                    p.stderr.close()
