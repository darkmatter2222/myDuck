import json,tempfile,threading,urllib.request,urllib.error
from pathlib import Path
from unittest import TestCase,mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.schema import training,overrides
from studio.manager import Manager,engine
from studio.catalog import scan,identifier
from studio.server import make_handler,ThreadingHTTPServer

class WebTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.runs=self.root/'runtime/logs';self.reports=self.root/'reports';self.runs.mkdir(parents=True)
        self.patch=mock.patch.multiple(engine,RUN_ROOT=self.runs,REPORTS=self.reports,REPO=self.root/'repo',BASE=self.root/'runtime');self.patch.start()
        self.manager=Manager(self.root/'control')
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def add_model(self,run='first',step=1999):
        p=self.runs/run/f'model_{step}.pt';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'test-model');scan(self.manager.store,self.runs,self.reports);return identifier(str(p.relative_to(self.runs)))
    def test_validation_rejects_unknown_nonfinite_and_unsafe_values(self):
        for spec in [{'environments':True},{'environments':0},{'seed':-1},{'shell':'rm'},{'stages':[]},{'forever':'yes'}]:
            with self.assertRaises(ValueError):training(spec)
        for spec in [{'lr':float('nan')},{'shell':1},{'forward_min':.8,'forward_max':.3}]:
            with self.assertRaises(ValueError):overrides(spec)
        self.assertEqual(training({})['stages'][0]['blocks'],5)
    def test_queue_preserves_immutable_parent_config(self):
        mid=self.add_model();jid=self.manager.enqueue('train',{'name':'Branch','parent':mid})
        job=self.manager.store.jobs()[0];self.assertEqual(job['spec']['parent'],mid)
        self.assertIn(mid,self.manager.protected())
        self.assertEqual(json.loads((self.manager.jobdir(jid)/'spec.json').read_text())['config'],job['spec'])
        with self.assertRaises(ValueError):self.manager.delete([mid],True)
        self.manager.stop(jid);self.manager.delete([mid],True);self.assertFalse((self.runs/'first/model_1999.pt').exists())
    def test_pins_preview_delete_and_deleted_history(self):
        mid=self.add_model();self.manager.annotate(mid,{'pinned':True,'label':'baseline','collection':'keepers'})
        with self.assertRaises(ValueError):self.manager.delete([mid],True)
        self.manager.annotate(mid,{'pinned':False});self.assertEqual(self.manager.delete([mid])['count'],1)
        self.assertTrue((self.runs/'first/model_1999.pt').exists());self.manager.delete([mid],True)
        self.assertEqual(self.manager.store.rows('SELECT deleted FROM models')[0]['deleted'],1)
    def test_missing_checkpoint_viewer_rejected_without_process(self):
        with mock.patch('studio.manager.subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):self.manager.enqueue('viewer',{'model':'missing'})
            spawn.assert_not_called()
    def test_catalog_parent_edges_and_symlink_escape(self):
        first=self.add_model();train=self.reports/'train';train.mkdir(parents=True)
        (train/'log.log').write_text(f'START training parent={self.runs}/first/model_1999.pt profile=gait envs=4096 updates=2000 tag=branch\n')
        second=self.add_model('dated-branch',3998)
        rows={r['id']:r for r in self.manager.store.rows('SELECT * FROM models')};self.assertEqual(rows[second]['parent'],first)
        outside=self.root/'model_100.pt';outside.touch();(self.runs/'first/model_100.pt').symlink_to(outside)
        scan(self.manager.store,self.runs,self.reports);self.assertEqual(len(self.manager.store.rows('SELECT * FROM models')),2)
    def test_reset_cancels_queued_work_and_blocks_new_jobs(self):
        jid=self.manager.enqueue('train',{});reset=self.manager.reset()
        jobs={j['id']:j for j in self.manager.store.jobs()};self.assertEqual(jobs[jid]['status'],'cancelled');self.assertEqual(jobs[reset]['kind'],'reset')
        with self.assertRaisesRegex(ValueError,'Reset is pending'):self.manager.enqueue('train',{})
    def test_queue_serializes_training(self):
        first=self.manager.enqueue('train',{});self.manager.enqueue('train',{})
        self.manager.last_scan=self.manager.last_hardware=__import__('time').time()
        with mock.patch.object(self.manager,'launch') as launch:self.manager.tick()
        launch.assert_called_once();self.assertEqual(launch.call_args[0][0]['id'],first)
    def test_persistence_survives_manager_restart(self):
        jid=self.manager.enqueue('train',{});second=Manager(self.root/'control');self.assertEqual(second.store.jobs()[0]['id'],jid)
    def test_api_security_and_empty_state(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'secret',{'127.0.0.1'}));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(url+'/') as r:self.assertIn(b'Checkpoint tree',r.read())
            for headers in [{},{'X-Studio-Token':'wrong'},{'X-Studio-Token':'secret','Origin':'https://evil.example'},{'X-Studio-Token':'secret','Host':'evil.example'}]:
                req=urllib.request.Request(url+'/api/jobs',data=b'{"kind":"setup"}',headers=headers,method='POST')
                with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(req)
                self.assertEqual(exc.exception.code,403)
            req=urllib.request.Request(url+'/api/state',headers={'X-Studio-Token':'secret'})
            with urllib.request.urlopen(req) as r:state=json.load(r);self.assertEqual(state['models'],[])
            req=urllib.request.Request(url+'/api/jobs',data=b'{"kind":"viewer","config":{"model":"absent"}}',headers={'X-Studio-Token':'secret'},method='POST')
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(req)
            self.assertEqual(exc.exception.code,400)
            self.assertEqual(self.manager.store.jobs(),[])
        finally:server.shutdown();server.server_close();thread.join()
