#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPRESS_ROOT="${REPO_ROOT}/ExpressServer"
ADDON_SLUG="grid_dashboard"
ADDON_NAME="Grid Dashboard"
DIST_ROOT="${REPO_ROOT}/build/home-assistant-addon"
ADDON_ROOT="${DIST_ROOT}/${ADDON_SLUG}"
APP_SRC_DIR="${ADDON_ROOT}/app"

read_package_version() {
  node -e "console.log(require(process.argv[1]).version)" "$1" 2>/dev/null || echo "0.0.0"
}

log() {
  echo "[$(date +"%H:%M:%S")] $*"
}

PACKAGE_VERSION="$(read_package_version "${EXPRESS_ROOT}/package.json")"

log "Preparing Home Assistant add-on payload at ${ADDON_ROOT}"
rm -rf "${ADDON_ROOT}"
mkdir -p \
  "${APP_SRC_DIR}/src" \
  "${ADDON_ROOT}/translations"

if [ ! -d "${EXPRESS_ROOT}/src" ]; then
  echo "ExpressServer sources not found at ${EXPRESS_ROOT}" >&2
  exit 1
fi

log "Copying ExpressServer sources"
rsync -a \
  --delete \
  --exclude 'node_modules' \
  --exclude 'dist' \
  "${EXPRESS_ROOT}/src/" "${APP_SRC_DIR}/src/"
cp "${EXPRESS_ROOT}/package.json" "${APP_SRC_DIR}/"
cp "${EXPRESS_ROOT}/package-lock.json" "${APP_SRC_DIR}/"
cp "${EXPRESS_ROOT}/tsconfig.json" "${APP_SRC_DIR}/"
cp "${EXPRESS_ROOT}/prettier.config.js" "${APP_SRC_DIR}/" 2>/dev/null || true

CONFIG_PATH="${ADDON_ROOT}/config.yaml"
log "Writing ${CONFIG_PATH}"
cat >"${CONFIG_PATH}" <<EOF
name: "${ADDON_NAME}"
version: "${PACKAGE_VERSION}"
slug: "${ADDON_SLUG}"
description: "Dashboard UI with Sonos shortcuts and Home Assistant webhook helpers."
url: "https://github.com/rtimmons/smarthome"
arch:
  - aarch64
  - amd64
  - armv7
  - armhf
  - i386
startup: services
ingress: true
ingress_port: 3000
ingress_entry: "/"
panel_icon: "mdi:view-dashboard"
panel_title: "Grid Dashboard"
init: false
homeassistant_api: true
auth_api: false
ports:
  3000/tcp: 3000
ports_description:
  3000/tcp: "Optional host port for direct access (ingress is enabled by default)."
homeassistant: "2024.6.0"
environment:
  NODE_OPTIONS: "--enable-source-maps"
  INGRESS_ENTRY: "/api/hassio_ingress"
options:
  sonos_base_url: "http://local-sonos-api:5006"
  webhook_base: ""
schema:
  sonos_base_url: "str?"
  webhook_base: "str?"
EOF

DOCKERFILE_PATH="${ADDON_ROOT}/Dockerfile"
log "Writing ${DOCKERFILE_PATH}"
cat >"${DOCKERFILE_PATH}" <<'EOF'
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
WORKDIR /opt/grid-dashboard/app

RUN apk add --no-cache nodejs npm

COPY app/ /opt/grid-dashboard/app/
RUN npm ci && npm cache clean --force

COPY run.sh /
RUN chmod a+x /run.sh

EXPOSE 3000

CMD ["/run.sh"]
EOF

RUN_SCRIPT_PATH="${ADDON_ROOT}/run.sh"
log "Writing ${RUN_SCRIPT_PATH}"
cat >"${RUN_SCRIPT_PATH}" <<'EOF'
#!/usr/bin/with-contenv bashio
set -euo pipefail

PORT="3000"
SONOS_BASE="$(bashio::config 'sonos_base_url' 2>/dev/null || true)"
WEBHOOK_BASE="$(bashio::config 'webhook_base' 2>/dev/null || true)"

SONOS_BASE="${SONOS_BASE:-http://local-sonos-api:5006}"

export PORT
export APP_PORT="${PORT}"
export SONOS_BASE_URL="${SONOS_BASE}"
if [ -n "${WEBHOOK_BASE:-}" ]; then
  export HASS_WEBHOOK_BASE="${WEBHOOK_BASE}"
fi

cd /opt/grid-dashboard/app
bashio::log.info "Starting Grid Dashboard on port ${PORT}"
exec npm start
EOF

README_PATH="${ADDON_ROOT}/README.md"
log "Writing ${README_PATH}"
cat >"${README_PATH}" <<'EOF'
# Grid Dashboard Home Assistant Add-on

Local add-on that exposes the Express-based grid dashboard UI with ingress support. Access the dashboard directly from the Home Assistant sidebar, or use the Sonos helper routes and convenience redirects.
EOF

DOCS_PATH="${ADDON_ROOT}/DOCS.md"
log "Writing ${DOCS_PATH}"
cat >"${DOCS_PATH}" <<'EOF'
# Grid Dashboard Add-on

