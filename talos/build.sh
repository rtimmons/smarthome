#!/usr/bin/env bash
set -euo pipefail

# Build/install talos into an isolated venv under talos/build
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
mkdir -p build

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_COLOR=1

# Check if we need to recreate the venv due to Python version mismatch
RECREATE_VENV=0
if [ -x "build/venv/bin/python" ]; then
  VENV_PYTHON_VERSION=$(build/venv/bin/python --version 2>&1 | awk '{print $2}')
  CURRENT_PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')

  # Compare major.minor versions
  VENV_MM=$(echo "$VENV_PYTHON_VERSION" | cut -d. -f1,2)
  CURRENT_MM=$(echo "$CURRENT_PYTHON_VERSION" | cut -d. -f1,2)

  if [ "$VENV_MM" != "$CURRENT_MM" ]; then
    echo "Python version changed ($VENV_MM → $CURRENT_MM), recreating venv..." >&2
    rm -rf build/venv
    RECREATE_VENV=1
  fi
fi

if [ ! -x "build/venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv build/venv
fi

# Quiet successful installs; stderr still shows failures
build/venv/bin/python -m pip install --upgrade pip >/dev/null
build/venv/bin/python -m pip install -e . >/dev/null

# Expose a stable bin path
(cd build && ln -sfn venv/bin bin)

echo "Talos ready: $SCRIPT_DIR/build/bin/talos"
