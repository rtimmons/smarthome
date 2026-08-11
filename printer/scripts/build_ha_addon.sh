#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TALOS_BIN="${WORKSPACE_ROOT}/talos/build/bin/talos"

if [ ! -x "${TALOS_BIN}" ]; then
  "${WORKSPACE_ROOT}/talos/build.sh"
fi

echo "[printer] Building with the repository's locked Talos add-on pipeline." >&2
exec "${TALOS_BIN}" addon build printer