This add-on packages the ExpressServer dashboard for Home Assistant, providing easy access to the dashboard UI, Sonos controls, and Home Assistant webhook helpers through the Home Assistant interface.

## Installation

1. Generate the add-on payload with `just ha-addon` (see the Justfile in this folder).
2. Copy the generated `grid_dashboard` folder or the tarball from `build/home-assistant-addon/` to your Home Assistant host under `/addons/`.
3. In Home Assistant, open **Settings → Add-ons → Add-on Store**, click **Check for updates**, then install **Grid Dashboard** from **Local add-ons**.
4. Start the add-on.

## Access

- **Preferred**: Use the add-on ingress link from the Home Assistant sidebar. After installation, click "Grid Dashboard" in the sidebar to open the UI.
- **Alternative**: Access directly via `http://<ha-host>:3000/` if you need to bypass ingress (port 3000 is exposed by default).

## Configuration

- `sonos_base_url`: Base URL for the Sonos API service. Default `http://local-sonos-api:5006`.
  - The Sonos API add-on provides custom routes and proxies to the Node Sonos HTTP API add-on
- `webhook_base`: Optional override for Home Assistant webhooks. Leave blank to use the supervisor proxy.

The add-on enables ingress by default, making it accessible through the Home Assistant interface. The sidebar panel provides quick access to the dashboard.
EOF

CHANGELOG_PATH="${ADDON_ROOT}/CHANGELOG.md"
log "Writing ${CHANGELOG_PATH}"
cat >"${CHANGELOG_PATH}" <<EOF
## ${PACKAGE_VERSION}

- Initial Home Assistant add-on packaging for Grid Dashboard.
EOF

APPARMOR_PATH="${ADDON_ROOT}/apparmor.txt"
log "Writing ${APPARMOR_PATH}"
cat >"${APPARMOR_PATH}" <<'EOF'
#include <tunables/global>

profile grid_dashboard flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  file,
  capability net_bind_service,

  /init ix,
  /bin/** ix,
  /usr/bin/** ix,
  /run/{s6,s6-rc*,service}/** ix,
  /package/** ix,
  /command/** ix,
  /etc/services.d/** rwix,
  /etc/cont-init.d/** rwix,
  /etc/cont-finish.d/** rwix,
  /run/{,**} rwk,
  /tmp/** rwk,

  /usr/lib/bashio/** ix,
  /data/** rw,
  /share/** rw,

  /usr/bin/node ix,
  /usr/bin/npm ix,
  /opt/grid-dashboard/app/** rwix,
}
EOF

TRANSLATIONS_PATH="${ADDON_ROOT}/translations/en.yaml"
log "Writing ${TRANSLATIONS_PATH}"
cat >"${TRANSLATIONS_PATH}" <<'EOF'
configuration:
  sonos_base_url:
    name: Sonos API base URL
    description: Base URL for node-sonos-http-api (e.g., http://node-sonos-http-api:5005).
  webhook_base:
    name: Webhook base URL
    description: Optional override for Home Assistant webhook calls; leave empty to use supervisor proxy.
EOF

generate_pngs() {
  python3 - "$ADDON_ROOT" <<'PY'
import base64
from pathlib import Path
import sys

root = Path(sys.argv[1])
icon = root / "icon.png"
logo = root / "logo.png"

placeholder = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAIwAAACMCAYAAAB1Hg1ZAAAABmJLR0QA/wD/AP+gvaeTAAABhUlEQVR4nO3aPW7CMBQG4M3lDAZhgXcwiAIwJgrAHRhBsENwDozBCnSlYB5iM5dfHpuO83I5ZrSX7/y3t59n9/PNHtq5VABERERERERERETkFy8A+gN1M1vHM/4O1Zhq6B3QK9jFrZqdd3kc1oAuY4ZrXtUa6PbUDrCOatbfRQuwN1kHtrTxBEcX3W6DBZR264yugPVkHYqVvRCuwR1kHarkgAV6HoUDLVKixj0J6gDtZB2Klb0QrsEdZB2rpJAFel6FAy1SosY9CeoA7WQdiplFRAb0DuoA7WQdiqW0gZ6BzUBoqVNRCewO6CDtZD0qVn0gY6BzUBoqVNRCewO6CDtZD0qVn0gY6BzUBoqVNRCewO6CDtZB2KpbSBnoHNAaKlT0QnsDugg7WQ9Kla9ICNUAZ7Bf0yu9oJvhYpoRERERERERERkd4TB5g2bgDW2lzQAAAABJRU5ErkJggg=="
)

def ensure_png(path: Path):
    if not path.exists():
        path.write_bytes(placeholder)

ensure_png(icon)
ensure_png(logo)
PY
}

log "Generating placeholder icon and logo"
generate_pngs

log "Packaging tarball"
mkdir -p "${DIST_ROOT}"
(cd "${DIST_ROOT}" && tar -czf "${ADDON_SLUG}.tar.gz" "${ADDON_SLUG}")

log "Add-on artifacts ready:"
log " - ${ADDON_ROOT}"
log " - ${DIST_ROOT}/${ADDON_SLUG}.tar.gz"
