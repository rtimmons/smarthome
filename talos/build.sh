#!/usr/bin/env bash
set -euo pipefail

# Build/install talos into an isolated venv under talos/build
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
mkdir -p build

if [ ! -x "build/venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv build/venv
fi

build/venv/bin/python -m pip install --upgrade pip
build/venv/bin/python -m pip install -e .

# Expose a stable bin path
(cd build && ln -sfn venv/bin bin)

echo "Talos ready: $SCRIPT_DIR/build/bin/talos"
