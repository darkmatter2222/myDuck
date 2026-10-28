# myDuck: XGO-Duck training control center

Train XGO-Duck in simulation from a Windows launcher, with WSL2, checkpoint recovery, automatic evaluation, TensorBoard and a browser viewer.

## Start

1. Clone this repository on Windows, or download and extract its ZIP. Keep the entire folder together.
2. Double-click **START-XGODUCK.cmd**.
3. Click **Start / resume training** in the desktop panel. Leave the training worker window open.

Start installs the pinned upstream simulator and dependencies, checks CUDA, starts TensorBoard and a waiting viewer, runs an 8-update training/evaluation preflight, then starts/resumes the campaign. WSL starts automatically when invoked, including after a reboot. The first download and Warp compilation can take time; progress and errors remain visible.

Requirements: Windows with an NVIDIA CUDA-capable GPU (target: RTX 5090), current Windows NVIDIA driver, Ubuntu on **WSL2**, internet access, and at least 15 GiB free in WSL for setup (substantially more for a long campaign). Ubuntu needs `python3`, `git`, `curl`, `flock` and normal system libraries. If WSL is absent, run `wsl --install -d Ubuntu` from an administrator terminal, reboot if requested, and finish Ubuntu's first-user setup. The launcher reports missing prerequisites rather than hiding an administrator/password prompt inside unattended work.

If more than one Ubuntu distribution is installed, use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\XgoDuck.ps1 -Distro Ubuntu-24.04
```

To skip the menu:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\XgoDuck.ps1 -Task run -Hold
```

## Desktop control panel

The default launcher opens a Windows desktop panel with named actions, visible service URLs, a task selector and the latest 250 lines of each task's log. Training workers remain separate, visible windows. A running worker window is not proof training succeeded; the log shows the actual phase and result.

**Export diagnostics** creates `diagnostics/myDuck-diagnostics-<timestamp>.txt` and selects it in Explorer. It combines recent Windows transcripts, WSL setup/preflight/training/evaluation/service log tails, campaign state, upstream revision and a bounded GPU probe. It still exports Windows logs if WSL is unavailable. Review it before sharing: usernames and local paths are included; model weights and environment-variable dumps are not.

The console menu remains available via `XgoDuck.ps1`. Option **8** exports the same report. Option **4** now prepares TensorBoard independently if training is not installed. TensorBoard can show an empty dashboard before training writes events. The viewer explicitly reports that port 8080 is unavailable while waiting for a checkpoint.

Setup logs are persisted from the beginning under `~/xgoduck_oneclick/reports/setup`. GPU verification identifies each phase and emits a heartbeat every 15 seconds. It stops after 20 minutes with a specific timeout instead of waiting silently. Dependency installation has a two-hour limit. These are failure diagnostics, not promises about setup duration.

## What you see

- **Training window:** setup, preflight, training progress, evaluation and recoverable errors. Worker windows stay open at completion or failure.
- **TensorBoard:** http://localhost:6007, opened only after HTTP readiness. PPO curves are written by upstream training.
- **Viewer:** http://localhost:8080, CPU playback of the first real checkpoint. It waits up to two hours for that checkpoint. This is a snapshot, not live policy hot-reloading. Close its window and choose **3** to load a newer snapshot.
- **Status (2):** checkpoint paths, current phase, best measured score, and last error.
- **Logs (5):** latest training, evaluation, preflight or service log. Windows startup logs are in `launcher-logs` beside the launcher. The desktop shows these live.

Viewer/TensorBoard failures have separate logs and do not terminate training. Opening either twice reuses the owned service. An unrelated process occupying the requested port produces a visible error. If automatic browser launch is unavailable in your WSL configuration, open the printed localhost URL manually.

## Training strategy

The initial 10,000 PPO updates follow one continuous policy, in 2,000-update blocks, with 4,096 parallel environments and checkpoints every 250 updates. The gait-discovery profile prioritizes commanded forward motion and reduces competing posture/head objectives. This is an engineering hypothesis, not a known optimal recipe.

After each block, a separate process measures standing, forward travel, reverse and turns at fixed commands/seeds. Selection depends on actual displacement and survival, not training reward alone. The best model is retained while learning continues. After the baseline, the controller tries longer reward/exploration profiles; meaningful forward progress unlocks broader command training. Occasional fresh seeds are deliberate later experiments, not a reaction to failed evaluation.

The default campaign has **no 24-hour timer and no automatic claim of completion**. It continues while healthy until you choose **7** or press Ctrl+C in training. Re-run **1** to resume saved work. Three consecutive failed block evaluations stop the campaign with models preserved; repeated training failures also stop rather than spin forever. A bounded CLI mode exists through `xgoduck_engine.py run --max-updates 10000` (omit `--forever`).

