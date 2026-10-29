# myDuck Studio engineering contract

The primary entry point is `./start.sh`. This is a local Linux/WSL web utility, not a Windows desktop launcher or publicly hosted website. The user has authorized replacing the old launcher architecture. Preserve the simulator integration and users' runtime data during source updates.

## Boundaries

- Web app: Python standard library, `studio/`, `web/`. No required npm install, UI toolkit or external CDN.
- Runtime: `~/xgoduck_oneclick`, upstream pinned to `725ed0c`; engine in `scripts/xgoduck_engine.py`.
- Metadata: `~/.local/share/myduck-studio`; persisted queue, audit, configs, worker stdout/stderr and results.
- Keep process starting distinct from HTTP readiness. A missing checkpoint must reject viewer startup before spawning a process.
- Never auto-delete models or prune a branch. Deletion is explicit, scoped, previews files/size, protects pending/active parents and pins, and retains tombstone history.
- Reset has one explicit confirmation. Stop recognized jobs/services, wait, then delete only the exact app-owned runtime path. Never kill an arbitrary port owner or delete metadata/source as part of runtime reset.
- Do not silently clear learning-stall pauses or claim convergence. Configurable repeating pipelines are not an autonomous optimizer.
- Checkpoints are trusted local training artifacts. Do not deserialize arbitrary user-uploaded pickle files. No upload/load-by-arbitrary-path route.
- Bound loopback; protect request origins/host headers/mutations. Remote use is through SSH tunnels.
- Train/evaluate serially under the existing runtime lock. Persist immutable parent/configuration before dispatch.
- Reconnect to known worker processes after web restart; never rerun a lost worker silently. Offer explicit branching from saved checkpoints.
- Effective custom reward settings use `cfg.env`, not top-level cfg reward/event fields. Preserve observation/action dimensions and `torch.no_grad()` evaluator semantics.
- Pinned RSL-RL naming: fresh N updates -> model_(N-1); parent P + N updates -> model_(P+N-1). Do not equate filename step with global optimizer-update count.
- Never compare different reward scales as proof of improvement. Measure net displacement, survival and per-task errors. A valid ONNX export is not a walking certification.
- Avoid arbitrary checkpoint merging. Distillation and skill routing require separate validated implementation.

## Verification

Run `python -m unittest discover -s tests -v`, `python -m compileall -q studio scripts`, `bash -n start.sh scripts/bootstrap.sh`, and `node --check web/app.js`. Node is only a development/CI check, not a user runtime dependency. Add behavioral tests for mutations and worker lifecycle. Test actual HTTP startup. Unit tests and mocked simulator jobs are not GPU training validation. Report browser QA limits accurately.

When publishing through GitHub API, transfer bounded chunks, verify every blob hash against local sources, then create the commit. Never trust potentially truncated tool output as source content. Preserve remote user changes with an expected-SHA lease.
