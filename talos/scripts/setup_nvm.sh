#!/usr/bin/env bash
set -euo pipefail

# Self-contained nvm installation for the smarthome project
# This script ensures nvm is installed in build/nvm/ without relying on system nvm

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

# Pin to a specific nvm version for reproducibility
NVM_VERSION="${NVM_VERSION:-v0.40.1}"
NVM_COMMIT="${NVM_COMMIT:-179d45050be0a71fd57591b0ed8aedf9b177ba10}"
NVM_REPO="https://github.com/nvm-sh/nvm.git"

# Self-contained nvm directory (not in user's home)
export NVM_DIR="$REPO_ROOT/build/nvm"
NVM_SRC_DIR="$NVM_DIR/nvm-src"
NVM_SH="$NVM_SRC_DIR/nvm.sh"

# Create build directory if it doesn't exist
mkdir -p "$NVM_DIR"

# Check if nvm is already installed
if [ -f "$NVM_SH" ]; then
  # Verify it's the correct version
  cd "$NVM_SRC_DIR"
  CURRENT_VERSION=$(git describe --tags --exact-match 2>/dev/null || echo "unknown")
  CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

  if [ "$CURRENT_VERSION" = "$NVM_VERSION" ] && [ "$CURRENT_COMMIT" = "$NVM_COMMIT" ]; then
    echo "✓ nvm $NVM_VERSION ($NVM_COMMIT) is already installed at $NVM_SRC_DIR" >&2
    exit 0
  else
    echo "⚠ nvm version mismatch (current: $CURRENT_VERSION, expected: $NVM_VERSION)" >&2
    echo "  Removing old installation and reinstalling..." >&2
    cd "$REPO_ROOT"
    rm -rf "$NVM_SRC_DIR"
  fi
fi

# Clone nvm repository
echo "📦 Installing nvm $NVM_VERSION to $NVM_SRC_DIR..." >&2

if ! command -v git >/dev/null 2>&1; then
  echo "✗ git is required to install nvm" >&2
  exit 1
fi

# Clone with specific version
git clone --depth 1 --branch "$NVM_VERSION" "$NVM_REPO" "$NVM_SRC_DIR" >/dev/null 2>&1

if [ "$(git -C "$NVM_SRC_DIR" rev-parse HEAD)" != "$NVM_COMMIT" ]; then
  echo "✗ nvm tag $NVM_VERSION did not resolve to reviewed commit $NVM_COMMIT" >&2
  exit 1
fi

if [ ! -f "$NVM_SH" ]; then
  echo "✗ Failed to install nvm: $NVM_SH not found after clone" >&2
  exit 1
fi

echo "✓ nvm $NVM_VERSION installed successfully" >&2
echo "  Location: $NVM_SRC_DIR" >&2
echo "  Script: $NVM_SH" >&2
