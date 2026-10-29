import contextlib,json,os,tempfile
from pathlib import Path
from unittest import TestCase,mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio import worker
from studio.schema import training
class WorkerTests(TestCase):
    def test_stage_sequence_continues_from_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';(repo/'.venv/bin').mkdir(parents=True);(repo/'.venv/bin/python').touch()
            job=root/'jobs/aabbccddeeff0011';job.mkdir(parents=True)
            config=training({'stages':[{'profile':'gait','updates':100,'blocks':2},{'profile':'gait_more_progress','updates':200,'blocks':1,'overrides':{'lr':.0002}}]})
            (job/'spec.json').write_text(json.dumps({'id':job.name,'kind':'train','config':config}))
            calls=[]
            def train(state,active,block):
                calls.append((active['parent'],active['profile'],json.loads(os.environ['MYDUCK_OVERRIDES'])))
                path=root/f'run{len(calls)}'/f'model_{active["target"]}.pt';path.parent.mkdir();path.touch();return path
            ev={'forward_progress':.2,'survival':.9,'score':25}
            with mock.patch.multiple(worker.e,REPO=repo,BASE=root,STATE_PATH=root/'old.json',PID_PATH=root/'pid'),mock.patch.object(worker.e,'exclusive_lock',side_effect=contextlib.nullcontext),mock.patch.object(worker.e,'preflight'),mock.patch.object(worker.e,'free_disk_gb',return_value=100),mock.patch.object(worker.e,'train_active',side_effect=train),mock.patch.object(worker.e,'evaluate_checkpoint',return_value=ev),mock.patch.object(worker.signal,'signal'),mock.patch.dict(os.environ,{},clear=False):
                worker.main(job)
            result=json.loads((job/'result.json').read_text());self.assertEqual(result['status'],'completed');self.assertEqual(result['updates'],400)
            self.assertIsNone(calls[0][0]);self.assertTrue(calls[1][0].endswith('model_99.pt'));self.assertTrue(calls[2][0].endswith('model_198.pt'));self.assertEqual(calls[2][2],{'lr':.0002})
