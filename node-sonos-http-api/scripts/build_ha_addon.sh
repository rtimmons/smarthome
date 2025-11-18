#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADDON_SLUG="node_sonos_http_api"
ADDON_NAME="Node Sonos HTTP API"
DIST_ROOT="${REPO_ROOT}/build/home-assistant-addon"
ADDON_ROOT="${DIST_ROOT}/${ADDON_SLUG}"

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
  "${ADDON_ROOT}/translations"

CONFIG_PATH="${ADDON_ROOT}/config.yaml"
log "Writing ${CONFIG_PATH}"
cat >"${CONFIG_PATH}" <<EOF
name: "${ADDON_NAME}"
version: "${PACKAGE_VERSION}"
slug: "${ADDON_SLUG}"
description: "The actual node-sonos-http-api server for controlling Sonos speakers via HTTP"
url: "https://github.com/jishi/node-sonos-http-api"
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
host_network: true
ports:
  5005/tcp: 5005
ports_description:
  5005/tcp: "Node Sonos HTTP API port"
homeassistant: "2024.6.0"
environment:
  NODE_OPTIONS: "--enable-source-maps"
options:
  sonos_discovery_timeout: 5
schema:
  sonos_discovery_timeout: "int?"
EOF

DOCKERFILE_PATH="${ADDON_ROOT}/Dockerfile"
log "Writing ${DOCKERFILE_PATH}"
cat >"${DOCKERFILE_PATH}" <<'EOF'
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
WORKDIR /app

# Install Node.js, npm, and git
RUN apk add --no-cache nodejs npm git

# Clone the node-sonos-http-api repository
RUN git clone https://github.com/jishi/node-sonos-http-api.git /app && \
    cd /app && \
    npm install --production && \
    npm cache clean --force

COPY run.sh /
RUN chmod a+x /run.sh

EXPOSE 5005

CMD ["/run.sh"]
EOF

RUN_SCRIPT_PATH="${ADDON_ROOT}/run.sh"
log "Writing ${RUN_SCRIPT_PATH}"
cat >"${RUN_SCRIPT_PATH}" <<'EOF'
#!/usr/bin/with-contenv bashio
set -euo pipefail

PORT="5005"
DISCOVERY_TIMEOUT="$(bashio::config 'sonos_discovery_timeout' 2>/dev/null || echo '5')"

export PORT
export SONOS_DISCOVERY_TIMEOUT="${DISCOVERY_TIMEOUT}"

cd /app
bashio::log.info "Starting Node Sonos HTTP API on port ${PORT}"
bashio::log.info "Discovery timeout: ${DISCOVERY_TIMEOUT} seconds"
exec npm start
EOF

README_PATH="${ADDON_ROOT}/README.md"
log "Writing ${README_PATH}"
cat >"${README_PATH}" <<'EOF'
# Node Sonos HTTP API Home Assistant Add-on

Local add-on that runs the node-sonos-http-api server for controlling Sonos speakers via HTTP API.

This is the actual Sonos HTTP API server that other add-ons (like the Sonos API proxy) can communicate with.
EOF

DOCS_PATH="${ADDON_ROOT}/DOCS.md"
log "Writing ${DOCS_PATH}"
cat >"${DOCS_PATH}" <<'EOF'
# Node Sonos HTTP API Add-on

This add-on runs the node-sonos-http-api server, which provides a simple HTTP API for controlling Sonos speakers on your network.

## Installation

1. Generate the add-on payload with `just ha-addon` (see the Justfile in this folder).
2. Copy the generated `node_sonos_http_api` folder or the tarball from `build/home-assistant-addon/` to your Home Assistant host under `/addons/`.
3. In Home Assistant, open **Settings → Add-ons → Add-on Store**, click **Check for updates**, then install **Node Sonos HTTP API** from **Local add-ons**.
4. Start the add-on.

## Access

The API will be available at `http://<ha-host>:5005/` or from other add-ons via `http://node-sonos-http-api:5005/`.

## Configuration

- `sonos_discovery_timeout`: Timeout in seconds for discovering Sonos speakers on the network (default: 5).

## API Documentation

For full API documentation, see the upstream project: https://github.com/jishi/node-sonos-http-api

## Common Endpoints

- `/<room>/play` - Start playback in a room
- `/<room>/pause` - Pause playback in a room
- `/<room>/volume/<level>` - Set volume (0-100)
- `/<room>/state` - Get current state of a room
- `/zones` - Get information about all zones
- `/preset/<preset-name>` - Activate a preset
EOF

CHANGELOG_PATH="${ADDON_ROOT}/CHANGELOG.md"
log "Writing ${CHANGELOG_PATH}"
cat >"${CHANGELOG_PATH}" <<EOF
## ${PACKAGE_VERSION}

- Initial Home Assistant add-on packaging for node-sonos-http-api.
EOF

APPARMOR_PATH="${ADDON_ROOT}/apparmor.txt"
log "Writing ${APPARMOR_PATH}"
cat >"${APPARMOR_PATH}" <<'EOF'
#include <tunables/global>

profile node_sonos_http_api flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  file,
  network inet stream,
  network inet6 stream,
  network inet dgram,
  network inet6 dgram,
  capability net_bind_service,
  capability net_raw,

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
  /app/** rwix,
}
EOF

TRANSLATIONS_PATH="${ADDON_ROOT}/translations/en.yaml"
log "Writing ${TRANSLATIONS_PATH}"
cat >"${TRANSLATIONS_PATH}" <<'EOF'
configuration:
  sonos_discovery_timeout:
    name: Sonos discovery timeout
    description: Timeout in seconds for discovering Sonos speakers on the network.
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
