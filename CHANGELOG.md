# 2.0.0

- Rebuilt Windows launcher: native exit codes separated from output; held worker windows; per-process transcripts; Ubuntu discovery; WSL startup and path mapping; encoded worker arguments.
- Fixed training overrides to address TrainConfig.env (verified against pinned mjlab source).
- Start launches TensorBoard and a checkpoint-waiting CPU viewer. Service logs, HTTP readiness, owned-service locks and port-conflict errors replace blind starts.
- Setup lock prevents environment mutation during training. CUDA kernel and task-registry checks added. Bootstrap handles local commit pins without fetching abbreviated hashes.
- Re-run preflight on engine-version changes. Fix bounded CLI mode and completed status. Preserve Ctrl+C through evaluation. Stop after three consecutive failed block evaluations.
- Added configuration/profile, service-error and interruption tests plus GitHub Actions Windows PowerShell parsing.
- Preserved gait-first lineage, explicit one-confirmation scoped reset, no archives, and checkpoint recovery.
