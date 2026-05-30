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

debug() {
  if [ "${NVM_USE_DEBUG:-0}" = "1" ]; then
    echo "[nvm_use] $*" >&2
  fi
}

debug "Starting nvm initialization..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || error_exit ${LINENO} "Failed to determine script directory"
debug "Script directory: $SCRIPT_DIR"

# Allow REPO_ROOT to be overridden for testing
if [ -z "${REPO_ROOT:-}" ]; then
  if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    :
  else
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
  fi
fi
debug "Repository root: $REPO_ROOT"

DEFAULT_NVMRC="$REPO_ROOT/.nvmrc"
LOCAL_NVMRC="$(pwd)/.nvmrc"

if [ -z "${NVM_VERSION_FILE:-}" ]; then
  if [ -f "$LOCAL_NVMRC" ]; then
    NVM_VERSION_FILE="$LOCAL_NVMRC"
  else
    NVM_VERSION_FILE="$DEFAULT_NVMRC"
  fi
fi
debug "Using version file: $NVM_VERSION_FILE"

if [ ! -f "$NVM_VERSION_FILE" ]; then
  error_exit ${LINENO} "Missing $NVM_VERSION_FILE; cannot select Node runtime."
fi

# Use self-contained nvm directory (not in user's home)
export NVM_DIR="$REPO_ROOT/build/nvm"
NVM_SH="$NVM_DIR/nvm-src/nvm.sh"
debug "NVM_DIR: $NVM_DIR"
debug "Looking for nvm.sh at: $NVM_SH"

# Ensure nvm is installed
if [ ! -f "$NVM_SH" ]; then
  debug "nvm not found; installing..."
  "$SCRIPT_DIR/setup_nvm.sh" || error_exit ${LINENO} "Failed to install nvm via setup_nvm.sh"
fi

# Verify nvm.sh exists after setup
if [ ! -f "$NVM_SH" ]; then
  error_exit ${LINENO} "nvm.sh still not found at $NVM_SH after setup"
fi

debug "Sourcing nvm.sh with --no-use..."
# Source nvm with --no-use flag to prevent auto-activation of .nvmrc versions
# On fresh machines, nvm.sh tries to auto-activate the version in .nvmrc during sourcing,
# which fails if Node.js isn't installed yet. --no-use prevents this behavior.

# Create a temporary file to capture nvm.sh stderr
NVM_SOURCE_LOG=$(mktemp)

set +eE
trap - ERR

# Redirect stderr to temp file while sourcing, then restore stderr
exec 3>&2 2>"$NVM_SOURCE_LOG"
. "$NVM_SH" --no-use
SOURCE_EXIT=$?
exec 2>&3 3>&-

set -e
trap 'error_exit ${LINENO} "Script failed"' ERR

if [ $SOURCE_EXIT -ne 0 ]; then
  echo "[nvm_use] nvm.sh failed with exit code $SOURCE_EXIT" >&2
  if [ -s "$NVM_SOURCE_LOG" ]; then
    echo "[nvm_use] nvm.sh error output:" >&2
    cat "$NVM_SOURCE_LOG" >&2
  else
    echo "[nvm_use] nvm.sh produced no error output (silent failure)" >&2
    echo "[nvm_use] This usually means a command inside nvm.sh failed without printing an error" >&2
    echo "[nvm_use] Common causes: missing dependencies (curl/wget), PATH issues, or shell incompatibilities" >&2
  fi
  rm -f "$NVM_SOURCE_LOG"
  error_exit ${LINENO} "Failed to source $NVM_SH (exit code: $SOURCE_EXIT)"
fi

rm -f "$NVM_SOURCE_LOG"

# Verify nvm is available
debug "Verifying nvm command is available..."
if ! command -v nvm >/dev/null 2>&1; then
  error_exit ${LINENO} "nvm command not available after sourcing $NVM_SH"
fi

# Install and use the required Node.js version
required=$(tr -d '[:space:]' < "$NVM_VERSION_FILE")
debug "Required Node.js version: $required"

if [ "$(nvm version "$required" 2>/dev/null || echo N/A)" = "N/A" ]; then
  debug "Installing Node $required via nvm..."
  nvm install "$required" || error_exit ${LINENO} "Failed to install Node $required"
fi

# Activate the required version
debug "Activating Node $required..."
if ! nvm use --silent "$required" >/dev/null 2>&1; then
  debug "Node $required not active; installing again..."
  nvm install "$required" || error_exit ${LINENO} "Failed to reinstall Node $required"
  nvm use --silent "$required" >/dev/null || error_exit ${LINENO} "nvm use failed after reinstall"
fi

debug "Successfully initialized Node.js $(node --version 2>/dev/null || echo 'unknown')"
