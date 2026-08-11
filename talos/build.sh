#!/usr/bin/env bash
set -euo pipefail

# Build/install talos into an isolated venv under talos/build
TALOS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$TALOS_ROOT"

# Source Python version management to ensure we use the correct Python version
source "$TALOS_ROOT/scripts/python_use.sh"
PYTHON_BIN="$TALOS_PYTHON_BIN"
mkdir -p build

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to install Talos from its lockfile; run 'just setup'." >&2
  exit 1
fi

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

# Sync the editable project and test tools from the hash-pinned uv lock.
UV_PROJECT_ENVIRONMENT="$TALOS_ROOT/build/venv" \
UV_CACHE_DIR="$TALOS_ROOT/build/uv-cache" \
UV_PYTHON_DOWNLOADS=never \
  uv sync --frozen --extra test --python "$PYTHON_BIN" >/dev/null

# Expose a stable bin path
(cd build && ln -sfn venv/bin bin)

echo "Talos ready: $TALOS_ROOT/build/bin/talos"
