# Training audit 2.2.0

TRAINING-REVIEW.md supersedes earlier looping/generalization descriptions. Export is read-only and contains no checkpoint weights. Never automatically clear learning-stall guards or discard evidence. New candidates continue the working lineage separately from the best model. Generalization requires gait_ready, not aggregate survival.

# Desktop and diagnostics 2.1.0

START-XGODUCK.cmd opens XgoDuck.Desktop.ps1. XgoDuck.ps1 remains the worker/console entry point. Desktop labels must distinguish waiting from ready; do not claim a worker process is successful training. Diagnostics must survive missing WSL and must not collect environment secrets or model weights. TensorBoard may prepare itself before training setup. Setup must log from the beginning and report the current verification phase. Tests now include Linux service/installer integration and Windows fixture end-to-end launch tests.

# Launcher update 2.0.1

Workers MUST use plain -File invocation through scripts/windows-worker.ps1, not encoded or evaluated command text. Use process-scoped RemoteSigned. Do not add antivirus exclusions or manipulate pending quarantine. Run tests/test_windows_launcher.ps1 on Windows in CI. This supersedes earlier encoded-argument guidance.

# Current release notes (2.0.0)

The launcher was rebuilt: WSL maps paths using wslpath; workers hold their windows; native output is sent to Out-Host and exit codes stay numeric. Start launches TensorBoard and a waiting CPU viewer. README.md is authoritative for user-facing behavior. Training overrides MUST use cfg.env, not cfg.events/rewards/etc. Preflight is versioned. Bounded mode is the engine CLI default; Windows Start explicitly passes --forever. Three consecutive failed evaluations halt with checkpoints retained. GitHub Actions checks Windows PowerShell syntax. No CUDA/Windows execution was available during authoring.

The engineering intent below remains relevant; earlier implementation descriptions are superseded by these notes and current code.

# AGENTS.md — XGO-Duck Gait-First Autopilot Engineering Contract

## Primary mission

This repository is a standalone Windows-to-WSL2 control layer for XGO-Duck. The user's objective is to leave a single script running overnight and return to measurable improvements in the duck's ability to **walk**, rather than accumulate PPO iterations or reward points. The system must preserve progress across crashes; prevent repeating hours of compute due to evaluator errors; and report clearly when no progress occurs. **No algorithm may assert guaranteed eventual convergence.**

## The non-negotiable operator contract

- **One human entry point:** `XgoDuck.ps1` in the extracted ZIP. The command in `START-HERE.md` must remain valid.
- **One real confirmation** for irreversible reset. Case-insensitive exact `DELETE`; no archive and no other destructive implicit action.
- **Strict reset scope:** `~/xgoduck_oneclick`, never `~/xgoduck_rl`, never `C:\Users\...\duck` or other arbitrary paths.
- **Never delete models on startup**; ensure state exists, and refuse a new random start if orphaned checkpoints are present.
- **Never do a five-way, 2,000-iteration Arena competition before teaching the robot a gait.** First baseline is one 10,000-update continuing policy.
- **Always run a preflight that exercises both the training and evaluation code** before investing hours in training. A failed evaluator cannot trigger retraining from random weights.
- **No trained-policy promotion based on reward or survival alone**. Use measured displacement plus survival gates.
- **No hard-to-debug hidden failures.** Preserve full stdout/stderr logs of training subprocesses and display the error tail.
- **Serial GPU workloads by default.** Do not assume two 4,096-world workers are faster than one; benchmark before adding concurrency.
- **No unbounded error loop.** Forever means continued experiments while healthy, not infinite restarts on the same configuration error.
- **Do not assume a policy can control the real robot safely.** The training environment is simulation-only.

## Entry points and files

`XgoDuck.ps1` is the only file the user needs to run. It starts `scripts/bootstrap.sh` when necessary, then calls `scripts/xgoduck_engine.py` via `wsl.exe -d Ubuntu -- python3 /mnt/c/.../xgoduck_engine.py`. Direct WSL paths are computed from the script directory in PowerShell (not by nested `bash -lc` calls) to avoid backslash quoting failures.

`scripts/bootstrap.sh`: checks WSL GPU interface and prerequisites, installs `uv` if necessary, clones `LuwuDynamics/xgoduck_rl` and checks out known revision `725ed0c`, runs `uv sync --frozen`, verifies PyTorch CUDA. It must not modify a dirty upstream clone.

`scripts/xgoduck_engine.py`: standard-library orchestration under system Python, plus training and evaluation child commands under the upstream `.venv/bin/python`. Contains a fixed-command simulator evaluator, direct movement reward and persistent crash-safe checkpoint state. `README.md` documents the interface.

`tests/test_engine.py`: offline unit and recovery checks. New features require new tests without GPU or network access.

## Fixed upstream pin, upgrades and API

At initial release, upstream revision is `725ed0c` with `mjlab==1.3.0`, Warp 1.12 and 61 input / 14 output walking policy. Never silently switch the user to an untested upstream commit. Major upgrades must verify the training CLI, `TrainConfig.from_task`, local checkpoint loading, observation/action layout, YAML serialization and both device modes of the evaluator. Document the changed exact commit and provide a reversible migration path.

