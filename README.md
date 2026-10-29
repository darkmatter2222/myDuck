# myDuck Studio 3

A Linux-first web utility for XGO-Duck experiments. Run it in WSL or on a Linux NVIDIA server; control it from your browser. No Windows launcher, PowerShell windows, Node installation or frontend build is needed.

## Start in WSL

Open Ubuntu and run:

```bash
sudo apt update
sudo apt install -y python3 git curl
cd ~
git clone https://github.com/darkmatter2222/myDuck.git
cd myDuck
./start.sh
```

Open **http://localhost:8765** in your Windows browser. The web app starts immediately with system Python 3.10+. Simulator dependencies download when you choose **Install / verify environment** or queue your first experiment. Training requires NVIDIA GPU access (`nvidia-smi` inside WSL) and at least 15 GiB free for setup. Keep this terminal running; closing the browser does not stop training.

If you already cloned into WSL:

```bash
cd ~/myDuck
git pull --ff-only
./start.sh
```

Do not start from the old Windows checkout or old PowerShell launchers. Stop old training before migrating. Existing models under `~/xgoduck_oneclick` are indexed without deleting them. The repo contains source; runtime data stays outside it. Updating source does not reset trained models.

## The workspace

| Page | What you can do |
|---|---|
| Overview | See runtime readiness, GPU utilization, model count, recent jobs, and evaluation trajectory |
| Experiments | Queue finite or repeating training pipelines, inspect saved settings/results/logs, cancel/stop jobs, clone configurations |
| Checkpoint tree | Inspect lineage; select a parent; branch/resume; pin, label, group into collections; preview and confirm deletion |
| Compare | Compare evaluations/configurations and overlay TensorBoard metrics across up to six selected runs |
| System & resources | Inspect host/GPU/disk/processes, start setup, stop services, export diagnostics/evidence, reset training data |

The viewer and TensorBoard stay separate: port **8080** and **6007** respectively. Their links activate after HTTP readiness and project ownership checks. After a reset, there is **no checkpoint to view**. Train until one is saved, select it in the tree, and choose **View checkpoint**. To switch, stop the existing viewer in System, then select another checkpoint. The viewer shows a snapshot, not live weights.

## Experiments and training

Create an experiment from random weights or any existing checkpoint. Each stage has a profile, update count, number of blocks and optional overrides. Stages continue from the previous stage's latest checkpoint, without jumping back to a champion on every rejected block. The original branch remains intact. New experiments do not automatically prune old checkpoints.

Supported controls: environment count, checkpoint interval, seed, learning rate, entropy coefficient, nine reward weights, forward/lateral/yaw command ranges, evaluation environments/seeds/duration, finite stage sequences, repeating sequences, and a configurable non-improvement pause limit. Not every simulator parameter is exposed; unknown fields are rejected rather than silently ignored. Editing settings creates a new experiment. Effective simulator configurations are also saved by upstream in each run's `params/` directory.

There is one queued training/evaluation/setup/export job at a time. CPU viewers and TensorBoard may run alongside training. Each new training job first exercises an 8-update training/evaluation preflight. Training blocks save checkpoints and are evaluated for standing, forward, reverse and turning behavior. A learning-stall pause is explicit and configurable; set the limit to 0 only if you intentionally want to disable it. Errors and low disk space still halt a job. Repeating mode repeats your chosen stage sequence; it is not an autonomous hyperparameter optimizer.

Run settings and provenance are immutable JSON snapshots. The app records job state in SQLite, while each worker writes durable logs and results. Restarting the web server reconnects to recognized worker processes. After a worker or machine crash, it does **not** silently replay a job: inspect the latest saved checkpoint and branch from it. Queued jobs resume dispatch when the web app starts. Stop/cancel unwanted queued work before leaving it unattended.

The training backend remains pinned to XGO-Duck upstream **725ed0c** rather than changing simulator APIs during the UI rebuild. The 61-observation / 14-action architecture is retained. Reward and curriculum profiles are experimental. Runtime, kernel, CUDA and real-robot convergence are not guaranteed by passing web tests.

## Checkpoint management

The tree groups runs and links their checkpoint lineage. File moves are represented by **collections**, which preserve upstream resume paths. Parent links inferred from old logs can be unknown; the UI does not invent missing history. Select one checkpoint and choose **Branch / resume** to continue into a new run. Multiple selected checkpoints can be deleted after a size/path preview and one confirmation. Pinned checkpoints and those needed by active/queued jobs are protected. Deleted files remain as history entries.

ONNX export is available for an individually selected checkpoint. Download the completed artifact from the job history. Exporting a file is not certification that the policy walks or is safe on hardware. Arbitrary checkpoint averaging/merging is deliberately absent: weight interpolation does not establish combined behavior. Teacher distillation, multi-skill routing and validated reference-motion training are research directions in [IDEAS-100.md](IDEAS-100.md).

## Comparisons and evidence

Compare shows run-level metrics from TensorBoard events with up to 500 samples per tag/run, by step or elapsed time. These are distinct from fixed-command evaluation results. Changes in reward weights can change reward scale, so compare displacement/survival and compatible configurations alongside reward. Training steps may overlap across resumed runs. Charts do not relabel them as one continuous optimization history.

Export training evidence from System. Download the ZIP from the completed export job. It contains original events, unsampled scalar CSV when TensorBoard is available, evaluation files, configurations, lineage, checkpoint inventory, source files, Studio database snapshot and job logs. Read its manifest for caps/omissions. Stop training for a consistent snapshot. Logs/configuration may contain local paths or private information. Model weights are not included. No automatic upload occurs.

## Run on a Linux server

Clone and start the same way on the server. From Windows, forward the app and optional services:

