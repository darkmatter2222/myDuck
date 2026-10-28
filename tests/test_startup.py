import contextlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
e=module('startup_engine','xgoduck_engine.py')
step=module('setup_step','setup_step.py')

class StartupTests(unittest.TestCase):
    def test_setup_step_merges_stderr_and_preserves_failure(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            rc=step.run_step([sys.executable,'-c','import sys; print("progress",file=sys.stderr); sys.exit(7)'],'probe',10)
        self.assertEqual(rc,7);self.assertIn('progress',out.getvalue())

    def test_setup_step_times_out_and_reports_heartbeat(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            rc=step.run_step([sys.executable,'-c','import time; time.sleep(30)'],'blocked',.3,.1)
        self.assertEqual(rc,124);self.assertIn('still running',out.getvalue())

    def test_tensorboard_preinstall_has_no_gpu_requirement(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);bin=home/'.local/bin';bin.mkdir(parents=True)
            for name in ('uv','uvx'):
                file=bin/name;file.write_text('#!/bin/sh\necho test-tool\n');file.chmod(0o755)
            result=subprocess.run(['bash',str(ROOT/'scripts/bootstrap.sh'),'--tensorboard-only'],env={**os.environ,'HOME':td},capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('TensorBoard only',result.stdout)
            self.assertFalse((home/'xgoduck_oneclick/xgoduck_rl').exists())
            self.assertTrue(list((home/'xgoduck_oneclick/reports/setup').glob('*.log')))

    def test_tensorboard_without_training_repo_uses_its_cache(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);uvx=home/'.local/bin/uvx';uvx.parent.mkdir(parents=True);uvx.touch()
            with mock.patch.multiple(e,HOME=home,BASE=home/'project',REPO=home/'project/repo',RUN_ROOT=home/'project/repo/logs'),mock.patch.object(e,'serve',return_value=0) as serve:
                self.assertEqual(e.cmd_tensorboard(N()),0)
                self.assertEqual(serve.call_args.args[2],6007)
                self.assertIn('setuptools==80.9.0',serve.call_args.args[0])
                self.assertIn('--python',serve.call_args.args[0])
                self.assertFalse(e.REPO.exists())

    def test_missing_uvx_prepares_tensorboard_automatically(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.multiple(e,HOME=Path(td),BASE=Path(td)/'base',REPO=Path(td)/'repo'),mock.patch.object(e.subprocess,'call',return_value=0) as setup,mock.patch.object(e,'serve',return_value=0):
                e.cmd_tensorboard(N())
                self.assertEqual(setup.call_args.args[0][-1],'--tensorboard-only')

    def test_real_http_service_becomes_ready_before_browser_opens(self):
        with tempfile.TemporaryDirectory() as td,socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1];reserve.close()
            code='from http.server import HTTPServer,BaseHTTPRequestHandler\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(b"ok")\nHTTPServer(("127.0.0.1",'+str(port)+'),H).handle_request()'
            with mock.patch.multiple(e,HOME=Path(td),BASE=Path(td),REPORTS=Path(td)/'reports'),mock.patch.object(e,'open_browser') as browser:
                self.assertEqual(e.serve([sys.executable,'-u','-c',code],'test',port),0)
                browser.assert_called_once_with(f'http://localhost:{port}')

    def test_diagnostics_survive_missing_install_and_failed_probes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);report=root/'report.txt';report.write_text('Windows section\n')
            with mock.patch.multiple(e,HOME=root,BASE=root/'base',REPO=root/'repo',REPORTS=root/'reports',STATE_PATH=root/'missing',PID_PATH=root/'pid'),mock.patch.object(e.subprocess,'run',side_effect=OSError('not installed')):
                self.assertEqual(e.cmd_diagnostics(N(output=str(report))),0)
            text=report.read_text();self.assertIn('Windows section',text);self.assertIn('WSL diagnostics',text);self.assertIn('Probe failed',text)

if __name__=='__main__':unittest.main()
