# 3.0.0 — Linux-first web experiment studio

Replaces the PowerShell/WinForms launcher with `./start.sh` and a local browser app on port 8765. Adds persistent job queue, sequential/repeating training stages, immutable configuration snapshots, checkpoint lineage and branches, pins/collections/protected deletion, comparisons, explicit service readiness, host health, ONNX/evidence downloads and scoped reset.

Keeps the pinned GPU simulator boundary and introduces per-experiment state instead of a single global autonomous campaign. Removes automatic checkpoint pruning from the new workflow. Adds input validation and origin/token protections. Old Windows launcher files and tests are removed; Git history retains previous releases.

The web UI does not guarantee successful learning. Reference-motion teachers, automated search and multi-skill composition are documented research ideas rather than implemented capabilities.
