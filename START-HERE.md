## Studio update 2.3.0

Update with `git pull --ff-only`, close the old studio and reopen `START-XGODUCK.cmd`.

The dark desktop now runs workers hidden, with no live-log panel or held worker consoles. Open saved logs and Export diagnostics remain available. Every task saves stdout, stderr, a PowerShell transcript and a JSON completion result under `launcher-logs`; desktop startup errors go to `desktop-startup.log`. The status area reports background activity and completion/failure/paused outcomes.

Start/resume checks the campaign before installing dependencies. A learning stall is an expected paused state (exit 20), not a traceback. Start no longer automatically launches TensorBoard or the viewer: open each explicitly when needed. Recognized existing project listeners are reused. An unrelated or unverified port owner is never killed; its conflict is reported in the saved log and status.

To start completely fresh, click Reset project and accept its single confirmation. It stops recognized project processes, waits up to 20 seconds and deletes only `~/xgoduck_oneclick`. If a process does not stop or the project lock is still held, deletion is refused and the error is logged. Your Windows repository and its launcher logs remain. There is no archive. After reset reports completion, click Start/resume for fresh setup and training.

Old held console windows may remain from the previous version; close them after stopping old tasks. Closing the new studio does not stop background work. The progress indicators describe tasks launched by that studio session, not live GPU metrics. Training quality is still subject to evaluation; these launcher repairs do not establish a successful learned gait.

Validation: 33 Linux tests; Windows CI covers parsing, desktop construction/layout, actual worker argument passing, native stderr, structured paused outcomes and confirmed background reset through a WSL fixture. Real Windows/WSL/Norton/GPU behavior on your machine still requires verification.

## Training stuck after an overnight run?

Stop training, update this repository, reopen the dark launcher and click **Export training data**. Send the ZIP selected in Explorer. Do not reset your models. See [TRAINING-REVIEW.md](TRAINING-REVIEW.md) for the repeated-attempt fix, export contents and next training decisions.

# Start here

Double-click **START-XGODUCK.cmd**, then click **Start / resume training**.

The desktop panel shows the live task log and service addresses:
- TensorBoard: http://localhost:6007
- Viewer: http://localhost:8080 (available only after a checkpoint loads)

Click **Export diagnostics** to create one text file containing Windows and WSL log tails. Explorer selects the file for you. This works even when setup has not finished.

Close old launcher windows after updating. Keep the repository folder intact. Use **Stop training** before resetting. **Reset project** asks for DELETE once and creates no archive.

Console fallback: run XgoDuck.ps1; option 8 exports diagnostics.
