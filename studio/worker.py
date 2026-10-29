"""Detached, logged jobs. Each experiment owns immutable config and recovery state."""
import json,os,signal,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
import xgoduck_engine as e

def main(jobdir):
    jobdir=Path(jobdir);spec=json.loads((jobdir/'spec.json').read_text());kind=spec['kind'];config=spec['config']
    def status(state,**kw):e.atomic_json(jobdir/'result.json',dict(status=state,updated=time.time(),**kw))
    def stop(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    status('running',phase='starting')
    try:
        if kind=='setup':
            rc=e.run_subprocess(['bash',str(ROOT/'scripts/bootstrap.sh')],jobdir/'setup.log',ROOT,hang_seconds=1800)
            if rc==130:raise KeyboardInterrupt()
            if rc:raise RuntimeError(f'Setup exited {rc}; inspect the setup log')
        elif kind=='reset':e.cmd_reset(type('Args',(),{'confirm':'DELETE'})())
        elif kind=='export':
            from training_export import export_training
            export_training(e.BASE,ROOT,jobdir/'training-evidence.zip',studio_root=jobdir.parents[1])
        elif kind=='onnx':
            with e.exclusive_lock():
                cmd=[str(e.REPO/'.venv/bin/python'),str(e.REPO/'scripts/export.py'),e.TASK,'--checkpoint-file',config['checkpoint'],'--onnx-file',str(jobdir/'policy.onnx'),'--device','cpu','--num-envs','1']
                rc=e.run_subprocess(cmd,jobdir/'onnx.log',e.REPO,hang_seconds=600)
                if rc==130:raise KeyboardInterrupt()
                if rc or not (jobdir/'policy.onnx').is_file():raise RuntimeError('ONNX export failed; inspect the export log')
        elif kind=='evaluate':
            with e.exclusive_lock():
                status('running',phase='evaluating')
                ev=e.evaluate_checkpoint({},Path(config['checkpoint']),config['eval_envs'],config['eval_seeds'],config['eval_seconds'])
                if ev is None:raise RuntimeError('Evaluation failed on both devices')
                status('completed',evaluation=ev);return
        elif kind=='train':
            if not (e.REPO/'.venv/bin/python').is_file():
                status('running',phase='installing environment')
                rc=e.run_subprocess(['bash',str(ROOT/'scripts/bootstrap.sh')],jobdir/'setup.log',ROOT,hang_seconds=1800)
                if rc==130:raise KeyboardInterrupt()
                if rc:raise RuntimeError('Setup failed; no training started')
            with e.exclusive_lock():
                e.PID_PATH.write_text(str(os.getpid()))
                e.STATE_PATH=jobdir/'state.json'
                state=e.read_json(e.STATE_PATH) or e.new_state()
                state.update(environments=config['environments'],save_every=config['save_every'])
                status('running',phase='GPU and evaluator preflight')
                # Separate preflight; no user overrides until their stage is selected.
                os.environ.pop('MYDUCK_OVERRIDES',None)
                e.preflight(state)
                parent=config.get('checkpoint');cycle=0;total=0;best=None;stalled=0
                while True:
                    for index,stage in enumerate(config['stages']):
                        os.environ['MYDUCK_OVERRIDES']=json.dumps(stage['overrides'])
                        for block in range(stage['blocks']):
                            if e.free_disk_gb(e.BASE)<e.MIN_FREE_GB:raise RuntimeError('Low disk space; checkpoint files preserved')
                            tag=f'studio-{spec["id"]}-s{index+1}-c{cycle+1}-b{block+1}'
                            idx=e.checkpoint_index(parent)
                            active=dict(id=tag,profile=stage['profile'],seed=config['seed'],parent=parent,
                             target=(idx if idx is not None else 0)+stage['updates']-1,block=stage['updates'],
                             attempts=[],created=e.iso(),phase='training',random_restart=False,environments=config['environments'])
                            state['active']=active;e.write_state(state)
                            status('running',phase='training',stage=index+1,cycle=cycle+1,block=block+1,updates=total,parent=parent)
                            ck=e.train_active(state,active,stage['updates']);parent=str(ck);total+=stage['updates']
                            status('running',phase='evaluating',checkpoint=parent,updates=total,stage=index+1)
                            ev=e.evaluate_checkpoint(state,ck,config['eval_envs'],config['eval_seeds'],config['eval_seconds'])
                            if ev is None:raise RuntimeError('Evaluation failed. Resume manually from the saved checkpoint after review.')
                            improved=e.significant_improvement(ev,best)
                            if improved:best=ev;stalled=0
                            else:stalled+=1
                            state.update(active=None,current_checkpoint=parent,total_updates=total,best_evaluation=best)
                            state['history'].append(dict(checkpoint=parent,parent=active['parent'],evaluation=ev,stage=stage,at=e.iso()))
                            e.write_state(state)
                            if config['stall_limit'] and stalled>=config['stall_limit']:
                                status('paused',phase='review needed',message='No measured improvement across configured stall limit',checkpoint=parent,updates=total);return
                    if not config['forever']:break
                    cycle+=1
                status('completed',checkpoint=parent,updates=total,evaluation=ev);return
        else:raise ValueError('Unknown worker operation')
        status('completed',phase='finished')
    except KeyboardInterrupt:
        status('stopped',message='Stopped by user. Saved checkpoints retained.')
    except Exception as exc:
        traceback.print_exc();status('failed',message=str(exc))
    finally:
        try:
            if e.PID_PATH.read_text().strip()==str(os.getpid()):e.PID_PATH.unlink()
        except OSError:pass
if __name__=='__main__':main(sys.argv[1])