```powershell
ssh -N -L 8765:127.0.0.1:8765 -L 8080:127.0.0.1:8080 -L 6007:127.0.0.1:6007 your-user@your-server
```

Then browse `http://localhost:8765`. The default listener is loopback only. This is a single-user local utility with host/origin checks and a per-server request token, not a hardened public multi-user hosting service. Do not expose it directly to the Internet. Use SSH forwarding. Set environment count to suit the GPU; the default is 4096, and a smaller GPU can use 2048 as an initial experiment rather than an assumed performance guarantee.

Run the app inside `tmux` on a server if it should survive SSH logout. Stopping the web server leaves detached workers running; restarting reconnects. A Windows/WSL shutdown still stops Linux processes. Windows sleep prevention is no longer handled by a launcher: configure your host power settings for unattended training.

## Files and reset

- `~/.local/share/myduck-studio/`: Studio database, audit, immutable job configurations, stdout/stderr, exported artifacts and `studio.log`.
- `~/xgoduck_oneclick/`: pinned simulator, virtualenv, run checkpoints, event logs and evaluations.
- `./start.sh --port 8765 --state-dir /path/to/studio-state`: customize web port and Studio metadata location. Runtime location remains the bounded app-owned path above.

Reset stops queued/active managed jobs and recognized project services before deleting **only** `~/xgoduck_oneclick`. It preserves the Studio database and job logs. If processes cannot stop, it refuses deletion. No archive is created. The web server remains available throughout reset; wait for the reset job to complete before creating a new experiment.

## Validation and scope

See [BUILD-VERIFY.md](BUILD-VERIFY.md) for tests and verification limits. See [IDEAS-100.md](IDEAS-100.md) for 100 concrete ideas with explicit implementation status. The new UI/job manager ships now; research ideas are not presented as implemented training capabilities.

## Studio 3.1: WSL start, update, restart and stop

In **Windows PowerShell**, enter `wsl`. Then run these commands **inside Ubuntu** for an existing checkout:

```bash
cd ~/myDuck
git pull --ff-only
./start.sh
```

For a first installation only:

```bash
cd ~
git clone https://github.com/darkmatter2222/myDuck.git
cd myDuck
./start.sh
```

Open the **exact localhost URL printed in the terminal** in your Windows browser. The preferred port is 8765; if another application owns it, Studio tries the next 19 ports. `./start.sh --port 8766` sets a different starting port. Keep this terminal open. Refresh the browser after restarting because its session token changes.

Starting again automatically stops a **verified previous Studio web server for this metadata workspace**, then starts the current code. It preserves training workers, checkpoints, and service processes. An older Studio version without a process identity record must be stopped with Ctrl+C in its original terminal once. Unrelated port owners are never killed.

```bash
./start.sh --stop
```

This stops the web dashboard only. Running training and viewer/TensorBoard workers continue; queued work waits for the dashboard to return. To stop everything cleanly, cancel queued experiments and stop active jobs in **Experiments**, stop the viewer and TensorBoard under **System**, then run `./start.sh --stop`. To shut down all WSL distributions, run `wsl --shutdown` from **Windows PowerShell**; this also interrupts any other WSL workloads and can lose training progress since the last checkpoint.

### Viewer, selection and comparisons

- **Overview → Inspect your duck:** pick a checkpoint and click **Start viewer**. Wait for readiness, then **Open**. No checkpoint means there is nothing to simulate; the screen explains this. Stop an existing viewer in System before choosing another checkpoint.
- **TensorBoard:** click **Start** on Overview, wait for readiness, then **Open**. Its normal port is 6007, not 6006.
- **Checkpoint tree:** click a row to inspect it; checkboxes select files for bulk actions. **Select all matching** includes every non-deleted checkpoint matching your search, including collapsed branches. **Clear selection** deselects everything. Pins and active parents remain protected against deletion.
- **Compare:** select one to six checkpoints; curves load on entry. Runs shared by selected checkpoints produce one training trajectory. Metric guidance explains interpretation, including metrics with no universal good direction. Change the axis between optimizer step and elapsed minutes.
- **Add chart tile** keeps a metric visible beside others (up to 12). Tiles use optimizer step on their horizontal axis. **Save dashboard** stores the metric layout in this browser; **Save SVG** exports a tile; **Export displayed data** saves sampled data as JSON. Full histories remain in evidence exports. Hover chart points for values.
- **Evaluate selected** queues fixed-command evaluations. Empty evaluation charts mean evaluations have not completed; saved training checkpoints do not themselves contain evaluation results.
- Hover or focus the **?** next to experiment fields for definitions. More parallel environments do not substitute for independent seeds.

### Policies and honest interpretation

The four current profiles train **locomotion**. They are reward/command presets, not four distinct robot skills. Sitting, recovery and stand-up tasks are not implemented. Adding their names to a menu would not teach those skills. These need task-specific commands, rewards, termination logic and physical evaluation before being offered as trainable behaviors.

See [IDEAS-200.md](IDEAS-200.md) for 100 additional analysis and utility proposals, clearly marked as a roadmap rather than implemented functionality.

## Analysis workbench

Use the persistent **Analysis targets** toolbar from any workspace. Filter by run, label or checkpoint step; select an item and click **Add target**. **Latest per run** selects one checkpoint from each of the six most recently saved runs. Remove individual target chips or use **Clear targets**. Compare loads these targets automatically. Targets stay selected while navigating; reloading the page clears them.

The **Checkpoint manager** has a separate selection for deletion and organization. Its checkboxes never change analysis targets. Analysis selection never authorizes deleting files. The workbench uses a horizontal workspace bar, full-width neutral graphite panels and NVIDIA-green circuit accents.
