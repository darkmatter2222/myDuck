import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock
from test_engine import e
spec=importlib.util.spec_from_file_location('training_export',Path(__file__).resolve().parents[1]/'scripts/training_export.py')
x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)

class TrainingAuditTests(unittest.TestCase):
    def test_old_repeated_campaign_stops_without_reset(self):
        state={'history':[{'decision':'RETAINED','profile':'generalize','checkpoint':f'/run{i}/model_21992.pt'} for i in range(3)]}
        before=json.dumps(state)
        with self.assertRaisesRegex(RuntimeError,'Learning stalled'):e.check_learning_stall(state)
        self.assertEqual(json.dumps(state),before)
        state['history'][-1]['decision']='PROMOTED'
        e.check_learning_stall(state)

    def test_generalization_requires_forward_survival(self):
        ev={'forward_progress':.8,'survival':.99,'scenarios':[{'scenario':'forward','progress_ratio':.8,'full_survival':.5,'lateral_m':.1}]}
        self.assertFalse(e.gait_ready(ev))
        ev['scenarios'][0]['full_survival']=1
        self.assertTrue(e.gait_ready(ev))
        self.assertFalse(e.gait_ready({'forward_progress':1,'survival':1}))

    def test_generalize_continues_candidate_not_champion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ck=Path(tmp)/'model_21992.pt';ck.touch()
            state=e.new_state();state.update(total_updates=24000,trials=9,current_checkpoint=str(ck),best_checkpoint='/old/model_17993.pt',best_evaluation={'forward_progress':.8,'scenarios':[{'scenario':'forward','full_survival':1,'progress_ratio':.8,'lateral_m':0}]})
            with mock.patch.object(e,'write_state'):
                active=e.create_active(state,2000)
            self.assertEqual(active['profile'],'generalize')
            self.assertEqual(active['parent'],str(ck))

    def test_bundle_preserves_models_events_lineage_and_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'base';source=root/'source';source.mkdir();base.mkdir()
            (base/'state.json').write_text('{"trials":3}')
            train=base/'reports/train';train.mkdir(parents=True)
            for i in range(3):(train/f'{i}.log').write_text(f'START training parent=/old/model_17993.pt profile=generalize envs=4096 updates=4000 tag=c{i}\n')
            run=base/'xgoduck_rl/logs/rsl_rl/xgoduck_velocity/run';run.mkdir(parents=True)
            (run/'events.out.tfevents.test').write_bytes(b'raw-event')
            (run/'model_21992.pt').write_bytes(b'preserve-model')
            (train/'escape.log').symlink_to('/etc/passwd')
            output=root/'evidence.zip'
            x.export_training(base,source,output)
            with zipfile.ZipFile(output) as z:
                names=z.namelist()
                self.assertIn('training/run/events.out.tfevents.test',names)
                self.assertNotIn('reports/train/escape.log',names)
                self.assertFalse(any(n.endswith('.pt') for n in names))
                self.assertEqual(len(json.loads(z.read('repeated_branches.json'))[0]['attempts']),3)
                self.assertEqual(len(json.loads(z.read('checkpoint_inventory.json'))),1)
            self.assertEqual((run/'model_21992.pt').read_bytes(),b'preserve-model')
            with self.assertRaises(FileExistsError):x.export_training(base,source,output)
            capped=root/'capped.zip'
            manifest=x.export_training(base,source,capped,max_total=1)
            self.assertTrue(any('Size cap' in w for w in manifest['warnings']))
