## Studio update 2.3.0

Update with `git pull --ff-only`, close the old studio and reopen `START-XGODUCK.cmd`.

The dark desktop now runs workers hidden, with no live-log panel or held worker consoles. Open saved logs and Export diagnostics remain available. Every task saves stdout, stderr, a PowerShell transcript and a JSON completion result under `launcher-logs`; desktop startup errors go to `desktop-startup.log`. The status area reports background activity and completion/failure/paused outcomes.

Start/resume checks the campaign before installing dependencies. A learning stall is an expected paused state (exit 20), not a traceback. Start no longer automatically launches TensorBoard or the viewer: open each explicitly when needed. Recognized existing project listeners are reused. An unrelated or unverified port owner is never killed; its conflict is reported in the saved log and status.

To start completely fresh, click Reset project and accept its single confirmation. It stops recognized project processes, waits up to 20 seconds and deletes only `~/xgoduck_oneclick`. If a process does not stop or the project lock is still held, deletion is refused and the error is logged. Your Windows repository and its launcher logs remain. There is no archive. After reset reports completion, click Start/resume for fresh setup and training.

Old held console windows may remain from the previous version; close them after stopping old tasks. Closing the new studio does not stop background work. The progress indicators describe tasks launched by that studio session, not live GPU metrics. Training quality is still subject to evaluation; these launcher repairs do not establish a successful learned gait.

Validation: 33 Linux tests; Windows CI covers parsing, desktop construction/layout, actual worker argument passing, native stderr, structured paused outcomes and confirmed background reset through a WSL fixture. Real Windows/WSL/Norton/GPU behavior on your machine still requires verification.

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
