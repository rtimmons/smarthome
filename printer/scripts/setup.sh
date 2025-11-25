#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$APP_ROOT/.." && pwd)"

brew_prefix="$(brew --prefix)"
if ! brew list --formula cairo >/dev/null 2>&1; then
  HOMEBREW_NO_AUTO_UPDATE=1 brew install cairo
fi

export PKG_CONFIG_PATH="${brew_prefix}/lib/pkgconfig:${brew_prefix}/share/pkgconfig:${PKG_CONFIG_PATH:-}"

source "$REPO_ROOT/talos/scripts/python_use.sh"

venv="$APP_ROOT/.venv"
talos_ensure_venv "$venv"

venv_python="$venv/bin/python"
"$venv_python" "$APP_ROOT/scripts/bootstrap_env.py"
