# 2.1.0

- Add a Windows desktop control panel with named actions, visible URLs and live task logs; retain the console fallback.
- Export one bounded diagnostics text file with Windows transcripts and WSL state/setup/preflight/training/evaluation/service logs, including when WSL cannot start.
- TensorBoard now prepares its own dependencies and can start before the training checkout exists.
- Merge native progress as readable text instead of PowerShell error-record formatting.
- Persist setup logs, add unbuffered verification phases, heartbeat and timeout supervision.
- Add actual local HTTP readiness, installer fixture, diagnostic recovery and Windows full-launcher success/failure tests. GPU/Norton testing remains a local requirement.

# 2.0.1

- Use plain PowerShell -File worker invocation instead of encoded command text.
- Replace process execution-policy Bypass with RemoteSigned in launchers and documented commands.
- Validate worker arguments, report immediate worker exit in the parent, and add real Windows child-process argument tests.
- Document Norton review steps without changing antivirus settings or creating exclusions.

# 2.0.0

- Rebuilt Windows launcher: native exit codes separated from output; held worker windows; per-process transcripts; Ubuntu discovery; WSL startup and path mapping; encoded worker arguments.
- Fixed training overrides to address TrainConfig.env (verified against pinned mjlab source).
- Start launches TensorBoard and a checkpoint-waiting CPU viewer. Service logs, HTTP readiness, owned-service locks and port-conflict errors replace blind starts.
- Setup lock prevents environment mutation during training. CUDA kernel and task-registry checks added. Bootstrap handles local commit pins without fetching abbreviated hashes.
- Re-run preflight on engine-version changes. Fix bounded CLI mode and completed status. Preserve Ctrl+C through evaluation. Stop after three consecutive failed block evaluations.
- Added configuration/profile, service-error and interruption tests plus GitHub Actions Windows PowerShell parsing.
- Preserved gait-first lineage, explicit one-confirmation scoped reset, no archives, and checkpoint recovery.
