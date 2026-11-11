#!/bin/bash
# make doctor: sanity checks. Prints PASS, FAIL or SKIP for each check. Exit 1 only when a check FAILs.
# Env (from the Makefile): IS_WSL SIM_IMAGE DEV_IMAGE PYTORCH_IMAGE LSP_BIN_DIR. Expected output: docs/setup.md
fails=0
pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1 -> $2"; fails=$((fails + 1)); }
skip() { echo "SKIP  $1 -> $2"; }
# check <name> <fix hint> <command...>
check() {
  local name="$1" hint="$2"; shift 2
  if "$@" >/dev/null 2>&1; then pass "$name"; else fail "$name" "$hint"; fi
}

for c in git make docker; do check "host tool: $c" "install $c" command -v "$c"; done
check "docker daemon" "start Docker Desktop and enable WSL integration" docker version
check "docker compose" "install the compose plugin" docker compose version
check "docker buildx" "install the buildx plugin" docker buildx version

if [ -n "$IS_WSL" ]; then
  check "WSL2 kernel (uname -r has microsoft-standard-WSL2)" "use WSL2, not WSL1" \
    bash -c 'uname -r | grep -q microsoft-standard-WSL2'
  check "WSLg mount /mnt/wslg" "update WSL: wsl --update" test -d /mnt/wslg
  check "GPU device /dev/dxg" "update the NVIDIA Windows driver and WSL" test -e /dev/dxg
  check "nvidia-smi in WSL" "install the NVIDIA Windows driver (no Linux driver in WSL)" nvidia-smi
  if docker image inspect "$PYTORCH_IMAGE" >/dev/null 2>&1; then
    check "docker GPU (nvidia-smi in container)" "enable GPU support in Docker Desktop" \
      docker run --rm --gpus all "$PYTORCH_IMAGE" nvidia-smi
  else
    skip "docker GPU (nvidia-smi in container)" "image not local; run: docker pull $PYTORCH_IMAGE (several GB)"
  fi
  skip "Docker Desktop host networking" "check by hand: Settings > Resources > Network > Enable host networking"
  skip "glxinfo -B (GUI renderer)" "the gui image comes in the sim-gz PR"
else
  skip "WSL checks (kernel, WSLg, /dev/dxg, GPU)" "not on WSL"
fi

if docker image inspect "$SIM_IMAGE" >/dev/null 2>&1; then
  check "sim image: gz sim --versions" "rebuild: make sim-image" \
    docker run --rm "$SIM_IMAGE" gz sim --versions
  check "sim image: ros_gz_bridge installed" "rebuild: make sim-image" \
    docker run --rm "$SIM_IMAGE" bash -c 'ros2 pkg list | grep -q ros_gz_bridge'
  check "sim image: rccar_bringup installed" "rebuild: make sim-image" \
    docker run --rm "$SIM_IMAGE" bash -c 'ros2 pkg list | grep -q rccar_bringup'
else
  fail "sim image $SIM_IMAGE" "run make sim-image"
fi

if docker image inspect "$DEV_IMAGE" >/dev/null 2>&1; then
  if [ -x "$LSP_BIN_DIR/pyright-langserver" ]; then
    check "LSP initialize through the shim" "run make lsp" \
      python3 tools/lsp/smoke.py "$LSP_BIN_DIR/pyright-langserver" --stdio
  else
    skip "LSP initialize through the shim" "shim not installed; run make lsp"
  fi
  check "make pin-check" "see tests/test_pin.py output" make pin-check
else
  fail "dev image $DEV_IMAGE" "run make dev-image"
fi

skip "gym image checks (torch, gymnasium)" "available after the gym PR"
skip "sim-up headless topic rates" "available after the sim-gz PR"

if [ "$fails" -gt 0 ]; then echo "doctor: $fails check(s) FAILED"; exit 1; fi
echo "doctor: no FAIL"
