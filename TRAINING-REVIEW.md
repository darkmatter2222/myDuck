# Training audit update (2.2.0)

Stop training before updating. Do not reset or delete your existing run.

1. Update this repository (`git pull --ff-only` in the repository folder).
2. Reopen START-XGODUCK.cmd and click **Export training data** in the dark desktop.
3. Explorer selects `diagnostics/myDuck-training-YYYYMMDD-HHMMSS.zip`. Review and share that ZIP for analysis. Console option 11 does the same.

The export includes raw TensorBoard event files, an unsampled scalar CSV when the training Python has TensorBoard, all evaluation JSON/leaderboards, training configuration files, controller state, Windows/Linux logs, source versions, checkpoint metadata and reconstructed parent lineage. Checkpoint weights stay on your machine. The manifest lists omitted files, truncated logs and changes during copying. Source capture is capped at 2 GiB total / 512 MiB per file, log tails at 16 MiB. The CSV has a separate 2 GiB limit. Exports may contain usernames, local paths and sensitive content in logs/configs: review before sharing. No automatic upload occurs.

## What the overnight evidence establishes

Runs c0008 through c0013 started generalization from the same model_17993.pt and requested 4000 updates. They were distinct optimizer attempts, but rejection repeatedly returned the next attempt to the same champion. The controller had no useful learning-stall stop. TensorBoard's repeated step ranges therefore do not, by themselves, mean the optimizer never ran.

The controller now preserves the best checkpoint separately while continuing the working candidate. Three consecutive rejected attempts with the same profile and ending checkpoint index, or six consecutive rejected candidates overall, stop training for review. This also recognizes old saved histories. Restarting does not clear the guard. An affected campaign is intentionally paused until its evidence has been reviewed; this update does not automatically repair its policy or erase its history.

Generalization and new walking ONNX exports now require forward progress >=0.7 and every forward evaluation seed to have full-episode survival >=0.9, progress >=0.5, and lateral drift <=0.3m. These are conservative engineering checks over the existing short evaluation, not proof of robust walking. Existing ONNX files are not removed or retroactively certified. Champion selection still keeps provisional nonwalking improvements.

The viewer loads a checkpoint snapshot at startup; it does not live-reload newly trained weights. Close and reopen it to inspect a later checkpoint. A falling viewer snapshot alone does not characterize every model trained afterward.

## Next training decisions

First inspect per-scenario displacement, survival, reward components, episode termination signals, PPO entropy/KL/value losses, configuration changes and checkpoint lineage together. Do not compare reward totals across different reward profiles as a common scale. Separate a standing local optimum, immediate physical falls, numerical instability and a stale viewer before changing hyperparameters.

Use the robot-specific upstream XGO-Duck environment as the reference, preserving the pinned simulator and observation/action layout. Reproduce a compatible known-good walking policy as a control if available; validate joint order, scales, morphology and actuator model before using it as a teacher. An ONNX inference policy is not a resumable PPO optimizer checkpoint.

If PPO still fails to discover a gait under the verified dynamics, investigate reference-motion imitation / teacher distillation, then forward-task fine-tuning. DeepMimic provides evidence for combining motion imitation and task objectives, but does not supply a drop-in XGO-Duck trainer. Expand commands and randomization incrementally only after forward gait validation, with longer holdouts and recorded rollouts. Neither this update nor more runtime guarantees convergence.

Sources:
- https://github.com/LuwuDynamics/xgoduck_rl
- https://github.com/LuwuDynamics/xgoduck_runtime_arduino
- https://arxiv.org/abs/1804.02717

## Validation

29 offline tests cover controller recovery, startup/service behavior, export ZIP content, model preservation, export size caps, lineage detection and the new curriculum guard. GitHub Actions additionally checks Windows PowerShell parsing, worker arguments, desktop construction/layout and launcher success/failure fixtures. These checks do not execute GPU training or establish a learned gait.
