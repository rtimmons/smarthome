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

# Initialize pyenv if present, prefer user installation.
if [ -z "${PYENV_ROOT:-}" ] && [ -d "$HOME/.pyenv" ]; then
  export PYENV_ROOT="$HOME/.pyenv"
fi
if [ -n "${PYENV_ROOT:-}" ] && [ -d "$PYENV_ROOT/bin" ]; then
  export PATH="$PYENV_ROOT/bin:$PATH"
fi
if command -v pyenv >/dev/null 2>&1; then
  eval "$(pyenv init -)" >/dev/null 2>&1 || true
fi

if ! command -v pyenv >/dev/null 2>&1; then
  echo "pyenv is required to manage Python versions. Install pyenv and run: pyenv install $PY_VERSION" >&2
  exit 1
fi

PYENV_HAS_INSTALL=0
if pyenv commands 2>/dev/null | grep -qx install; then
  PYENV_HAS_INSTALL=1
fi

pyenv_root="$(pyenv root 2>/dev/null || true)"
if [ -z "$pyenv_root" ]; then
  pyenv_root="$HOME/.pyenv"
fi

version_dir="$pyenv_root/versions/$PY_VERSION"
needs_install=0
if ! pyenv versions --bare 2>/dev/null | grep -qx "$PY_VERSION"; then
  needs_install=1
fi
if [ ! -x "$version_dir/bin/python" ]; then
  needs_install=1
fi

if [ $needs_install -eq 1 ]; then
  if [ $PYENV_HAS_INSTALL -ne 1 ]; then
    echo "pyenv install plugin not found; install it and run: pyenv install $PY_VERSION" >&2
    exit 1
  fi
  echo "Installing Python $PY_VERSION via pyenv (one-time)..." >&2
  if ! pyenv install -s "$PY_VERSION"; then
    echo "pyenv install $PY_VERSION failed; install it manually." >&2
    exit 1
  fi
  pyenv rehash >/dev/null 2>&1 || true
fi

version_dir="$pyenv_root/versions/$PY_VERSION"
candidate_bin="$version_dir/bin/python"

if [ ! -x "$candidate_bin" ]; then
  echo "pyenv could not locate Python $PY_VERSION in $version_dir; retrying install..." >&2
  if [ $PYENV_HAS_INSTALL -ne 1 ]; then
    echo "pyenv install plugin not found; install it and run: pyenv install $PY_VERSION" >&2
    exit 1
  fi
  pyenv uninstall -f "$PY_VERSION" >/dev/null 2>&1 || true
  if ! pyenv install -s "$PY_VERSION"; then
    echo "pyenv install $PY_VERSION failed; install it manually (pyenv uninstall -f $PY_VERSION; pyenv install $PY_VERSION)." >&2
    exit 1
  fi
  pyenv rehash >/dev/null 2>&1 || true
fi

export PYENV_VERSION="$PY_VERSION"
export PATH="$version_dir/bin:$PATH"
TALOS_PYTHON_BIN="$candidate_bin"
actual_version="$("$TALOS_PYTHON_BIN" --version 2>&1 | awk 'NR==1{print $2}')"
actual_mm="$(echo "$actual_version" | cut -d. -f1-2)"
required_mm="$(echo "$PY_VERSION" | cut -d. -f1-2)"
if [ "$actual_mm" != "$required_mm" ]; then
  echo "pyenv resolved to $actual_version (expected $PY_VERSION); adjust your pyenv install." >&2
  exit 1
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
