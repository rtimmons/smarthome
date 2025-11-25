#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
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
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

if [ ! -f "$NVM_VERSION_FILE" ]; then
  echo "Missing $NVM_VERSION_FILE; cannot select Node runtime." >&2
  exit 1
fi

ensure_nvm() {
  if command -v nvm >/dev/null 2>&1 || [ -s "$NVM_DIR/nvm.sh" ] || [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] || [ -s "/usr/local/opt/nvm/nvm.sh" ]; then
    return
  fi

  if command -v brew >/dev/null 2>&1; then
    echo "Installing nvm via Homebrew (one-time)..." >&2
    HOMEBREW_NO_AUTO_UPDATE=1 brew install nvm || { echo "Homebrew could not install nvm; install it manually." >&2; exit 1; }
    mkdir -p "$NVM_DIR"
    return
  fi

  echo "nvm not installed; install via https://github.com/nvm-sh/nvm" >&2
  exit 1
}

load_nvm() {
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
    return 0
  fi

  # Homebrew installs nvm under its prefix; prefer that if NVM_DIR is empty.
  if command -v brew >/dev/null 2>&1; then
    local brew_prefix
    brew_prefix="$(brew --prefix nvm 2>/dev/null || true)"
    if [ -n "$brew_prefix" ] && [ -s "$brew_prefix/nvm.sh" ]; then
      mkdir -p "$NVM_DIR"
      ln -sf "$brew_prefix/nvm.sh" "$NVM_DIR/nvm.sh"
      . "$brew_prefix/nvm.sh"
      return 0
    fi
  fi

  for candidate in "/opt/homebrew/opt/nvm/nvm.sh" "/usr/local/opt/nvm/nvm.sh"; do
    if [ -s "$candidate" ]; then
      mkdir -p "$NVM_DIR"
      ln -sf "$candidate" "$NVM_DIR/nvm.sh"
      . "$candidate"
      return 0
    fi
  done

  return 1
}

ensure_nvm
if ! load_nvm; then
  echo "nvm not installed; see docs/setup.md" >&2
  exit 1
fi

required=$(tr -d '[:space:]' < "$NVM_VERSION_FILE")
if [ "$(nvm version "$required" 2>/dev/null || echo N/A)" = "N/A" ]; then
  echo "Installing Node $required via nvm..." >&2
  nvm install "$required"
fi

# If the version is still not present, attempt install once more then fail loudly.
if ! nvm use --silent "$required" >/dev/null 2>&1; then
  echo "Node $required not active; installing now via nvm..." >&2
  nvm install "$required"
  nvm use --silent "$required" >/dev/null || { echo "nvm use failed after install; check nvm setup" >&2; exit 1; }
fi
