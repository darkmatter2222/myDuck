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
