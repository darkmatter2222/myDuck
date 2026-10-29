"""Offline structural tests. Run: python -m unittest discover -s tests -v"""
import contextlib
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import importlib.util
import os
import tempfile

ENGINE=Path(__file__).resolve().parents[1]/'scripts'/'xgoduck_engine.py'
spec=importlib.util.spec_from_file_location('xgoduck_engine',ENGINE)
e=importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

class EngineTests(TestCase):
    def test_checkpoint_index(self):
        self.assertEqual(e.checkpoint_index('model_1999.pt'),1999)
        self.assertEqual(e.checkpoint_index('/foo/model_3998.pt'),3998)
        self.assertIsNone(e.checkpoint_index('model_3999.onnx'))

    def test_nonwalking_reward_cannot_beat_forward_motion(self):
        good={'score':28,'survival':.8,'forward_progress':.25}
        old={'score':80,'survival':1.,'forward_progress':0.0}
        self.assertTrue(e.significant_improvement(good,old))
        bad={'score':99,'survival':1.,'forward_progress':0.0}
        self.assertFalse(e.significant_improvement(bad,old))

    def test_score_requires_translation(self):
        rec=[dict(scenario=k,progress_ratio=0.,survival_ratio=1.,distance_m=0.,lateral_m=0.) for k in e.SCENARIOS]
        no_motion=e.summarize_evaluation(rec)
        rec2=[{**r,'progress_ratio':.75} if r['scenario']=='forward' else r for r in rec]
        walking=e.summarize_evaluation(rec2)
        self.assertEqual(no_motion['forward_progress'],0)
        self.assertGreater(walking['score'],no_motion['score']+40)

    def test_fresh_baseline_uses_one_lineage_10k_not_five_random_2k(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with mock.patch.multiple(e,
                BASE=root/'xgoduck_oneclick',
                REPO=root/'xgoduck_oneclick'/'xgoduck_rl',
                STATE_PATH=root/'xgoduck_oneclick'/'state.json',
                RUN_ROOT=root/'xgoduck_oneclick'/'xgoduck_rl'/'logs'/'rsl_rl'/'xgoduck_velocity',
                REPORTS=root/'xgoduck_oneclick'/'reports',
                BEST_DIR=root/'xgoduck_oneclick'/'best'):
                (e.REPO/'.venv/bin').mkdir(parents=True)
                (e.REPO/'.venv/bin/python').write_text('stub')
                snapshots=[]
                def fake_training(s,a,_):
                    snapshots.append((a['parent'],a['target'],a['profile'],a['random_restart']))
                    folder=e.RUN_ROOT/('fake_'+a['id'])
                    folder.mkdir(parents=True,exist_ok=True)
                    cp=folder/f"model_{a['target']}.pt"
                    cp.write_bytes(b'0'*2048)
                    return cp
                args=SimpleNamespace(environments=4096,block_iterations=2000,save_every=200,
                    eval_envs=2,eval_seeds=2,eval_seconds=10.,forever=False,max_updates=10000)
                oldcwd=os.getcwd()
                try:
                    with mock.patch.object(e,'exclusive_lock',return_value=contextlib.nullcontext()),\
                        mock.patch.object(e,'train_active',side_effect=fake_training),\
                        mock.patch.object(e,'preflight',return_value=None),\
                        mock.patch.object(e,'evaluate_checkpoint',return_value=dict(score=15.,forward_progress=0.,survival=1.,reverse_progress=0.,yaw_progress=0.)),\
                        mock.patch.object(e,'free_disk_gb',return_value=100.),\
                        mock.patch.object(e,'PID_PATH',root/'pid'):
                        self.assertEqual(e.run_autopilot(args),0)
                finally:os.chdir(oldcwd)
                self.assertEqual(len(snapshots),5)
                self.assertIsNone(snapshots[0][0])
                self.assertEqual([x[1] for x in snapshots],[1999,3998,5997,7996,9995])
                self.assertTrue(all(x[0] is not None for x in snapshots[1:]))
                self.assertTrue(all(x[2]=='gait' for x in snapshots))
                self.assertEqual(e.read_json(e.STATE_PATH)['total_updates'],10000)

    def test_no_walking_does_not_reset_to_early_champion_after_ten_k(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)/'model_9995.pt'; parent.write_bytes(b'1'*2048)
            ck=Path(td)/'model_11994.pt';ck.write_bytes(b'1'*2048)
            with mock.patch.multiple(e,
                    REPORTS=Path(td)/'reports',BEST_DIR=Path(td)/'best',
                    STATE_PATH=Path(td)/'state.json'):
                s=e.new_state()
                s.update(total_updates=10000,trials=5,current_checkpoint=str(parent),
                         best_checkpoint=str(parent),
                         best_evaluation=dict(score=50.,survival=1.,forward_progress=0.0))
                a={'id':'gait_more_progress_test','profile':'gait_more_progress','block':2000,
                   'attempts':[],'random_restart':False}
                e.complete_active(s,a,ck,ev=dict(score=40.,survival=.9,forward_progress=0.0,
                    reverse_progress=0.,yaw_progress=.0))
                self.assertEqual(s['current_checkpoint'],str(ck))
                self.assertEqual(s['best_checkpoint'],str(parent))

    def test_reset_only_exact_app_owned_directory(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);base=home/'xgoduck_oneclick';base.mkdir()
            (base/'state.json').write_text('{}')
            (home/'xgoduck_rl').mkdir()
            legacy=home/'xgoduck_rl'/'important.txt';legacy.write_text('keep')
            with mock.patch.multiple(e,HOME=home,BASE=base,LOCK_PATH=home/'.lock'),\
               mock.patch.object(e,'known_controller_pid',return_value=None):
                self.assertEqual(e.cmd_reset(SimpleNamespace(confirm='DELETE')),0)
                self.assertFalse(base.exists())
                self.assertEqual(legacy.read_text(),'keep')

    def test_no_explicit_delete_confirmation_refused(self):
        with self.assertRaisesRegex(RuntimeError,'requires one explicit DELETE'):
            e.cmd_reset(SimpleNamespace(confirm='yes'))

    def test_missing_state_with_checkpoints_blocks_random_restart(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);runs=root/'logs';a=runs/'some_run';a.mkdir(parents=True)
            (a/'model_1999.pt').write_bytes(b'2'*2048)
            with mock.patch.multiple(e,STATE_PATH=root/'state.json',RUN_ROOT=runs):
                with self.assertRaisesRegex(RuntimeError,'Refusing to start random weights'):
                    e.get_state()


    def test_active_checkpoint_selection_and_complete_no_retraining(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with mock.patch.object(e,'RUN_ROOT',root):
                tags=['a1','a2']
                for name,number in [('a1',2600),('a2',3998)]:
                    d=root/('2026-10-28_'+name)
                    d.mkdir()
                    (d/f'model_{number}.pt').write_bytes(b'0'*2048)
                active={'target':3998,'environments':4096,'attempts':[{'tag':name} for name in tags]}
                self.assertEqual(e.active_checkpoint(active).name,'model_3998.pt')
                with mock.patch.object(e,'run_subprocess',side_effect=AssertionError('must not retrain')):
                    self.assertEqual(e.train_active({},active,2000).name,'model_3998.pt')

    def test_missing_evaluation_does_not_erase_good_model(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cp=root/'model_1999.pt'
            cp.write_bytes(b'0'*2048)
            with mock.patch.multiple(e,REPORTS=root/'reports',BEST_DIR=root/'best',STATE_PATH=root/'state.json'):
                state=e.new_state()
                active={'id':'c01-gait','profile':'gait','block':2000,'attempts':[],'random_restart':False}
                e.complete_active(state,active,cp,None)
                self.assertEqual(state['current_checkpoint'],str(cp))
                self.assertIsNone(state['best_checkpoint'])
                self.assertTrue(cp.exists())
                self.assertEqual(state['history'][-1]['decision'],'EVAL_FAILED')

    def test_post_baseline_search_blocks_longer_than_two_k(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cp=root/'model_9995.pt';cp.write_bytes(b'0'*2048)
            with mock.patch.object(e,'STATE_PATH',root/'state.json'):
                state=e.new_state();state.update(total_updates=10000,trials=5,current_checkpoint=str(cp),
                    best_evaluation=dict(score=40.,forward_progress=0.0,survival=1.0))
                active=e.create_active(state,2000)
                self.assertEqual(active['block'],4000)
                self.assertEqual(active['parent'],str(cp))
                self.assertEqual(active['target'],13994)

    def test_reset_blocks_when_known_viewer_running(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);base=home/'xgoduck_oneclick';base.mkdir()
            with mock.patch.multiple(e,HOME=home,BASE=base,LOCK_PATH=home/'.lock'),\
              mock.patch.object(e,'known_controller_pid',return_value=None),\
              mock.patch.object(e,'existing_viewer_or_worker',return_value=[(777,'viewer')]),\
              mock.patch.object(e,'stop_project_processes',side_effect=RuntimeError('Project processes did not stop')):
                with self.assertRaisesRegex(RuntimeError,'Project processes did not stop'):
                    e.cmd_reset(SimpleNamespace(confirm='DELETE'))
                self.assertTrue(base.is_dir())

if __name__=='__main__':
    import unittest
    unittest.main()