The controller does **not** patch upstream source files or vendor CUDA wheels. It creates an in-memory copy of `TrainConfig` during `worker-train`. The observation/action architecture remains compatible with the upstream runtime and ONNX exporter even while reward weights/command distributions change.

## State machine

App root: `~/xgoduck_oneclick/`. Source checkout: `~/xgoduck_oneclick/xgoduck_rl/`. State: `~/xgoduck_oneclick/state.json`. Reports: `~/xgoduck_oneclick/reports/`. Best: `~/xgoduck_oneclick/best/`. Project lock: `~/.xgoduck_oneclick.lock` (intentionally outside deleted app tree). Running PID: `~/.xgoduck_oneclick.pid`.

Pseudo-state:

```text
BOOTSTRAP + CUDA VERIFY
    -> ATOMIC STATE FILE
    -> PREFLIGHT (8 updates, then real holdout eval)
    -> 10K single-lineage gait discovery
        -> every 2K: checkpoint, evaluate, preserve best, continue same model
    -> IF forward progress >= gate and survival adequate
        -> generalization profile, keep best policy across trials
    -> ELSE
        -> longer staged reward/exploration trials and occasional fresh seeds
    -> evaluate/reject/promote/continue until user stops or unrecoverable error
```

A block is represented by `state.active`, containing parent checkpoint, target inclusive iteration index, profile, seed, attempted run tags and training phase. Save state **before** launching a worker. A restart scans **only the recorded attempt tags** to find latest checkpoint and calculates the remaining iterations. If an attempt already reached its target, skip training and execute evaluation. Never start random weights unless there is no parent and this block was intentionally designated fresh.

### Checkpoint arithmetic

The pinned RSL-RL runner labels the final model of N PPO updates `model_(N-1).pt` on a fresh start. From parent `model_P.pt`, an additional N updates produce a final model named `model_(P+N-1).pt`.

- Fresh 2,000 → `model_1999.pt`.
- From `model_1999.pt`, 2,000 updates → `model_3998.pt`.
- From `model_3998.pt`, another 2,000 → `model_5997.pt`.

The index is a **filename**, not a guaranteed unique number of new PPO optimizer updates across restarts. RSL-RL may repeat an index at resume boundaries. Do not reintroduce the old error that expected `model_3999.pt` after `model_1999.pt + 2000`. If a training job reports success but the latest checkpoint is at `target-1`, the current controller accepts it with a warning; this tolerates a one-step upstream indexing drift without discarding hours of work.

### Atomicity and crash recovery

`atomic_json` writes temporary JSON, flushes, calls `fsync` and atomically replaces `state.json`. `active.attempts` stores every run suffix. `latest_checkpoint` selects by numeric iteration index, not alphabetical model name. After interruption, the newest available attempt model becomes the parent; the controller does not jump to an unrelated later run.

`run_subprocess` captures full output under `reports/`, emits periodic iteration lines, supports Ctrl+C forwarding, and times out only after sustained silence. A nonzero training exit preserves checkpoint files, reduces environments **only on explicit memory indicators**, and stops after five retries.

When an evaluation fails, retry on a secondary device, preserve the trained checkpoint, label the result as not evaluated, and continue the current policy lineage. Never silently promote or declare success on evaluation failure.

## Training objectives and curricula

`gait`: the default discovery profile. Changes the command distribution toward 0.08–0.30 m/s forward, largely disables early turning and lateral motion, and reduces head/body/posture regularization; a signed progress reward encourages actual commanded forward body speed. Removes push events and some domain randomization in the early discovery phase. These overrides **do not** change the action or observation dimensions.

`gait_more_progress`: stronger signed progress/tracking; more conservative learning rate.

`gait_explore`: higher entropy and weak stride shaping; only used in controlled attempts after the initial 10,000 updates.

`generalize`: restores more of the original command distribution, lateral/backward/turning goals and posture reward once forward locomotion has already appeared. It must not be entered just because the policy can stand.

Always preserve the comparator's evaluation config and monitor whether task changes induce catastrophic forgetting. Reward changes are hypotheses. There is no evidence that a particular profile is guaranteed to solve the standing local optimum. Validate command-space compatibility before deployment.

## Direct-motion reward rationale

The public `pollen-robotics/microduck_rl#46` issue documented a policy that collected balance/airtime reward without net displacement. The wrapper adds a reward proportional to the signed body-frame velocity **toward the commanded direction**, rather than using absolute speed or raw foot action alone. Zero forward motion yields zero progress reward. Backward drift receives a negative value. Combined with a tighter tracking objective, this reduces—but does not mathematically eliminate—the incentive to stand still.

The reward is defined as a top-level function in the engine and used as an `RewardTermCfg(func=forward_progress_reward, ...)`. It must remain importable and YAML-serializable by the pinned mjlab training stack. Changes must pass preflight.

