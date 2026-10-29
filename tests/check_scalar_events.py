"""Integration check run in CI's real TensorBoard environment."""
import json,subprocess,sys,tempfile
from pathlib import Path
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary
with tempfile.TemporaryDirectory() as root:
    writer=EventFileWriter(root)
    for step,value in [(1,.25),(2,.5)]:writer.add_event(Event(wall_time=100+step,step=step,summary=Summary(value=[Summary.Value(tag='Train/reward',simple_value=value),Summary.Value(tag='Loss/value',simple_value=value*2)])))
    writer.flush();writer.close()
    reader=Path(__file__).resolve().parents[1]/'scripts/scalar_reader.py'
    result=subprocess.run([sys.executable,str(reader)],input=json.dumps({'runs':[root],'tag':'Train/reward'}),capture_output=True,text=True,check=True)
    data=json.loads(result.stdout)
    assert data['series'][0]['points']==[[1,.25,101],[2,.5,102]],data
    batch=subprocess.run([sys.executable,str(reader)],input=json.dumps({'runs':[root],'all':True}),capture_output=True,text=True,check=True)
    batch_data=json.loads(batch.stdout)
    assert {s['tag'] for s in batch_data['series']}=={'Train/reward','Loss/value'},batch_data
    assert all(len(s['points'])==2 for s in batch_data['series']),batch_data
    print('Real TensorBoard event-to-chart integration passed')
