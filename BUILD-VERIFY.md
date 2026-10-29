# Verification

- 43 Python tests pass locally: existing engine recovery/startup/export tests plus the new API, schema, catalog lineage, protected deletion, queue serialization, persistence, reset cancellation, and staged-worker continuation tests.
- Python modules compile; Bash entry/setup scripts parse; browser JavaScript passes Node syntax checks.
- GitHub Actions runs all checks and starts the actual HTTP application to check health, page content and authenticated empty state. It also verifies real TensorBoard installation.
- New worker pipeline tests use a simulator fixture. No CUDA training, real checkpoint deserialization, MuJoCo viewer or ONNX conversion was executed in this development host.
- Browser visual interaction QA was attempted through the supported preview, but the browser route was blocked by its security policy. Do not characterize the interface as visually verified.

User runtime requires Python 3.10+, Linux/WSL, and working NVIDIA driver access for training. GPU dependencies are installed from the fixed upstream lockfile by the setup action. A fresh first run must pass the short training/evaluation preflight before extended training.
