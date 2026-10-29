# 2.2.0 — training evidence and stall protection

- Export training history from dark desktop / console option 11, preserving models.
- Stop repeated rejected branches, including existing campaigns; keep champion separate from continuing candidate.
- Require forward-task survival and progress before generalization / new walking exports.
- Record parent and score in history; document research and remaining GPU validation.

# TensorBoard dependency fix

- Full setup verifies the TensorBoard already installed in the training environment; it no longer creates a redundant isolated install.
- Standalone TensorBoard explicitly includes setuptools 80.9.0 (provides pkg_resources) and Python 3.12.
- Dashboard verification/window launch failures no longer abort a healthy training setup.
- CI installs and runs the real standalone TensorBoard command, beyond fixture tests.

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
