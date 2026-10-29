# Start in Ubuntu / Linux

```bash
git clone https://github.com/darkmatter2222/myDuck.git
cd myDuck
./start.sh
```

Open **http://localhost:8765** in your Windows browser. If Python/git/curl are missing, install them with `sudo apt install python3 git curl`.

Choose **New experiment**. Starting the first training job installs the simulation dependencies and runs a short GPU preflight. After a checkpoint appears, select it in **Checkpoint tree** to view, evaluate, export, or branch. A fresh environment has no model to display.

For a server, use the SSH forwarding instructions in [README.md](README.md). The old PowerShell and desktop launchers have been removed.
