#!/usr/bin/env bash
set -euo pipefail

# Build/install talos into an isolated venv under talos/build
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
mkdir -p build

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_COLOR=1

if [ ! -x "build/venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv build/venv
fi

# Quiet successful installs; stderr still shows failures
build/venv/bin/python -m pip install --upgrade pip >/dev/null
build/venv/bin/python -m pip install -e . >/dev/null

# Expose a stable bin path
(cd build && ln -sfn venv/bin bin)

echo "Talos ready: $SCRIPT_DIR/build/bin/talos"
