#!/usr/bin/env bash
# One-click reproducible XGO-Duck install. Does not touch legacy ~/xgoduck_rl.
set -Eeuo pipefail
export PATH="$HOME/.local/bin:/usr/lib/wsl/lib:$PATH"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONUNBUFFERED=1 UV_NO_PROGRESS=1 NO_COLOR=1 TERM=dumb
BASE="$HOME/xgoduck_oneclick"
REPO="$BASE/xgoduck_rl"
PIN='725ed0c'
if [[ -L "$BASE" ]]; then echo 'Refusing symlink project root'; exit 23; fi
# Serialize setup with training/reset; prevent uv sync changing a live environment.
exec 9>"$HOME/.xgoduck_oneclick.lock"
flock -n 9 || { echo 'Training/setup is already active. Use Status.'; exit 25; }
mkdir -p "$BASE/reports/setup"
SETUP_LOG="$BASE/reports/setup/setup-$(date +%Y%m%d-%H%M%S)-$$.log"
exec > >(tee -a "$SETUP_LOG") 2>&1
echo "[XGO-SETUP] Full setup log: $SETUP_LOG"
trap 'echo "[XGO-SETUP] Failed at line $LINENO (exit $?). Re-run Setup after fixing the visible error."' ERR
log(){ printf '[XGO-SETUP] %s\n' "$*"; }
for bin in python3 git curl; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    log "Missing $bin in Ubuntu. Install prerequisite and re-run. No models were removed."
    exit 21
  fi
done
if ! command -v uv >/dev/null 2>&1; then
  log 'Installing uv package manager'
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:/usr/lib/wsl/lib:$PATH"
fi
if [[ "${1:-}" == '--tensorboard-only' ]]; then
  log 'Preparing TensorBoard only; no GPU or training installation required'
  python3 "$SCRIPT_DIR/setup_step.py" --label 'TensorBoard package' --timeout 900 -- uvx --python 3.12 --with setuptools==80.9.0 --from tensorboard==2.20.0 tensorboard --version
  exit 0
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  log 'NVIDIA driver interface is not available inside WSL. Install/update Windows NVIDIA driver; run nvidia-smi in Ubuntu.'
  exit 22
fi
log "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"
if [[ ! -d "$REPO/.git" ]]; then
  if [[ -e "$REPO" ]]; then log "Refusing to overwrite unexpected directory $REPO"; exit 23; fi
  log 'Cloning upstream XGO-Duck robotics simulation repository'
  git clone https://github.com/LuwuDynamics/xgoduck_rl.git "$REPO"
fi
cd "$REPO"
current="$(git rev-parse --short HEAD 2>/dev/null || true)"
if [[ "$current" != "$PIN" ]]; then
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    log "Local source edits found in $REPO. Refusing to overwrite user modifications."
    exit 24
  fi
  log "Checking out tested upstream revision $PIN"
  if ! git cat-file -e "$PIN^{commit}" 2>/dev/null; then git fetch origin; fi
  git checkout --detach "$PIN"
fi
free_kb=$(df -Pk "$BASE" | awk 'NR==2 {print $4}')
if (( free_kb < 15728640 )); then log 'Need at least 15 GiB free for setup.'; exit 26; fi
log 'Installing pinned dependencies into Linux .venv (large first-time download)'
export UV_HTTP_TIMEOUT=600
uv python install 3.12
python3 "$SCRIPT_DIR/setup_step.py" --label 'Pinned dependency installation' --timeout 7200 -- uv sync --frozen
log 'Verifying CUDA and simulator (heartbeat every 15 seconds; 20 minute timeout)'
python3 "$SCRIPT_DIR/setup_step.py" --label 'CUDA and simulator verification' --timeout 1200 -- "$REPO/.venv/bin/python" -u "$SCRIPT_DIR/verify_runtime.py"
log 'Checking TensorBoard from the existing training environment'
if python3 "$SCRIPT_DIR/setup_step.py" --label 'Training-environment TensorBoard' --timeout 120 -- "$REPO/.venv/bin/tensorboard" --version; then
  log 'TensorBoard ready (using training environment; no second installation)'
else
  log 'WARNING: TensorBoard check failed. Training setup is ready; dashboard failure will not block training.'
fi
log "READY: $REPO"
