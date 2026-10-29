import socket
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase,mock
from test_engine import e

class StudioTests(TestCase):
    def test_owned_service_reused_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            port=listener.getsockname()[1]
            with mock.patch.object(e,'HOME',Path(tmp)),mock.patch.object(e,'owned_listener',return_value=True),mock.patch.object(e,'open_browser') as browser,mock.patch.object(e.subprocess,'Popen') as spawn:
                self.assertEqual(e.serve(['never'],'tensorboard',port),0)
                spawn.assert_not_called();browser.assert_called_once()

    def test_stop_scoped_processes_then_wait(self):
        with mock.patch.object(e,'existing_viewer_or_worker',side_effect=[[(123,'run'),(456,'viewer')],[],[]]),mock.patch.object(e.os,'kill') as kill:
            e.stop_project_processes()
            self.assertEqual(kill.call_args_list,[mock.call(123,e.signal.SIGINT),mock.call(456,e.signal.SIGTERM)])

    def test_unstoppable_process_blocks_reset(self):
        with mock.patch.object(e,'existing_viewer_or_worker',return_value=[(123,'viewer')]),mock.patch.object(e.os,'kill'):
            with self.assertRaisesRegex(RuntimeError,'nothing deleted'):e.stop_project_processes(timeout=0)

    def test_reset_stops_services_before_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);base=home/'xgoduck_oneclick';base.mkdir();(base/'state.json').write_text('{}')
            def stopped():self.assertTrue(base.exists())
            with mock.patch.multiple(e,HOME=home,BASE=base,LOCK_PATH=home/'.lock'),mock.patch.object(e,'stop_project_processes',side_effect=stopped) as stop,mock.patch.object(e,'known_controller_pid',return_value=None),mock.patch.object(e,'existing_viewer_or_worker',return_value=[]):
                self.assertEqual(e.cmd_reset(SimpleNamespace(confirm='DELETE')),0)
                stop.assert_called_once();self.assertFalse(base.exists())
