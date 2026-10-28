"""Regression tests for the actual configuration and service boundaries."""
import contextlib
import importlib.util
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest import mock

spec=importlib.util.spec_from_file_location('engine',Path(__file__).parents[1]/'scripts/xgoduck_engine.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
N=types.SimpleNamespace

class Regressions(unittest.TestCase):
    def test_all_profiles_apply_to_environment_not_train_container(self):
        for profile in e.PROFILES:
            with self.subTest(profile=profile):
                rewards={key:N(weight=1,params={}) for key in ('head_pose_bias','track_linear_velocity','track_angular_velocity','upright','pose','air_time','head_pose_tracking','foot_swing_height','action_rate_l2')}
                env=N(scene=N(num_envs=1),events={'push_robot':object()},curriculum={},
                      commands={'twist':N(ranges=N()),'head_pose':N()},rewards=rewards,
                      observations=object(),actions=object())
                cfg=N(env=env,agent=N(algorithm=N()))
                layout=(env.observations,env.actions)
                train=types.ModuleType('mjlab.scripts.train')
                train.TrainConfig=N(from_task=lambda task:cfg)
                train.launch_training=mock.Mock()
                managers=types.ModuleType('mjlab.managers');managers.RewardTermCfg=lambda **kw:N(**kw)
                modules={key:types.ModuleType(key) for key in ('mjlab','mjlab.tasks','mjlab.scripts')}
                modules.update({'mjlab.scripts.train':train,'mjlab.managers':managers})
                args=N(envs=64,updates=8,save_every=8,tag='test',seed=3,profile=profile,parent='')
                with mock.patch.dict(sys.modules,modules):self.assertEqual(e.worker_train(args),0)
                self.assertEqual(layout,(env.observations,env.actions))
                self.assertIn('forward_progress',env.rewards)
                self.assertEqual(cfg.agent.max_iterations,8)
                train.launch_training.assert_called_once_with(e.TASK,cfg)

    def test_cli_bounded_and_forever_are_distinct(self):
        self.assertFalse(e.parser().parse_args(['run']).forever)
        self.assertTrue(e.parser().parse_args(['run','--forever']).forever)

    def test_eval_interrupt_does_not_retry_or_train(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(e,'REPORTS',Path(td)),mock.patch.object(e,'run_subprocess',return_value=130) as run:
            with self.assertRaises(KeyboardInterrupt):e.evaluate_checkpoint({},Path(td)/'model_7.pt')
            self.assertEqual(run.call_count,1)

    def test_service_rejects_occupied_port_without_starting_child(self):
        with tempfile.TemporaryDirectory() as td,socket.socket() as sock:
            sock.bind(('127.0.0.1',0));sock.listen()
            with mock.patch.object(e,'HOME',Path(td)),mock.patch.object(e.subprocess,'Popen') as start:
                with self.assertRaisesRegex(RuntimeError,'occupied'):
                    e.serve(['unused'],'test',sock.getsockname()[1])
                start.assert_not_called()

    def test_service_reports_child_error_and_log(self):
        with tempfile.TemporaryDirectory() as td,socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
            child=N(poll=lambda:7,returncode=7)
            with mock.patch.multiple(e,HOME=Path(td),REPORTS=Path(td),REPO=Path(td)),mock.patch.object(e.subprocess,'Popen',return_value=child):
                with self.assertRaisesRegex(RuntimeError,'exited 7'):
                    e.serve(['unused'],'test',port)

    def test_no_preflight_checkpoint_in_viewer(self):
        with tempfile.TemporaryDirectory() as td,mock.patch.multiple(e,STATE_PATH=Path(td)/'state.json',BEST_DIR=Path(td)):
            self.assertIsNone(e.viewer_checkpoint(True))

if __name__=='__main__':unittest.main()
