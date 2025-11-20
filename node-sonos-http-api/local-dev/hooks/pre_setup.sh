#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDON_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CHECK_SCRIPT="${ADDON_DIR}/tools/check_sonos_multicast.js"

echo "[node-sonos-http-api] Validating Sonos discovery reachability..." >&2

if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is required to run the Sonos multicast probe." >&2
    exit 1
fi

node "${CHECK_SCRIPT}"
