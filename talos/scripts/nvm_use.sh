#!/usr/bin/env bash
set -euo pipefail

# Self-contained nvm usage script for the smarthome project
# This script uses the nvm installation in build/nvm/ without relying on system nvm

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Allow REPO_ROOT to be overridden for testing
if [ -z "${REPO_ROOT:-}" ]; then
  if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    :
  else
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
  fi
fi

DEFAULT_NVMRC="$REPO_ROOT/.nvmrc"
LOCAL_NVMRC="$(pwd)/.nvmrc"

if [ -z "${NVM_VERSION_FILE:-}" ]; then
  if [ -f "$LOCAL_NVMRC" ]; then
    NVM_VERSION_FILE="$LOCAL_NVMRC"
  else
    NVM_VERSION_FILE="$DEFAULT_NVMRC"
  fi
fi

if [ ! -f "$NVM_VERSION_FILE" ]; then
  echo "Missing $NVM_VERSION_FILE; cannot select Node runtime." >&2
  exit 1
fi

# Use self-contained nvm directory (not in user's home)
export NVM_DIR="$REPO_ROOT/build/nvm"
NVM_SH="$NVM_DIR/nvm-src/nvm.sh"

# Ensure nvm is installed
if [ ! -f "$NVM_SH" ]; then
  echo "nvm not found at $NVM_SH; installing..." >&2
  if ! "$SCRIPT_DIR/setup_nvm.sh"; then
    echo "Failed to install nvm" >&2
    exit 1
  fi
fi

# Verify nvm.sh exists after setup
if [ ! -f "$NVM_SH" ]; then
  echo "nvm.sh still not found after setup; something went wrong" >&2
  exit 1
fi

# Source nvm
. "$NVM_SH"

# Verify nvm is available
if ! command -v nvm >/dev/null 2>&1; then
  echo "nvm command not available after sourcing $NVM_SH" >&2
  exit 1
fi

# Install and use the required Node.js version
required=$(tr -d '[:space:]' < "$NVM_VERSION_FILE")

if [ "$(nvm version "$required" 2>/dev/null || echo N/A)" = "N/A" ]; then
  echo "Installing Node $required via nvm..." >&2
  nvm install "$required"
fi

# Activate the required version
if ! nvm use --silent "$required" >/dev/null 2>&1; then
  echo "Node $required not active; installing now via nvm..." >&2
  nvm install "$required"
  nvm use --silent "$required" >/dev/null || {
    echo "nvm use failed after install; check nvm setup" >&2
    exit 1
  }
fi
