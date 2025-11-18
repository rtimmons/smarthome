#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADDON_SLUG="sonos_api"
ADDON_NAME="Sonos API"
DIST_ROOT="${REPO_ROOT}/build/home-assistant-addon"
ADDON_ROOT="${DIST_ROOT}/${ADDON_SLUG}"
APP_SRC_DIR="${ADDON_ROOT}/app"

read_package_version() {
  node -e "console.log(require(process.argv[1]).version)" "$1" 2>/dev/null || echo "0.0.0"
}

log() {
  echo "[$(date +"%H:%M:%S")] $*"
}

PACKAGE_VERSION="$(read_package_version "${REPO_ROOT}/package.json")"

log "Preparing Home Assistant add-on payload at ${ADDON_ROOT}"
rm -rf "${ADDON_ROOT}"
mkdir -p \
  "${APP_SRC_DIR}/src" \
  "${ADDON_ROOT}/translations"

if [ ! -d "${REPO_ROOT}/src" ]; then
  echo "Sonos API sources not found at ${REPO_ROOT}/src" >&2
  exit 1
fi

log "Copying Sonos API sources"
rsync -a \
  --delete \
  --exclude 'node_modules' \
  --exclude 'dist' \
  "${REPO_ROOT}/src/" "${APP_SRC_DIR}/src/"
cp "${REPO_ROOT}/package.json" "${APP_SRC_DIR}/"
cp "${REPO_ROOT}/package-lock.json" "${APP_SRC_DIR}/"
cp "${REPO_ROOT}/tsconfig.json" "${APP_SRC_DIR}/"

CONFIG_PATH="${ADDON_ROOT}/config.yaml"
log "Writing ${CONFIG_PATH}"
cat >"${CONFIG_PATH}" <<EOF
name: "${ADDON_NAME}"
version: "${PACKAGE_VERSION}"
slug: "${ADDON_SLUG}"
description: "Proxy API for node-sonos-http-api with custom routes and helpers."
url: "https://github.com/rtimmons/smarthome"
arch:
  - aarch64
  - amd64
  - armv7
  - armhf
  - i386
startup: services
ingress: false
init: false
homeassistant_api: false
auth_api: false
ports:
  5006/tcp: 5006
ports_description:
  5006/tcp: "Sonos API HTTP port"
homeassistant: "2024.6.0"
environment:
  NODE_OPTIONS: "--enable-source-maps"
options:
  sonos_base_url: "http://node-sonos-http-api:5005"
schema:
  sonos_base_url: "str?"
EOF

DOCKERFILE_PATH="${ADDON_ROOT}/Dockerfile"
log "Writing ${DOCKERFILE_PATH}"
cat >"${DOCKERFILE_PATH}" <<'EOF'
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
WORKDIR /opt/sonos-api/app

RUN apk add --no-cache nodejs npm

COPY app/ /opt/sonos-api/app/
RUN npm ci && npm run build && npm cache clean --force

COPY run.sh /
RUN chmod a+x /run.sh

EXPOSE 5006

CMD ["/run.sh"]
EOF

RUN_SCRIPT_PATH="${ADDON_ROOT}/run.sh"
log "Writing ${RUN_SCRIPT_PATH}"
cat >"${RUN_SCRIPT_PATH}" <<'EOF'
#!/usr/bin/with-contenv bashio
set -euo pipefail

PORT="5006"
SONOS_BASE="$(bashio::config 'sonos_base_url' 2>/dev/null || true)"

SONOS_BASE="${SONOS_BASE:-http://node-sonos-http-api:5005}"

export PORT
export APP_PORT="${PORT}"
export SONOS_BASE_URL="${SONOS_BASE}"

cd /opt/sonos-api/app
bashio::log.info "Starting Sonos API on port ${PORT}"
exec npm start
EOF

README_PATH="${ADDON_ROOT}/README.md"
log "Writing ${README_PATH}"
cat >"${README_PATH}" <<'EOF'
# Sonos API Home Assistant Add-on

Local add-on that provides a proxy API for node-sonos-http-api with custom routes and helper endpoints for controlling Sonos speakers.
EOF

DOCS_PATH="${ADDON_ROOT}/DOCS.md"
log "Writing ${DOCS_PATH}"
cat >"${DOCS_PATH}" <<'EOF'
# Sonos API Add-on

This add-on provides a proxy API for node-sonos-http-api with custom routes and helper endpoints tailored for controlling Sonos speakers in your smart home setup.

## Installation

1. Generate the add-on payload with `just ha-addon` (see the Justfile in this folder).
2. Copy the generated `sonos_api` folder or the tarball from `build/home-assistant-addon/` to your Home Assistant host under `/addons/`.
3. In Home Assistant, open **Settings → Add-ons → Add-on Store**, click **Check for updates**, then install **Sonos API** from **Local add-ons**.
4. Start the add-on.

## Access

Access the API at `http://<ha-host>:5006/` or use it from other add-ons via `http://sonos-api:5006/`.

## Configuration

- `sonos_base_url`: Base URL for the upstream `node-sonos-http-api` service. Default `http://node-sonos-http-api:5005`.

## API Routes

- `/pause` - Pause playback
- `/play` - Resume playback
- `/tv` - Switch all speakers to TV mode
- `/07` - Play Zero 7 Radio
- `/quiet` - Set group volume to 7
- `/same/:room` - Sync all room volumes in the same zone
- `/down` - Smart volume down (pause if volume <= 3 and playing)
- `/up` - Smart volume up (play if paused, otherwise increase volume)
- `/sonos/*` - Proxy any request to the underlying node-sonos-http-api
- `/health` - Health check endpoint
EOF

CHANGELOG_PATH="${ADDON_ROOT}/CHANGELOG.md"
log "Writing ${CHANGELOG_PATH}"
cat >"${CHANGELOG_PATH}" <<EOF
## ${PACKAGE_VERSION}

- Initial Home Assistant add-on packaging for Sonos API.
EOF

APPARMOR_PATH="${ADDON_ROOT}/apparmor.txt"
log "Writing ${APPARMOR_PATH}"
cat >"${APPARMOR_PATH}" <<'EOF'
#include <tunables/global>

profile sonos_api flags=(attach_disconnected,mediate_deleted) {
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

  /usr/bin/node ix,
  /usr/bin/npm ix,
  /opt/sonos-api/app/** rwix,
}
EOF

TRANSLATIONS_PATH="${ADDON_ROOT}/translations/en.yaml"
log "Writing ${TRANSLATIONS_PATH}"
cat >"${TRANSLATIONS_PATH}" <<'EOF'
configuration:
  sonos_base_url:
    name: Sonos API base URL
    description: Base URL for node-sonos-http-api (e.g., http://node-sonos-http-api:5005).
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
