#!/usr/bin/env python3
"""XGO-Duck Gait-First Autopilot, original Windows/WSL wrapper engine.

No Python packages beyond stdlib required for orchestration. Training and
fixed-command validation run as subprocesses under XgoDuck's pinned .venv.
The code intentionally prefers no work to the risk of destroying models.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import sys
import time
import traceback

HOME = Path.home()
BASE = HOME / 'xgoduck_oneclick'
REPO = BASE / 'xgoduck_rl'
STATE_PATH = BASE / 'state.json'
CONTROL_DIR = BASE / 'control'
REPORTS = BASE / 'reports'
RUN_ROOT = REPO / 'logs' / 'rsl_rl' / 'xgoduck_velocity'
BEST_DIR = BASE / 'best'
LOCK_PATH = HOME / '.xgoduck_oneclick.lock'
PID_PATH = HOME / '.xgoduck_oneclick.pid'
TASK = 'Mjlab-Velocity-Flat-XgoDuck'
VERSION = '2.1.0-desktop-diagnostics'
SEED = 48017
DATE_FORMAT = '%Y%m%d-%H%M%S'
STAGE_A_UPDATES = 10000
STAGE_A_BLOCK = 2000
DEFAULT_ENVIRONMENTS = 4096
MIN_FREE_GB = 6.0

# Controller levels are deliberately not optimized via proxy rewards; measured
# forward travel is the primary gate. Tests are only a proxy for actual hardware.
PROFILES = {
    'gait': dict(entropy=0.012, lr=0.0006, linear=6.0, angular=0.4, upright=1.2,
                 pose=0.4, air=0.55, head=0.2, swing=-0.4, smooth=-0.025, progress=4.0),
    'gait_more_progress': dict(entropy=0.015, lr=0.00045, linear=7.0, angular=0.4, upright=1.1,
                 pose=0.3, air=0.45, head=0.15, swing=-0.3, smooth=-0.02, progress=6.0),
    'gait_explore': dict(entropy=0.022, lr=0.00045, linear=6.5, angular=0.5, upright=1.1,
                 pose=0.3, air=0.7, head=0.15, swing=-0.2, smooth=-0.02, progress=5.0),
    'generalize': dict(entropy=0.008, lr=0.00025, linear=4.5, angular=2.0, upright=1.8,
                 pose=0.7, air=1.0, head=0.5, swing=-1.5, smooth=-0.1, progress=2.5),
}
SCENARIOS = {
    'stand': (0.0, 0.0, 0.0),
    'forward': (0.20, 0.0, 0.0),
    'reverse': (-0.15, 0.0, 0.0),
    'left-turn': (0.0, 0.0, 0.50),
    'right-turn': (0.0, 0.0, -0.50),
}


def say(*items):
    print('[XGO-ONECLICK]', *items, flush=True)


def iso():
    return datetime.now(timezone.utc).isoformat()


def stamp():
    return datetime.now().strftime(DATE_FORMAT)


def read_json(path: Path, default=None):
    if not path.is_file():
        return default
    with path.open(encoding='utf-8') as fd:
        return json.load(fd)


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as fd:
        json.dump(data, fd, indent=2, sort_keys=True, allow_nan=False)
        fd.write('\n')
        fd.flush()
        os.fsync(fd.fileno())
    os.replace(tmp, path)


def checkpoint_index(path: Path | str | None):
    if not path:
        return None
    match = re.fullmatch(r'model_(\d+)\.pt', Path(path).name)
    if match:
        return int(match.group(1))
    return None


def current_dir_for_tag(tag: str):
    if not RUN_ROOT.is_dir():
        return None
    matches = [p for p in RUN_ROOT.iterdir() if p.is_dir() and p.name.endswith('_'+tag)]
    return sorted(matches)[-1] if matches else None


def latest_checkpoint(run_dir: Path | None):
    if not run_dir or not run_dir.is_dir():
        return None
    entries = []
    for p in run_dir.glob('model_*.pt'):
        if p.is_file() and p.stat().st_size > 1024 and checkpoint_index(p) is not None:
            entries.append((checkpoint_index(p), p))
    return max(entries, default=(None,None), key=lambda x: x[0])[1]


def active_checkpoint(active: dict):
    matches=[]
    for attempt in active.get('attempts', []):
        p=latest_checkpoint(current_dir_for_tag(attempt['tag']))
        if p:
            matches.append((checkpoint_index(p),p))
    return max(matches,default=(None,None),key=lambda x:x[0])[1]


def find_latest_any_checkpoint():
    """Used only if state.json is missing. NEVER silently restart random weights."""
    if not RUN_ROOT.is_dir():
        return None
    all_ckpt=[]
    for p in RUN_ROOT.iterdir():
        if p.is_dir():
            cp=latest_checkpoint(p)
            if cp:
                all_ckpt.append((cp.stat().st_mtime,cp))
    return max(all_ckpt,default=(None,None),key=lambda x:x[0])[1]


@contextlib.contextmanager
def exclusive_lock():
    with LOCK_PATH.open('a+') as fd:
        try:
            fcntl.flock(fd.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Autopilot already running; refusing duplicate process or reset.') from exc
        try:
            yield
        finally:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)


def process_alive(pid: int):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError,ValueError):
        return False


def known_controller_pid():
    try:
        pid=int(PID_PATH.read_text().strip())
    except (ValueError,OSError):
        return None
    if not process_alive(pid):
        return None
    try:
        cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode('utf-8','replace').replace('\0',' ')
        if 'xgoduck_engine.py' in cmd and ' run ' in cmd:
            return pid
    except OSError:
        pass
    return None


def free_disk_gb(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free/1024**3


def new_state():
    return {'version':VERSION,'created':iso(),'campaign':stamp(), 'status':'new',
      'total_updates':0, 'stage':'gait-discovery', 'current_checkpoint':None,
      'best_checkpoint':None,'best_evaluation':None,'best_id':None,
      'trials':0,'stalled_trials':0,'active':None,'evaluations':0,
      'environments':DEFAULT_ENVIRONMENTS,'history':[],'last_error':None}


def get_state():
    s=read_json(STATE_PATH)
    if s is not None:
        return s
    existing=find_latest_any_checkpoint()
    if existing:
        raise RuntimeError('Saved model files exist but state.json is missing. Refusing to start random weights. Use status/repair or reset explicitly. Model: '+str(existing))
    return new_state()


def write_state(s):
    atomic_json(STATE_PATH,s)


def _copy_best_model(path:Path):
    BEST_DIR.mkdir(parents=True,exist_ok=True)
    target=BEST_DIR/'champion.pt'
    temp=BEST_DIR/'champion.pt.tmp'
    shutil.copy2(path,temp)
    os.replace(temp,target)
    return target


def current_profile(s):
    # Single policy lineage through 10,000 training iterations. No early Arena
    # competition. After this we diversify deliberately based on measurements.
    if s['total_updates'] < STAGE_A_UPDATES:
        return 'gait'
    ev=s.get('best_evaluation') or {}
    if ev.get('forward_progress',0.0) >= 0.35 and ev.get('survival',0) >= 0.65:
        return 'generalize'
    return ('gait_more_progress','gait_explore','gait')[s['trials']%3]


def create_active(s, block_iterations:int):
    profile=current_profile(s)
    baseline=s['total_updates']<STAGE_A_UPDATES
    # A new exploratory candidate may start from scratch only after multiple
    # completed, measured unsuccessful experiments. Never reset early.
    random_restart = (not baseline and s['trials']>0 and s['trials']%5==4 and
                      (s.get('best_evaluation') or {}).get('forward_progress',0.0)<.15)
    parent=None if (baseline and s['total_updates']==0) or random_restart else (
        s.get('best_checkpoint') if not baseline and profile=='generalize' and s.get('best_checkpoint')
        else s.get('current_checkpoint'))
    if parent and not Path(parent).is_file():
        raise FileNotFoundError('Training parent missing; refusing random restart: '+parent)
    parent_idx=checkpoint_index(parent)
    if parent and parent_idx is None:
        raise ValueError('Parent not a model_*.pt checkpoint: '+str(parent))
    block=block_iterations if baseline else max(block_iterations,4000)
    if random_restart:
        block=max(block,6000)  # Fresh-seed attempts need more than 2k to discover gait.
    if baseline:
        block=min(block,STAGE_A_UPDATES-s['total_updates'])
    # Pinned RSL-RL's final filename is parent_index + updates - 1.
    target_idx=(parent_idx+block-1) if parent_idx is not None else block-1
    name=f'c{s["trials"]+1:04d}-{profile}-{stamp()}'
    active={'id':name,'profile':profile,'seed':SEED+s['trials']*997,
      'parent':parent,'target':target_idx,'block':block,
      'attempts':[],'created':iso(),'phase':'training',
      'random_restart':random_restart,'environments':s['environments']}
    s['active']=active
    write_state(s)
    return active


def run_subprocess(cmd:list[str], logfile:Path, cwd:Path, print_every:int=100, hang_seconds:int=1500):
    """Stream log without hiding tracebacks. Detect long hangs, respond to SIGINT."""
    logfile.parent.mkdir(parents=True,exist_ok=True)
    say('Command:', ' '.join(cmd[-16:]))
    say('Full log:',str(logfile))
    p=subprocess.Popen(cmd,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        start_new_session=True,bufsize=0)
    assert p.stdout is not None
    buf=b'';last_output=time.monotonic(); last_print_iter=-1
    with logfile.open('ab') as f:
        try:
            while True:
                ready,_,_=select.select([p.stdout],[],[],1.5)
                if ready:
                    chunk=os.read(p.stdout.fileno(),65536)
                    if chunk:
                        last_output=time.monotonic()
                        f.write(chunk);f.flush()
                        buf+=chunk
                        while b'\n' in buf:
                            line,buf=buf.split(b'\n',1)
                            line=line.decode('utf-8','replace')
                            match=re.search(r'Learning iteration\s+(\d+)/(\d+)',line)
                            if match:
                                n=int(match.group(1))
                                if n==0 or n//print_every>last_print_iter//print_every:
                                    say(f'Iteration {n}/{match.group(2)}')
                                    last_print_iter=n
                            elif ('Traceback' in line or 'Error:' in line or 'out of memory' in line.lower()):
                                say(line[:250])
                    elif p.poll() is not None:
                        break
                if p.poll() is not None and not ready:
                    break
                if time.monotonic()-last_output > hang_seconds:
                    say(f'No worker output for {hang_seconds}s. Interrupting hung worker.')
                    os.killpg(p.pid,signal.SIGINT)
                    try:p.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(p.pid,signal.SIGKILL)
                        p.wait()
                    return 124
        except KeyboardInterrupt:
            say('Interrupt received; preserving checkpoints.')
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGINT)
                try:p.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGKILL)
                    p.wait()
            return 130
        finally:
            if buf:
                f.write(buf);f.flush()
    return p.wait()


def log_tail(path:Path, n:int=40):
    try:
        return '\n'.join(path.read_text(errors='replace').splitlines()[-n:])
    except OSError:
        return '(log unavailable)'


def train_active(s:dict, active:dict, block_iterations:int):
    attempts=0
    envs=active['environments']
    while True:
        ck=active_checkpoint(active)
        idx=checkpoint_index(ck)
        if idx is not None and idx >= active['target']-1:
            if idx<active['target']:
                say('Using near-target final checkpoint:',ck.name,'(confirmed complete/near-complete)')
            else:
                say('Recovered completed training checkpoint:',ck.name)
            return ck
        parent=ck or (Path(active['parent']) if active['parent'] else None)
        if ck is not None:
            remaining=active['target']-idx+1
        elif parent:
            remaining=active['target']-checkpoint_index(parent)+1
        else:
            remaining=active['target']+1
        if remaining<=0:
            return ck
        attempts+=1
        if attempts>5:
            raise RuntimeError('Five training attempts exhausted; last checkpoint retained')
        tag=f'{active["id"]}-a{len(active["attempts"])+1:02d}'
        active['attempts'].append({'tag':tag,'started':iso(),'parent':str(parent) if parent else None,
                                    'updates':remaining,'envs':envs})
        write_state(s)
        cmd=[str(REPO/'.venv/bin/python'),'-u',str(Path(__file__).resolve()),'worker-train',
           '--parent',str(parent) if parent else '', '--tag',tag,
           '--updates',str(remaining),'--envs',str(envs),'--seed',str(active['seed']+attempts-1),
           '--save-every',str(max(50,min(int(s.get('save_every',250)),remaining))),
           '--profile',active['profile']]
        log=REPORTS/'train'/f'{tag}.log'
        rc=run_subprocess(cmd,log,REPO)
        attempt=active['attempts'][-1]
        attempt['exit_code']=rc
        attempt['finished']=iso()
        write_state(s)
        ck_after=active_checkpoint(active)
        if rc==0 and ck_after and checkpoint_index(ck_after)>=active['target']-1:
            say('Training block complete:',ck_after)
            return ck_after
        if rc==130:
            raise KeyboardInterrupt()
        # preserve progress on all failures; resume from latest model in next attempt
        tail=log_tail(log).lower()
        suspected_memory=any(word in tail for word in ('out of memory','cuda error: out of memory',
            'cuda out of memory','std::bad_alloc','killed process','memoryerror'))
        # A GPU/WSL child may die without a traceback (SIGTERM/SIGKILL). After two
        # identical unexplained terminations, cautiously back off once; do not
        # infer this was definitely memory related.
        unexplained_kill=(rc in (-9,-15,9,15,137,143) and attempts>=2 and
                          'traceback' not in tail)
        if suspected_memory or unexplained_kill:
            if unexplained_kill:
                say('Suspected host/WSL process termination (not confirmed OOM); testing lower concurrency.')
            lower=max(2048,int(envs*.75)//256*256)
            if lower<envs:
                say(f'Possible memory limit; reducing environments {envs}->{lower}')
                envs=lower
                active['environments']=envs
                write_state(s)
            else:
                say('At minimum environments, cannot reduce further.')
        else:
            say('Trainer exited',rc,'without expected checkpoint; retrying from most recent saved model.')
            say(log_tail(log,12))
        time.sleep(3)


def worker_train(args):
    import mjlab.tasks  # noqa: F401
    from mjlab.scripts.train import TrainConfig,launch_training
    from mjlab.managers import RewardTermCfg
    cfg=TrainConfig.from_task(TASK)
    cfg.env.scene.num_envs=args.envs
    cfg.agent.max_iterations=args.updates
    cfg.agent.save_interval=args.save_every
    cfg.agent.run_name=args.tag
    cfg.agent.seed=args.seed
    profile=PROFILES[args.profile]
    cfg.agent.algorithm.entropy_coef=profile['entropy']
    cfg.agent.algorithm.learning_rate=profile['lr']
    if args.profile!='generalize':
        # Keep 61->14 observation/action architecture unchanged. We reduce
        # competing posture/head rewards and encourage actual forward velocity.
        cfg.env.events.pop('push_robot',None)
        for key in ('randomize_com','randomize_head_com','randomize_mass_inertia'):
            cfg.env.events.pop(key,None)
        cfg.env.curriculum.pop('standing_envs',None)
        cfg.env.curriculum.pop('head_pose_range',None)
        cfg.env.curriculum.pop('head_pose_bias_weight',None)
        cfg.env.curriculum.pop('action_rate_weight',None)
        cfg.env.curriculum.pop('com_range',None)
        cfg.env.curriculum.pop('head_com_range',None)
        cfg.env.commands['twist'].ranges.lin_vel_x=(0.08,0.30)
        cfg.env.commands['twist'].ranges.lin_vel_y=(-0.02,0.02)
        cfg.env.commands['twist'].ranges.ang_vel_z=(-0.20,0.20)
        cfg.env.commands['twist'].rel_standing_envs=0.03
        cfg.env.commands['twist'].rel_turn_in_place_envs=0.0
        cfg.env.commands['twist'].rel_backward_envs=0.0
        cfg.env.commands['twist'].rel_forward_envs=0.15
        cfg.env.commands['head_pose'].ranges=((0.0,0.0),)*4
        cfg.env.rewards['head_pose_bias'].weight=0.0
        cfg.env.rewards['track_linear_velocity'].params['std']=0.17
        cfg.env.rewards['track_angular_velocity'].params['std']=0.50
    else:
        # Generalize only after a measurable gait exists, restoring full command
        # sampling and robustness while retaining a modest progress incentive.
        cfg.env.events.pop('push_robot',None)  # reintroduce via later experiments, not this first phase
        cfg.env.curriculum.pop('action_rate_weight',None)
    cfg.env.rewards['track_linear_velocity'].weight=profile['linear']
    cfg.env.rewards['track_angular_velocity'].weight=profile['angular']
    cfg.env.rewards['upright'].weight=profile['upright']
    cfg.env.rewards['pose'].weight=profile['pose']
    cfg.env.rewards['air_time'].weight=profile['air']
    cfg.env.rewards['head_pose_tracking'].weight=profile['head']
    cfg.env.rewards['foot_swing_height'].weight=profile['swing']
    cfg.env.rewards['action_rate_l2'].weight=profile['smooth']
    cfg.env.rewards['forward_progress'] = RewardTermCfg(func=forward_progress_reward,
             weight=profile['progress'],params={'command_name':'twist'})
    if args.parent:
        src=Path(args.parent)
        if not src.is_file():
            raise FileNotFoundError(f'Parent missing: {src}')
        cfg.agent.resume=True
        cfg.agent.load_run='^'+re.escape(src.parent.name)+'$'
        cfg.agent.load_checkpoint='^'+re.escape(src.name)+'$'
    else:
        cfg.agent.resume=False
    say(f'START training parent={args.parent or "RANDOM"} profile={args.profile} envs={args.envs} updates={args.updates} tag={args.tag}')
    launch_training(TASK,cfg)
    return 0


def forward_progress_reward(env,command_name:str):
    """Signed motion in requested direction; zero benefit for stepping in place.

    Explicitly uses robot *body-frame* forward velocity, not absolute speed,
    to avoid the tap-dance/sideways reward shortcut seen in public diagnostics.
    """
    import torch
    cmd=env.command_manager.get_command(command_name)[:,0]
    v=env.scene['robot'].data.root_link_lin_vel_b[:,0]
    active=(cmd.abs()>0.05)
    toward=torch.sign(cmd)*v
    return torch.where(active,torch.clamp(toward/cmd.abs().clamp(min=.08),min=-1.,max=1.2),torch.zeros_like(v))


def worker_evaluate(args):
    """Holdout simulator: no torch.inference_mode(), no pushes, fixed commands.

    Training and evaluation run in separate processes; all env mutations happen
    within torch.no_grad() (fixes previous inference-tensor in-place crash).
    """
    import torch
    import mjlab.tasks  # noqa: F401
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import MjlabOnPolicyRunner,RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_env_cfg,load_rl_cfg,load_runner_cls
    if torch.is_inference_mode_enabled():
        raise RuntimeError('Never run environment evaluation under torch.inference_mode')
    device=args.device
    if device=='cuda:0' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable for evaluation')
    env_cfg=load_env_cfg(TASK,play=False)
    agent_cfg=load_rl_cfg(TASK)
    env_cfg.scene.num_envs=args.eval_envs
    env_cfg.seed=91007
    env_cfg.episode_length_s=max(14.0,args.seconds+2.0)
    env_cfg.curriculum={}
    env_cfg.events.pop('push_robot',None)
    env_cfg.auto_reset=True
    with torch.no_grad():
        env=ManagerBasedRlEnv(cfg=env_cfg,device=device)
        wrapped=RslRlVecEnvWrapper(env,clip_actions=agent_cfg.clip_actions)
        try:
            cls=load_runner_cls(TASK) or MjlabOnPolicyRunner
            runner=cls(wrapped,asdict(agent_cfg),device=device)
            runner.load(args.checkpoint,load_cfg={'actor':True},strict=True,map_location=device)
            policy=runner.get_inference_policy(device=device)
            robot=env.scene['robot']
            twist=env.command_manager.get_term('twist')
            nsteps=math.ceil(args.seconds/env.step_dt)
            records=[]
            for scenario, cmd3 in SCENARIOS.items():
                command=torch.tensor(cmd3,device=device,dtype=torch.float32)
                for j in range(args.seeds):
                    seed=91007+args.seed_offset+j*101
                    env.seed(seed)
                    torch.manual_seed(seed)
                    wrapped.reset()
                    def force_cmd():
                        twist.is_heading_env.fill_(False)
                        twist.is_world_env.fill_(False)
                        twist.is_forward_env.fill_(False)
                        twist.is_standing_env.fill_(scenario=='stand')
                        twist.time_left.fill_(1e6)
                        twist.vel_command_b[:]=command
                        twist.vel_command_w[:]=command
                    force_cmd()
                    first_pos=robot.data.root_link_pos_w[:,:2].detach().clone()
                    quat=robot.data.root_link_quat_w
                    theta=torch.atan2(2*(quat[:,0]*quat[:,3]+quat[:,1]*quat[:,2]),1-2*(quat[:,2]**2+quat[:,3]**2))
                    forward=torch.stack([torch.cos(theta),torch.sin(theta)],dim=1)
                    sideways=torch.stack([-torch.sin(theta),torch.cos(theta)],dim=1)
                    last_pos=first_pos.clone()
                    yaw=torch.zeros(args.eval_envs,device=device)
                    alive=torch.ones(args.eval_envs,dtype=torch.bool,device=device)
                    survived=torch.zeros(args.eval_envs,device=device)
                    error_sum=torch.zeros([],device=device)
                    yawerr_sum=torch.zeros([],device=device)
                    num_samples=0
                    for step in range(nsteps):
                        force_cmd()
                        actions=policy(wrapped.get_observations())
                        _,_,done,_=wrapped.step(actions)
                        done=done.bool()
                        ok=alive & ~done
                        survived[alive]+=1
                        if bool(ok.any().item()):
                            actual_xy=robot.data.root_link_lin_vel_b[:,:2]
                            actual_yaw=robot.data.root_link_ang_vel_b[:,2]
                            error_sum+=torch.linalg.norm(actual_xy[ok]-command[:2],dim=1).sum()
                            yawerr_sum+=(actual_yaw[ok]-command[2]).abs().sum()
                            num_samples+=int(ok.sum().item())
                            yaw[ok]+=actual_yaw[ok]*env.step_dt
                            last_pos[ok]=robot.data.root_link_pos_w[ok,:2]
                        alive=ok
                        if not bool(alive.any().item()):
                            break
                    delta=last_pos-first_pos
                    long=(delta*forward).sum(dim=1)
                    lat=(delta*sideways).sum(dim=1).abs()
                    desired=abs(cmd3[0]*args.seconds) if scenario in ('forward','reverse') else abs(cmd3[2]*args.seconds)
                    if scenario in ('forward','reverse'):
                        sign=1 if cmd3[0]>0 else -1
                        progress=float((long*sign).mean().item())/max(.001,desired)
                    elif scenario.endswith('turn'):
                        sign=1 if cmd3[2]>0 else -1
                        progress=float((yaw*sign).mean().item())/max(.001,desired)
                    else:progress=0.0
                    records.append(dict(scenario=scenario,seed=seed,progress_ratio=round(progress,6),
                       distance_m=round(float(long.mean().item()),6),lateral_m=round(float(lat.mean().item()),6),
                       survival_ratio=round(float(survived.mean().item())/nsteps,6),
                       full_survival=round(float(alive.float().mean().item()),6),
                       xy_error=round(float(error_sum.item())/max(1,num_samples),6),
                       yaw_error=round(float(yawerr_sum.item())/max(1,num_samples),6)))
            result=summarize_evaluation(records)
            result.update(dict(checkpoint=args.checkpoint,created=iso(),device=device,
                seeds=args.seeds,eval_envs=args.eval_envs,seconds=args.seconds,
                seed_offset=args.seed_offset,scenarios=records,version=VERSION))
            atomic_json(Path(args.output),result)
            say('EVAL forward=%.3f survival=%.3f yaw=%.3f score=%.3f'%(
                result['forward_progress'],result['survival'],result['yaw_progress'],result['score']))
        finally:
            wrapped.close()
    return 0


def summarize_evaluation(records:list[dict]):
    from statistics import mean
    g={k:[r for r in records if r['scenario']==k] for k in SCENARIOS}
    if any(not v for v in g.values()):
        raise ValueError('Missing evaluation scenarios')
    clip=lambda x:max(0.0,min(1.0,x))
    mean_key=lambda k,name:mean(float(x[name]) for x in g[k])
    all_survival=mean(float(r['survival_ratio']) for r in records)
    fwd=clip(mean_key('forward','progress_ratio'))
    rev=clip(mean_key('reverse','progress_ratio'))
    yaw=mean(clip(mean_key(x,'progress_ratio')) for x in ('left-turn','right-turn'))
    stand=math.exp(-5*(abs(mean_key('stand','distance_m'))+mean_key('stand','lateral_m')))
    lateral=mean_key('forward','lateral_m')
    score=100*(0.64*fwd+0.15*all_survival+0.08*rev+0.08*yaw+0.05*stand)-8*min(1,lateral)
    return dict(score=round(score,5),forward_progress=round(fwd,5),reverse_progress=round(rev,5),
                yaw_progress=round(yaw,5),survival=round(all_survival,5),stand_still=round(stand,5),
                forward_lateral_m=round(lateral,5))


def significant_improvement(candidate:dict,incumbent:dict|None):
    if not candidate or not math.isfinite(candidate.get('score',float('nan'))):return False
    if incumbent is None:return True
    if incumbent.get('forward_progress',0)<0.15:
        return candidate['forward_progress'] >= incumbent['forward_progress']+0.03 and candidate['survival']>=.40
    if candidate['survival'] < incumbent['survival']-.10:return False
    return (candidate['forward_progress']>=incumbent['forward_progress']-.03 and
            candidate['score']>=incumbent['score']+1.0)


def evaluate_checkpoint(s:dict,ck:Path,eval_envs:int=2,eval_seeds:int=2,seconds:float=10.0):
    REPORTS.mkdir(parents=True,exist_ok=True)
    out=REPORTS/'eval'/f'{ck.parent.name}__{ck.stem}__{VERSION}.json'
    if out.is_file():
        prev=read_json(out)
        if prev and prev.get('version')==VERSION:
            return prev
    for device in ('cpu','cuda:0'):
        cmd=[str(REPO/'.venv/bin/python'),'-u',str(Path(__file__).resolve()),'worker-eval',
             '--checkpoint',str(ck),'--output',str(out),'--device',device,
             '--eval-envs',str(eval_envs),'--seeds',str(eval_seeds),'--seconds',str(seconds),
             '--seed-offset','5000']
        log=out.with_suffix('.log')
        rc=run_subprocess(cmd,log,REPO,hang_seconds=900)
        if rc==0 and out.exists():
            return read_json(out)
        if rc==130: raise KeyboardInterrupt()
        say(f'Evaluation failed on {device} (exit={rc}); details in {log}.')
        say(log_tail(log,9))
    return None


def export_best():
    best=BEST_DIR/'champion.pt'
    if not best.exists():return
    output=BEST_DIR/'champion_walk.onnx'
    cmd=[str(REPO/'.venv/bin/python'),str(REPO/'scripts/export.py'),TASK,
        '--checkpoint-file',str(best),'--onnx-file',str(output),'--device','cpu',
        '--num-envs','1']
    try:
        result=subprocess.run(cmd,cwd=str(REPO),capture_output=True,text=True,timeout=600)
        if result.returncode:
            say('ONNX export warning:',(result.stderr or result.stdout)[-600:])
        elif output.is_file():say('ONNX export:',output)
    except (OSError,subprocess.TimeoutExpired) as exc:
        say('ONNX export warning (training unaffected):',exc)


def maybe_prune_checkpoints(dirpath:Path,retain:int=3):
    """Automatic local disk retention for completed run directories only.

    All candidates and best policy independently tracked. Current/pending runs
    are not pruned; old intermediate checkpoints (except latest 3) may be removed.
    """
    if not dirpath.is_dir():return
    found=[]
    for p in dirpath.glob('model_*.pt'):
        idx=checkpoint_index(p)
        if idx is not None:found.append((idx,p))
    for _,p in sorted(found)[:-retain]:
        try:p.unlink()
        except OSError:pass


def append_board(active:dict,ck:Path,ev:dict|None,decision:str):
    file=REPORTS/'leaderboard.csv'
    file.parent.mkdir(parents=True,exist_ok=True)
    cols=['time','id','profile','checkpoint','score','forward_progress','reverse_progress',
          'yaw_progress','survival','decision']
    exists=file.exists()
    with file.open('a',encoding='utf-8',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=cols)
        if not exists:w.writeheader()
        data={**(ev or {}),**active,'time':iso(),'id':active['id'],
              'checkpoint':str(ck),'decision':decision}
        w.writerow({k:data.get(k,'') for k in cols})


def complete_active(s:dict,active:dict,ck:Path,ev:dict|None):
    prev_best=s.get('best_evaluation')
    selected=significant_improvement(ev,prev_best) if ev else False
    if selected:
        bestpath=_copy_best_model(ck)
        s['best_checkpoint']=str(ck)
        s['best_id']=active['id']
        s['best_evaluation']=ev
        say('NEW CHAMPION forward=%.3f score=%.2f (%s)'%(
            ev['forward_progress'],ev['score'],ck.name))
        if ev.get('forward_progress',0)>=.35 and ev.get('survival',0)>=.6:
            export_best()
        else:
            say('Champion is PROVISIONAL (walking threshold not met); no deployable walking ONNX exported.')
    s['evaluation_failures'] = 0 if ev else s.get('evaluation_failures',0)+1
    if ev:
        s['evaluations']+=1
    s['total_updates']+=active['block']
    s['trials']+=1
    # First 10k is ONE lineage: even if score dips, continue from current.
    # Beyond that, only promote successful branches to the working lineage.
    if s['total_updates'] <= STAGE_A_UPDATES:
        s['current_checkpoint']=str(ck)
    elif selected:
        s['current_checkpoint']=str(ck)
    elif (s.get('best_evaluation') or {}).get('forward_progress',0.0)<.35:
        # Still searching for the first walking gait: do NOT regress to the
        # earliest high-survival nonwalking champion after every trial.
        if not active.get('random_restart'):
            s['current_checkpoint']=str(ck)
        # A failed deliberate fresh-seed experiment must not destroy the prior lineage.
    else:
        s['current_checkpoint']=s.get('best_checkpoint') or str(ck)
    s['stage']='gait-discovery' if s['total_updates']<STAGE_A_UPDATES else (
        'skill-expansion' if (s.get('best_evaluation') or {}).get('forward_progress',0)>=.35 else 'gait-search')
    decision='PROMOTED' if selected else ('EVAL_FAILED' if ev is None else 'RETAINED')
    append_board(active,ck,ev,decision)
    s['history']=(s.get('history') or [])[-200:]+[dict(id=active['id'],checkpoint=str(ck),
      profile=active['profile'],decision=decision,forward_progress=(ev or {}).get('forward_progress'),at=iso())]
    s['active']=None
    s['last_error']=None if ev else 'Evaluation failed; candidate retained; controller continued from latest checkpoint.'
    write_state(s)
    if ev is not None:
        for attempt in active['attempts']:
            run=current_dir_for_tag(attempt['tag'])
            if run and str(ck.parent)!=str(run):
                maybe_prune_checkpoints(run)
        maybe_prune_checkpoints(ck.parent)



def preflight(s:dict):
    """Prove TRAIN + HOLDOUT-EVALUATION work before hours of GPU training.

    This 8-update random test is NOT part of the useful walking policy.
    """
    if s.get('preflight_version') == VERSION:
        return
    say('Preflight: validating custom reward, GPU simulation, PPO, checkpoint and evaluator.')
    tag='preflight-8-'+s['campaign']
    previous=current_dir_for_tag(tag)
    checkpoint=latest_checkpoint(previous)
    if not checkpoint:
        cmd=[str(REPO/'.venv/bin/python'),'-u',str(Path(__file__).resolve()),'worker-train',
             '--parent','','--tag',tag,'--updates','8','--envs','64',
             '--seed','8817','--save-every','8','--profile','gait']
        log=REPORTS/'preflight'/(tag+'.log')
        rc=run_subprocess(cmd,log,REPO,hang_seconds=1200)
        checkpoint=latest_checkpoint(current_dir_for_tag(tag))
        if rc==130: raise KeyboardInterrupt()
        if rc!=0 or not checkpoint:
            raise RuntimeError('Preflight train failed. See '+str(log)+'\n'+log_tail(log,25))
    out=REPORTS/'preflight'/(tag+'-eval.json')
    if not out.exists():
        for device in ('cpu','cuda:0'):
            log=REPORTS/'preflight'/(tag+'-eval-'+device.replace(':','')+'.log')
            cmd=[str(REPO/'.venv/bin/python'),'-u',str(Path(__file__).resolve()),'worker-eval',
                 '--checkpoint',str(checkpoint),'--output',str(out),'--device',device,
                 '--eval-envs','1','--seeds','1','--seconds','2','--seed-offset','14000']
            rc=run_subprocess(cmd,log,REPO,hang_seconds=900)
            if rc==130: raise KeyboardInterrupt()
            if rc==0 and out.exists():break
            say('Preflight evaluator failure on '+device+': '+log_tail(log,10))
    if not out.exists():
        raise RuntimeError('Both evaluator modes failed during preflight. Do NOT waste 2 hours training. Inspect '+str(REPORTS/'preflight'))
    s['preflight_done']=True
    s['preflight_version']=VERSION
    write_state(s)
    say('Preflight passed. Starting genuine training from RANDOM WEIGHTS (not preflight).')


def run_autopilot(args):
    if not (REPO/'.venv/bin/python').is_file():
        raise RuntimeError('XGO-Duck environment missing. Run setup first: '+str(REPO))
    with exclusive_lock():
        PID_PATH.write_text(str(os.getpid())+'\n')
        try:
            s=get_state()
            s['environments']=args.environments
            s['save_every']=args.save_every
            s['status']='running'
            write_state(s)
            preflight(s)
            say(f'Gait-First Autopilot | envs={args.environments} | block={args.block_iterations} | no cycle limit')
            say('Persistent state:',STATE_PATH)
            say('First 10,000 PPO iterations follow ONE lineage; not five premature contenders.')
            say('Forward displacement is the primary evaluation metric. No convergence guarantee.')
            while True:
                if free_disk_gb(BASE)<MIN_FREE_GB:
                    raise RuntimeError(f'Less than {MIN_FREE_GB} GiB available; stopping safely to avoid disk exhaustion.')
                active=s.get('active') or create_active(s,args.block_iterations)
                ck=train_active(s,active,args.block_iterations)
                active['phase']='evaluating'
                active['trained_checkpoint']=str(ck)
                write_state(s)
                ev=evaluate_checkpoint(s,ck,eval_envs=args.eval_envs,eval_seeds=args.eval_seeds,
                                       seconds=args.eval_seconds)
                complete_active(s,active,ck,ev)
                if s.get('evaluation_failures',0)>=3:
                    raise RuntimeError('Three consecutive evaluations failed. Checkpoints preserved; repair evaluation before continuing.')
                if not args.forever and s['total_updates']>=args.max_updates:
                    say('Bounded run completed; winner: ',s.get('best_checkpoint'))
                    s['status']='completed'
                    write_state(s)
                    break
        except KeyboardInterrupt:
            say('Stopped by user; latest checkpoint retained. Re-run to resume.')
            s=read_json(STATE_PATH) or {}
            s['status']='interrupted'
            write_state(s)
            return 130
        except Exception as exc:
            s=read_json(STATE_PATH) or {}
            s['status']='error';s['last_error']=str(exc)
            write_state(s)
            raise
        finally:
            if PID_PATH.exists():
                try:
                    if PID_PATH.read_text().strip()==str(os.getpid()):PID_PATH.unlink()
                except OSError:pass
    return 0


def cmd_status(args):
    s=read_json(STATE_PATH)
    say('WSL project:',REPO)
    say('Controller PID:',known_controller_pid() or 'not running')
    if not s:
        say('No campaign initialized yet. Start training from the menu.')
        return 0
    for key in ('version','created','status','stage','total_updates','trials','evaluations',
                'current_checkpoint','best_checkpoint','best_id','last_error'):
        say(f'{key}:',s.get(key))
    if s.get('best_evaluation'):
        v=s['best_evaluation']
        say('BEST forward',v.get('forward_progress'),'survival',v.get('survival'),'score',v.get('score'))
    if s.get('active'):
        a=s['active']
        say('ACTIVE:',a.get('id'),'profile=',a.get('profile'),'target=',a.get('target'),'phase=',a.get('phase'))
        cp=active_checkpoint(a)
        say('ACTIVE LATEST:',cp or '(none yet)')
    if (REPORTS/'leaderboard.csv').exists():
        say('Leaderboard:',REPORTS/'leaderboard.csv')
    return 0


def cmd_active(args):
    pid=known_controller_pid()
    if pid:
        say('Training is already active with PID',pid)
        return 0
    return 2


def cmd_stop(args):
    pid=known_controller_pid()
    if not pid:
        say('No active controller to stop.')
        return 0
    os.kill(pid,signal.SIGINT)
    say('Sent graceful interrupt to controller PID',pid)
    return 0


def existing_viewer_or_worker():
    """Return known active project processes besides this controller.

    Never match arbitrary shells or strings; match the executable and our exact
    paths. Read-only status process calls must not block deletion.
    """
    detected=[]
    proc=Path('/proc')
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name)==os.getpid():continue
        try:
            args=(entry/'cmdline').read_bytes().decode('utf-8','replace').split('\0')
        except OSError:continue
        if not args or not args[0]:continue
        text=' '.join(args)
        role=None
        if str(Path(__file__).resolve()) in args:
            for token in ('worker-train','worker-eval','viewer','tensorboard','run'):
                if token in args:
                    role=token;break
        elif str(REPO) in text and any('/bin/play' in x or '/bin/train' in x for x in args):
            role='upstream-train-or-play'
        if role:detected.append((int(entry.name),role))
    return detected


def cmd_reset(args):
    if args.confirm!='DELETE':
        raise RuntimeError('Permanent reset requires one explicit DELETE confirmation from launcher.')
    with exclusive_lock():
        if known_controller_pid():
            raise RuntimeError('Training still running. Stop from menu first.')
        others=existing_viewer_or_worker()
        if others:
            raise RuntimeError('Viewer/trainer still using project files: '+str(others)+'; close them before reset.')
        # The only path this operation can remove is the exact app-owned directory.
        canonical=HOME/'xgoduck_oneclick'
        if BASE!=canonical or BASE.is_symlink():
            raise RuntimeError('Reset path validation failed; refusing deletion.')
        if BASE.exists():
            say('PERMANENT DELETE of',BASE)
            shutil.rmtree(BASE)
            say('Deleted app-owned repository, logs, checkpoints, policies, reports and state.')
        else:say('No app-owned installation/data exists.')
        # Legacy ~/xgoduck_rl is purposefully out of scope.
        say('Launcher package in Windows and any legacy ~/xgoduck_rl were not touched.')
    return 0


def open_browser(url):
    browser = shutil.which('cmd.exe')
    if browser:
        subprocess.Popen([browser, '/c', 'start', '', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say('Open in Windows browser:', url)


def serve(cmd, name, port):
    """Keep one owned service, retain its log, and wait for actual HTTP readiness."""
    import urllib.request
    import socket
    lock = HOME / ('.xgoduck_' + name + '.lock')
    url = f'http://localhost:{port}'
    with lock.open('a+') as fd:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            say(name, 'already starting/running.', url)
            open_browser(url)
            return 0
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port)) == 0:
                raise RuntimeError(f'Port {port} is occupied by another process. Close it before starting {name}.')
        log = REPORTS / 'services' / (name + '-' + stamp() + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        say(name, 'STARTING:', url, '(not ready until READY appears)')
        say('Service log:', log)
        with log.open('wb') as output:
            child = subprocess.Popen(cmd, cwd=str(BASE), stdout=output,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            try:
                deadline = time.monotonic() + 600
                ready = False
                last_notice = 0.0
                while child.poll() is None:
                    if not ready:
                        if time.monotonic()-last_notice >= 15:
                            say(name, 'initializing; waiting for HTTP:', url)
                            say(log_tail(log,3))
                            last_notice=time.monotonic()
                        try:
                            with urllib.request.urlopen(url,timeout=2) as response:
                                ready = response.status == 200
                        except Exception:
                            pass
                        if ready:
                            say(name, 'READY:', url)
                            open_browser(url)
                        elif time.monotonic() > deadline:
                            raise RuntimeError(f'{name} did not become ready within 10 minutes. Log: {log}')
                    time.sleep(1)
                if child.returncode:
                    raise RuntimeError(f'{name} exited {child.returncode}: '+log_tail(log,30))
                return 0
            finally:
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGTERM)
                    try: child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGKILL)
                        child.wait()


def viewer_checkpoint(latest):
    st=read_json(STATE_PATH,default={}) or {}
    current=st.get('current_checkpoint')
    active=st.get('active')
    cp=active_checkpoint(active) if active and latest else None
    if cp is None and latest and current and Path(current).is_file():
        cp=Path(current)
    if cp is None and (BEST_DIR/'champion.pt').is_file():
        cp=BEST_DIR/'champion.pt'
    return cp


def cmd_viewer(args):
    say('Viewer URL: http://localhost:8080. The page starts ONLY after a checkpoint is loaded.')
    started=time.monotonic()
    last_notice=0.0
    cp=viewer_checkpoint(args.latest)
    if cp is None and args.wait:
        say('Waiting for the first real training checkpoint. Preflight models are excluded.')
    while cp is None and time.monotonic()-started < args.wait:
        if time.monotonic()-started > 120 and not known_controller_pid():
            say('VIEWER UNAVAILABLE: training is not running and no checkpoint exists. Click Start training first.')
            return 0
        if time.monotonic()-last_notice>=15:
            say('VIEWER WAITING: no real checkpoint yet. http://localhost:8080 is not serving yet.')
            last_notice=time.monotonic()
        time.sleep(5)
        cp=viewer_checkpoint(args.latest)
    if cp is None:
        raise RuntimeError('No checkpoint available yet. Reopen Viewer after training saves a model.')
    # Copy a stable snapshot so pruning or later saves cannot invalidate the viewer.
    snapshot=BASE/'viewer'/f'snapshot-{os.getpid()}.pt'
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(cp,snapshot)
    say('Viewing snapshot:', cp, '(reopen viewer to load a newer model)')
    cmd=[str(REPO/'.venv/bin/play'),TASK,'--checkpoint-file',str(snapshot),
         '--num-envs','1','--device',args.device,'--viewer','viser']
    return serve(cmd,'viewer',8080)


def cmd_tensorboard(args):
    say('TensorBoard URL: http://localhost:6007 (not port 6006). Preparing service...')
    BASE.mkdir(parents=True,exist_ok=True)
    tb=REPO/'.venv/bin/tensorboard'
    if tb.exists():
        cmd=[str(tb)]
    else:
        uvx=HOME/'.local/bin/uvx'
        if not uvx.exists():
            say('Installing TensorBoard prerequisites automatically; full training setup is not required.')
            rc=subprocess.call(['bash',str(Path(__file__).with_name('bootstrap.sh')),'--tensorboard-only'])
            if rc: raise RuntimeError(f'TensorBoard preparation failed (exit {rc}). Export diagnostics for details.')
        cmd=[str(uvx),'--python','3.12','--with','setuptools==80.9.0','--from','tensorboard==2.20.0','tensorboard']
    cmd+=['--logdir',str(RUN_ROOT),'--host','127.0.0.1','--port','6007']
    return serve(cmd,'tensorboard',6007)


def cmd_log(args):
    candidates=[]
    for folder in (REPORTS/'train',REPORTS/'eval',REPORTS/'preflight',REPORTS/'services',REPORTS/'setup'):
        if folder.exists():candidates+=list(folder.glob('*.log'))
    if not candidates:
        say('No training or evaluation logs yet.')
        return 0
    p=max(candidates,key=lambda x:x.stat().st_mtime)
    say('Latest:',p)
    print(log_tail(p,args.lines))
    return 0


def cmd_benchmark(args):
    s=get_state()
    p=s.get('current_checkpoint') or s.get('best_checkpoint')
    if not p:
        say('No checkpoint ready for evaluation.')
        return 2
    ev=evaluate_checkpoint(s,Path(p),eval_envs=args.eval_envs,eval_seeds=args.eval_seeds,
                           seconds=args.eval_seconds)
    if ev is None:return 1
    print(json.dumps(ev,indent=2))
    return 0


def cmd_diagnostics(args):
    """Bounded, local-only support report; no environment variables or model bytes."""
    import platform
    lines=['\n=== WSL diagnostics ===', 'Engine: '+VERSION, 'Time: '+iso(),
           'Platform: '+platform.platform(), 'Python: '+sys.version,
           'Project: '+str(BASE), 'Controller: '+str(known_controller_pid()),
           'TensorBoard: http://localhost:6007', 'Viewer: http://localhost:8080']
    try:
        lines+=['Free GiB: %.2f'%(shutil.disk_usage(HOME).free/1024**3)]
        lines+=['State:',json.dumps(read_json(STATE_PATH,{}),indent=2)]
    except Exception as exc: lines+=['State unavailable: '+str(exc)]
    gpu=shutil.which('nvidia-smi') or '/usr/lib/wsl/lib/nvidia-smi'
    for cmd in ([gpu,'--query-gpu=name,memory.total,driver_version','--format=csv'],
                ['git','-C',str(REPO),'rev-parse','HEAD']):
        try:
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
            lines+=['Command: '+' '.join(cmd), 'Exit: '+str(result.returncode),result.stdout,result.stderr]
        except Exception as exc:lines+=['Probe failed: '+str(exc)]
    candidates=[]
    for name in ('setup','preflight','train','eval','services'):
        folder=REPORTS/name
        if folder.exists():
            candidates+=sorted(folder.glob('*.log'),key=lambda p:p.stat().st_mtime,reverse=True)[:3]
    for log in candidates:
        try:
            # Read at most 96 KiB per log, even if a long training run produced gigabytes.
            with log.open('rb') as fd:
                fd.seek(max(0,log.stat().st_size-98304))
                tail=fd.read().decode('utf-8','replace')
            lines+=['\n=== '+str(log)+' (last 250 lines) ===','\n'.join(tail.splitlines()[-250:])]
        except OSError as exc:lines+=['Cannot read '+str(log)+': '+str(exc)]
    text='\n'.join(lines)+'\n'
    if args.output:
        output=Path(args.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('a',encoding='utf-8') as fd:fd.write(text)
        say('Diagnostics saved:',output)
    else:print(text)
    return 0


def cmd_unit(args):
    # These checks do not require CUDA/mjlab, only Python stdlib.
    assert checkpoint_index('model_1999.pt')==1999
    assert checkpoint_index('model_3998.pt')==3998
    assert checkpoint_index('bad.pt') is None
    r=[{'scenario':k,'progress_ratio':0.0,'survival_ratio':1.0,
         'distance_m':0.0,'lateral_m':0.0} for k in SCENARIOS]
    base=summarize_evaluation(r)
    assert base['forward_progress']==0
    assert significant_improvement(dict(score=3,forward_progress=0,survival=1),
                                   dict(score=90,forward_progress=0,survival=1)) is False
    assert significant_improvement(dict(score=10,forward_progress=0.2,survival=.9),
                                   dict(score=40,forward_progress=0,survival=1)) is True
    say('Self-test passed')
    return 0


def parser():
    p=argparse.ArgumentParser(description='XGO-Duck Gait-First Autopilot')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('run','worker-train','worker-eval','status','active','stop','reset','viewer','tensorboard','log','benchmark','unit','diagnostics'):
        s=sub.add_parser(name)
        if name=='run':
            s.add_argument('--environments',type=int,default=DEFAULT_ENVIRONMENTS)
            s.add_argument('--block-iterations',type=int,default=STAGE_A_BLOCK)
            s.add_argument('--save-every',type=int,default=250)
            s.add_argument('--eval-envs',type=int,default=2)
            s.add_argument('--eval-seeds',type=int,default=2)
            s.add_argument('--eval-seconds',type=float,default=10.)
            s.add_argument('--forever',action='store_true',default=False)
            s.add_argument('--max-updates',type=int,default=10000)
        if name=='worker-train':
            for flag,kw in (('--parent',dict(default='')),('--tag',dict(required=True)),
                ('--updates',dict(type=int,required=True)),('--envs',dict(type=int,required=True)),
                ('--seed',dict(type=int,required=True)),('--save-every',dict(type=int,required=True)),
                ('--profile',dict(choices=sorted(PROFILES),required=True))):
                s.add_argument(flag,**kw)
        if name=='worker-eval':
            s.add_argument('--checkpoint',required=True)
            s.add_argument('--output',required=True)
            s.add_argument('--device',choices=['cpu','cuda:0'],required=True)
            s.add_argument('--eval-envs',type=int,required=True)
            s.add_argument('--seeds',type=int,required=True)
            s.add_argument('--seconds',type=float,required=True)
            s.add_argument('--seed-offset',type=int,default=5000)
        if name=='diagnostics':s.add_argument('--output')
        if name=='reset':s.add_argument('--confirm',required=True)
        if name=='viewer':
            s.add_argument('--device',default='cpu',choices=['cpu','cuda:0'])
            s.add_argument('--latest',action='store_true')
            s.add_argument('--wait',type=float,default=0)
        if name in ('benchmark',):
            s.add_argument('--eval-envs',type=int,default=2)
            s.add_argument('--eval-seeds',type=int,default=2)
            s.add_argument('--eval-seconds',type=float,default=10.)
        if name=='log':s.add_argument('--lines',type=int,default=75)
    return p


def main():
    args=parser().parse_args()
    if args.command=='run':return run_autopilot(args)
    if args.command=='worker-train':return worker_train(args)
    if args.command=='worker-eval':return worker_evaluate(args)
    if args.command=='status':return cmd_status(args)
    if args.command=='active':return cmd_active(args)
    if args.command=='stop':return cmd_stop(args)
    if args.command=='reset':return cmd_reset(args)
    if args.command=='viewer':return cmd_viewer(args)
    if args.command=='tensorboard':return cmd_tensorboard(args)
    if args.command=='log':return cmd_log(args)
    if args.command=='benchmark':return cmd_benchmark(args)
    if args.command=='unit':return cmd_unit(args)
    if args.command=='diagnostics':return cmd_diagnostics(args)
    return 2

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        say('FATAL:',str(exc))
        traceback.print_exc()
        sys.exit(1)
