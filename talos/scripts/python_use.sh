#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

DEFAULT_PY_VERSION_FILE="$REPO_ROOT/.python-version"
LOCAL_PY_VERSION_FILE="$(pwd)/.python-version"

if [ -z "${PY_VERSION_FILE:-}" ]; then
  if [ -f "$LOCAL_PY_VERSION_FILE" ]; then
    PY_VERSION_FILE="$LOCAL_PY_VERSION_FILE"
  else
    PY_VERSION_FILE="$DEFAULT_PY_VERSION_FILE"
  fi
fi

if [ ! -f "$PY_VERSION_FILE" ]; then
  echo "Missing $PY_VERSION_FILE; cannot select Python runtime." >&2
  exit 1
fi

PY_VERSION="$(tr -d '[:space:]' < "$PY_VERSION_FILE")"
TALOS_PYTHON_BIN=""
PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"

ensure_pyenv_available() {
  if command -v pyenv >/dev/null 2>&1; then
    return 0
  fi

  if [ "${TALOS_PYENV_SKIP_INSTALL:-0}" = "1" ]; then
    return 1
  fi

  if command -v brew >/dev/null 2>&1; then
    echo "Installing pyenv via Homebrew (one-time)..." >&2
    if HOMEBREW_NO_AUTO_UPDATE=1 brew install pyenv >/dev/null; then
      return 0
    fi
  fi

  return 1
}

if ensure_pyenv_available; then
  # Prefer pyenv-managed Python; install quietly if missing.
  PYENV_VERSION="$PY_VERSION" pyenv install -s "$PY_VERSION" >/dev/null 2>&1 || true
  TALOS_PYTHON_BIN="$(PYENV_VERSION="$PY_VERSION" pyenv which python 2>/dev/null || true)"
  if [ -z "${TALOS_PYTHON_BIN:-}" ]; then
    echo "pyenv could not provide Python $PY_VERSION; ensure it is installed (pyenv install $PY_VERSION)." >&2
    exit 1
  fi
else
  if command -v python3 >/dev/null 2>&1; then
    TALOS_PYTHON_BIN="$(command -v python3)"
  fi

  if [ -z "${TALOS_PYTHON_BIN:-}" ]; then
    echo "Python $PY_VERSION not found; install via pyenv or your package manager." >&2
    exit 1
  fi

  actual_version="$("$TALOS_PYTHON_BIN" --version 2>&1 | awk 'NR==1{print $2}')"
  required_major_minor="$(echo "$PY_VERSION" | cut -d. -f1-2)"
  actual_major_minor="$(echo "$actual_version" | cut -d. -f1-2)"

  if [ "$required_major_minor" != "$actual_major_minor" ]; then
    echo "Python version mismatch: required $PY_VERSION (major.minor $required_major_minor), found $actual_version at $TALOS_PYTHON_BIN" >&2
    echo "Install the required version via pyenv (preferred) or adjust your PATH." >&2
    exit 1
  fi
fi

export TALOS_PYTHON_VERSION="$PY_VERSION"
export TALOS_PYTHON_BIN

talos_ensure_venv() {
  local venv_dir="${1:-.venv}"
  local py_bin="${TALOS_PYTHON_BIN}"
  if [ -x "$venv_dir/bin/python" ]; then
    local current="$("$venv_dir/bin/python" --version 2>&1 | awk 'NR==1{print $2}')"
    local current_mm="$(echo "$current" | cut -d. -f1-2)"
    local required_mm="$(echo "$PY_VERSION" | cut -d. -f1-2)"
    if [ "$current_mm" != "$required_mm" ]; then
      rm -rf "$venv_dir"
    fi
  fi
  if [ ! -d "$venv_dir" ]; then
    "$py_bin" -m venv "$venv_dir"
  fi
  if [ ! -x "$venv_dir/bin/pip" ]; then
    "$venv_dir/bin/python" -m ensurepip --upgrade >/dev/null
  fi
}