## Evaluation protocol

The evaluator uses a separate `.venv` process and `torch.no_grad()` across **every** simulator step. It must never surround environment stepping with `torch.inference_mode()`; this caused the user's earlier `RuntimeError: Inplace update to inference tensor outside InferenceMode is not allowed` at the end of two multi-hour runs. No-gait policies are not rewarded as though they walked.

For each checkpoint, evaluate on fixed seeds: stand, forward, reverse, left yaw, right yaw, 10 s each. Suppress pushes in the evaluator. `forward_progress = clipped(actual_forward_displacement / desired_forward_displacement)`. Also record lateral drift, survival ratio, and yaw progress. Score weights forward progress primarily (64%). The selection function additionally requires meaningful forward improvement or, once a gait exists, no significant forward/survival regressions. This is a practical engineering gate, not a statistically validated optimality criterion.

If changing reward weights across candidate phases, **never compare raw Episode_Reward curves as if their scale were invariant**. Similarly, `Metrics/twist/error_vel_xy` accumulates over episode life in mjlab 1.3.0 and grows with episode duration; use evaluation's per-step tracking error and measured net displacement instead.

## Failure history to prevent regression

1. Running `list-envs` with this older CLI emitted a nonzero exit equal to task count. Check the registry from Python instead.
2. Viewer launch under PowerShell malformed WSL distro argument. Use direct native arguments.
3. `--video` used without explicit Boolean and invalid CLI flags. Keep training headless by default.
4. CRLF broke embedded Bash heredocs. Package actual LF `.sh` source files.
5. `wslpath` received escaped Windows paths without backslashes. Avoid nested shell conversion; compute `/mnt/<drive>/...` in PowerShell.
6. `torch.inference_mode` broke the evaluator after hours. Use full `torch.no_grad` and preflight eval.
7. Checkpoint off-by-one expected `model_3999.pt` where runner produced `model_3998.pt`. Test inclusive arithmetic.
8. Previous tournament restarted from random weights when evaluation failed. Keep active block state and recover the last model.
9. Too many parallel robots (12,288) could fail before a traceback; default to 4096 and back off only for documented resource issues.
10. The early Arena selected a nonwalking champion and prevented its children from learning long enough. First discovery is a single 10k lineage, with direct displacement evaluation and continued learning through interim dips.
11. Confirmation typo case sensitivity and overly broad archive deletion UX. Current project uses only one explicit typed `DELETE` for its own app-owned directory. **No archive is implemented.**

## Safety and deletion

`cmd_reset` must verify confirmation token, acquire its file lock and refuse to delete while recognized training, evaluator or viewer processes are running. It uses `shutil.rmtree(BASE)` *only when* `BASE == HOME/'xgoduck_oneclick'` and BASE is not a symlink. Do not add a 'delete everything' option that deletes the user's Windows home directory or legacy WSL repo. Source checkout is deleted only because it is within the app-owned directory; resetting requires the next bootstrap to re-download dependencies.

PowerShell's worker uses `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` so Windows does not idle-sleep during unattended training. It does not make the system immune to shutdown, Windows Update, kernel errors or the user terminating the process. Do not promise such immunity.

## Tests required for new changes

Run `python -m unittest discover -s tests -v`, `python -m py_compile scripts/xgoduck_engine.py` and `bash -n scripts/bootstrap.sh` before release. The first live user run must execute the 8-iteration/evaluator preflight before meaningful training. Check recovery of interrupted blocks and model indexing on a real test job before declaring unattended behavior validated.

Add tests for: missing state with models; early 10k parent continuity; failed eval preserving latest checkpoint; changes to reward profile not altering observation/action dimensions; safe reset scope and lock; classifier of active project processes; reset preventing active process deletes; proper low-memory behavior; viewer CPU when `.pt` exists; actual TensorBoard availability; no double-run after stopping and resuming.

## Release and provenance

Package only the launcher, helper sources and documentation/tests. Do not bundle Hugging Face, GitHub or NVIDIA binaries. Zip paths must be relative and free of `__pycache__`. Include exact tested pin and state schema version. Maintain a `CHANGELOG.md`. Be candid that offline tests cannot verify a CUDA training cycle, MuJoCo collisions or the actor/critic weight-export path.

## Next research opportunities, not current guarantees

- Benchmark time-to-first-gait at 2,048/4,096/6,144 environments.
- Collect teacher demonstrations from a scripted stable alternating gait if pure PPO still converges to standing; validate the scripted model physically moves under the same actuator constraints.
- Optimize stride timing, foot contacts and physical actuation model against a sim-to-real test bench.
- Train stand-up and sit/stand separately, then use a high-level policy router; *not* pretend the walking task automatically learns get-up behavior.
- Introduce truly held-out terrains, perturbations and episodes exceeding 10 seconds once the flat-ground gait works.
- Add model-selection confidence intervals and several distinct evaluation seeds for robust generalization.
- Add an optional Windows startup task for crash/reboot recovery, but only with explicit user request and permission. Do not silently install a boot-time service.
