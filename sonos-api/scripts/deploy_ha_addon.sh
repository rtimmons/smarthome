#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADDON_SLUG="sonos_api"
ARCHIVE="${REPO_ROOT}/build/home-assistant-addon/${ADDON_SLUG}.tar.gz"

HA_HOST="${HA_HOST:-homeassistant.local}"
HA_PORT="${HA_PORT:-22}"
HA_USER="${HA_USER:-root}"

REMOTE_BASE="/root"
REMOTE_TAR="${REMOTE_BASE}/${ADDON_SLUG}.tar.gz"
REMOTE_ADDON_DIR="/addons/${ADDON_SLUG}"

log() {
  echo "[$(date +"%H:%M:%S")] $*"
}

log "Building add-on payload"
"${REPO_ROOT}/scripts/build_ha_addon.sh"

if [ ! -f "${ARCHIVE}" ]; then
  echo "Add-on archive not found at ${ARCHIVE}" >&2
  exit 1
fi

log "Copying archive to ${HA_USER}@${HA_HOST}:${REMOTE_TAR}"
scp -P "${HA_PORT}" "${ARCHIVE}" "${HA_USER}@${HA_HOST}:${REMOTE_TAR}"

log "Deploying to Home Assistant host"
ssh -p "${HA_PORT}" "${HA_USER}@${HA_HOST}" bash <<'EOF'
set -euo pipefail
ADDON_SLUG="sonos_api"
ADDON_ID="local_${ADDON_SLUG}"
REMOTE_TAR="/root/${ADDON_SLUG}.tar.gz"
REMOTE_ADDON_DIR="/addons/${ADDON_SLUG}"

ha addons stop "${ADDON_ID}" >/dev/null 2>&1 || true
ha addons uninstall "${ADDON_ID}" >/dev/null 2>&1 || true
rm -rf "${REMOTE_ADDON_DIR}"
rm -rf "/data/addons/local/${ADDON_SLUG}"
mkdir -p "/addons"
tar -xzf "${REMOTE_TAR}" -C "/addons"
rm -f "${REMOTE_TAR}"

ha addons reload
sleep 2
ha addons install "${ADDON_ID}"
ha addons start "${ADDON_ID}" || true
EOF

log "Deployment complete. The add-on should be available under Local add-ons."