A provisional champion may only stand. Status shows its measured forward progress. ONNX export is attempted only after a minimum movement/survival gate, and export errors are warnings. Passing this gate is not certification for physical deployment. Walking, stand-up, object interaction and vision are separate capabilities; this project trains the velocity/walking policy.

## Reset: one confirmation, no archives

Stop training and close viewer/TensorBoard. Choose **9**, then type **DELETE** once.

This permanently removes **`~/xgoduck_oneclick`**, including its upstream checkout, dependencies, checkpoints, logs, best policy and controller state. It never archives. It refuses to delete while recognized project processes hold the files. Your Windows launcher checkout and a separate legacy `~/xgoduck_rl` are outside the reset scope. The next Start reinstalls the project.

## Installed layout

| Path inside Ubuntu | Purpose |
|---|---|
| `~/xgoduck_oneclick/xgoduck_rl` | Pinned upstream simulator, robot model and Python environment |
| `~/xgoduck_oneclick/state.json` | Atomic campaign state |
| `~/xgoduck_oneclick/reports` | Evaluation JSON/CSV and complete subprocess logs |
| `~/xgoduck_oneclick/best` | Champion copy and qualifying ONNX export |
| `~/xgoduck_oneclick/xgoduck_rl/logs/rsl_rl/xgoduck_velocity` | PPO checkpoints and TensorBoard events |

All project control code is in this repository. The first run downloads upstream source/assets and packages; GPU libraries and wheels are not committed here. Upstream is pinned to `LuwuDynamics/xgoduck_rl` revision `725ed0c`, which pins mjlab 1.3.0, Warp 1.12.0 and PyTorch 2.9.1. TensorBoard fallback is pinned to 2.20.0 with setuptools 80.9.0 and Python 3.12 because this release imports pkg_resources. Full training setup uses its existing TensorBoard and does not create a second installation. Dashboard startup failures do not block the training campaign. No cloud training account is needed.

## Research and limits

- [XGO-Duck upstream](https://github.com/LuwuDynamics/xgoduck_rl): robot-specific geometry, masses, BAM actuators, PPO and ONNX workflow. A MicroDuck checkpoint is not assumed to fit XGO-Duck.
- [MicroDuck issue 46](https://github.com/pollen-robotics/microduck_rl/issues/46): reports standing-in-place convergence despite reward changes. More iterations alone do not prove walking.
- [Google locomotion research](https://research.google/pubs/sim-to-real-learning-agile-locomotion-for-quadruped-robots/): accurate simulation, randomization and optional reference motion can aid transfer. This is supporting research, not proof for this biped.
- [Learning locomotion skills for Cassie](https://proceedings.mlr.press/v100/xie20a.html): reference-motion guidance and iterative design provide another path if gait discovery remains stuck. A validated XGO-Duck reference gait is not available in this package, so an untested demonstration is not silently substituted.

The practical starting approach here is the robot-specific pinned PPO stack, a motion-focused curriculum, measured evaluation and retained checkpoints. A teacher/reference gait is a future option if measured results stall. No software can promise a perfect or physically ready duck after an unattended run.

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/xgoduck_engine.py
bash -n scripts/bootstrap.sh
```

GitHub Actions runs offline tests and Windows PowerShell 5.1 parsing. These checks do not validate GPU physics, local WSL networking, browser rendering or real-robot behavior. The live preflight on your machine is mandatory; do not treat offline test success as a completed CUDA run.

## Norton behavioral alert / disappearing workers

Version 2.0.1 replaces encoded PowerShell worker commands with visible `-File` calls and uses process-scoped `RemoteSigned` instead of `Bypass`. The parent reports an immediate worker exit. No antivirus exclusions, security-service changes or quarantine actions are performed by this project.

A reported IDP.HELU.PSE95 alert terminated PowerShell/WSL while launching workers. An antivirus-terminated process cannot keep its own window open. The encoded command is a suspected trigger, not a verified diagnosis of the local system. This change does not clear Norton's pending quarantine or guarantee Norton will accept the new command.

Close the old menu, update this checkout with `git pull --ff-only` from Command Prompt, and run Norton LiveUpdate. If Norton still lists pending quarantine of PowerShell/WSL, stop relaunching and ask Norton Support to review that pending action. Do not broadly exclude PowerShell, WSL, Windows folders or all scripts. Norton documents suspected false-positive reports at https://support.norton.com/sp/en/us/home/current/solutions/kb20090410134005EN . Include the detection name, alert ID, repository URL and exact logged command. This repository cannot validate your installed Windows binaries or cancel Norton's reboot action.

Prefer a Git clone. ZIP downloads may mark scripts as internet-origin, which RemoteSigned can reject. Review the downloaded files and their provenance; do not weaken system-wide execution policy to resolve a launch error.
