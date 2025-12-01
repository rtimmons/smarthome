#!/usr/bin/env bash
set -euo pipefail

# Self-contained nvm usage script for the smarthome project
# This script uses the nvm installation in build/nvm/ without relying on system nvm

# Error handler to provide context
error_exit() {
  echo "ERROR in nvm_use.sh at line $1: $2" >&2
  exit 1
}

trap 'error_exit ${LINENO} "Script failed"' ERR

echo "[nvm_use] Starting nvm initialization..." >&2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || error_exit ${LINENO} "Failed to determine script directory"
echo "[nvm_use] Script directory: $SCRIPT_DIR" >&2

# Allow REPO_ROOT to be overridden for testing
if [ -z "${REPO_ROOT:-}" ]; then
  if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    :
  else
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
  fi
fi
echo "[nvm_use] Repository root: $REPO_ROOT" >&2

DEFAULT_NVMRC="$REPO_ROOT/.nvmrc"
LOCAL_NVMRC="$(pwd)/.nvmrc"

if [ -z "${NVM_VERSION_FILE:-}" ]; then
  if [ -f "$LOCAL_NVMRC" ]; then
    NVM_VERSION_FILE="$LOCAL_NVMRC"
  else
    NVM_VERSION_FILE="$DEFAULT_NVMRC"
  fi
fi
echo "[nvm_use] Using version file: $NVM_VERSION_FILE" >&2

if [ ! -f "$NVM_VERSION_FILE" ]; then
  error_exit ${LINENO} "Missing $NVM_VERSION_FILE; cannot select Node runtime."
fi

# Use self-contained nvm directory (not in user's home)
export NVM_DIR="$REPO_ROOT/build/nvm"
NVM_SH="$NVM_DIR/nvm-src/nvm.sh"
echo "[nvm_use] NVM_DIR: $NVM_DIR" >&2
echo "[nvm_use] Looking for nvm.sh at: $NVM_SH" >&2

# Ensure nvm is installed
if [ ! -f "$NVM_SH" ]; then
  echo "[nvm_use] nvm not found; installing..." >&2
  "$SCRIPT_DIR/setup_nvm.sh" || error_exit ${LINENO} "Failed to install nvm via setup_nvm.sh"
fi

# Verify nvm.sh exists after setup
if [ ! -f "$NVM_SH" ]; then
  error_exit ${LINENO} "nvm.sh still not found at $NVM_SH after setup"
fi

echo "[nvm_use] Sourcing nvm.sh..." >&2
# Source nvm (disable errexit temporarily to handle nvm.sh's internal logic)
set +e
. "$NVM_SH"
SOURCE_EXIT=$?
set -e

if [ $SOURCE_EXIT -ne 0 ]; then
  error_exit ${LINENO} "Failed to source $NVM_SH (exit code: $SOURCE_EXIT)"
fi

# Verify nvm is available
echo "[nvm_use] Verifying nvm command is available..." >&2
if ! command -v nvm >/dev/null 2>&1; then
  error_exit ${LINENO} "nvm command not available after sourcing $NVM_SH"
fi

# Install and use the required Node.js version
required=$(tr -d '[:space:]' < "$NVM_VERSION_FILE")
echo "[nvm_use] Required Node.js version: $required" >&2

if [ "$(nvm version "$required" 2>/dev/null || echo N/A)" = "N/A" ]; then
  echo "[nvm_use] Installing Node $required via nvm..." >&2
  nvm install "$required" || error_exit ${LINENO} "Failed to install Node $required"
fi

# Activate the required version
echo "[nvm_use] Activating Node $required..." >&2
if ! nvm use --silent "$required" >/dev/null 2>&1; then
  echo "[nvm_use] Node $required not active; installing again..." >&2
  nvm install "$required" || error_exit ${LINENO} "Failed to reinstall Node $required"
  nvm use --silent "$required" >/dev/null || error_exit ${LINENO} "nvm use failed after reinstall"
fi

echo "[nvm_use] Successfully initialized Node.js $(node --version 2>/dev/null || echo 'unknown')" >&2
