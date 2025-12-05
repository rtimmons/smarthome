#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADDON_SLUG="printer_service"
ADDON_NAME="Printer Service"
DIST_ROOT="${REPO_ROOT}/build/home-assistant-addon"
ADDON_ROOT="${DIST_ROOT}/${ADDON_SLUG}"
APP_SRC_DIR="${ADDON_ROOT}/app"

read_pyproject_version() {
  python3 - "$REPO_ROOT/pyproject.toml" <<'PY' || echo "0.0.0"
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
raw = path.read_text()

try:
    import tomllib  # type: ignore
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        import re

        match = re.search(r'^version\s*=\s*"(?P<version>[^"]+)"', raw, re.MULTILINE)
        print(match.group("version") if match else "0.0.0")
        sys.exit(0)

data = tomllib.loads(raw)
print(data["project"]["version"])
PY
}

log() {
  echo "[$(date +"%H:%M:%S")] $*"
}

PACKAGE_VERSION="$(read_pyproject_version)"

log "Preparing Home Assistant add-on payload at ${ADDON_ROOT}"
rm -rf "${ADDON_ROOT}"
mkdir -p "${APP_SRC_DIR}" "${ADDON_ROOT}/translations"

log "Copying application sources"
rsync -a \
  --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${REPO_ROOT}/src/" "${APP_SRC_DIR}/src/"
cp "${REPO_ROOT}/pyproject.toml" "${APP_SRC_DIR}/"
cp "${REPO_ROOT}/uv.lock" "${APP_SRC_DIR}/" 2>/dev/null || true

CONFIG_PATH="${ADDON_ROOT}/config.yaml"
log "Writing ${CONFIG_PATH}"
cat >"${CONFIG_PATH}" <<EOF
name: "${ADDON_NAME}"
version: "${PACKAGE_VERSION}"
slug: "${ADDON_SLUG}"
description: "Generate and print kitchen labels via Brother/ESC/POS printers or file output."
url: "https://github.com/rtimmons/printer"
arch:
  - aarch64
  - amd64
  - armv7
  - armhf
  - i386
startup: services
ingress: true
ingress_port: 8099
ingress_entry: "/"
panel_icon: "mdi:printer"
panel_title: "Printer"
init: false
ports:
  8099/tcp: 8099
ports_description:
  8099/tcp: "Optional host port for direct access (ingress is enabled by default)."
map:
  - type: share
    read_only: false
usb: true
audio: false
gpio: false
homeassistant_api: false
auth_api: false
homeassistant: "2024.6.0"
options:
  printer_backend: "brother-network"
  brother_uri: "tcp://192.168.1.192:9100"
  brother_model: "QL-810W"
  brother_label: "62x29"
  rotate: "auto"
  high_quality: true
  cut: true
  usb_vendor_id: 0x0FE6
  usb_product_id: 0x811E
  label_output_dir: "/share/printer-labels"
  dev_reload: false
schema:
  printer_backend: "list(file|brother-network|escpos-usb|escpos-bluetooth)"
  brother_uri: "str?"
  brother_model: "str?"
  brother_label: "str?"
  rotate: "list(auto|0|90|180|270)?"
  high_quality: bool
  cut: bool
  usb_vendor_id: "int?"
  usb_product_id: "int?"
  label_output_dir: "str?"
  dev_reload: bool
EOF

DOCKERFILE_PATH="${ADDON_ROOT}/Dockerfile"
log "Writing ${DOCKERFILE_PATH}"
cat >"${DOCKERFILE_PATH}" <<'EOF'
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/printer

RUN \
  apk add --no-cache \
    bash \
    python3 \
    python3-dev \
    py3-pip \
    py3-virtualenv \
    py3-wheel \
    libstdc++ \
    cairo \
    pango \
    gdk-pixbuf \
    ttf-dejavu \
    libjpeg-turbo \
    libwebp \
    lcms2 \
    openjpeg \
    tiff \
    libxcb \
    harfbuzz \
    fribidi \
    zlib \
    freetype \
    libpng \
    libffi \
    libusb \
    pkgconf \
  && apk add --no-cache --virtual .build-deps \
    build-base \
    linux-headers \
    python3-dev \
    cairo-dev \
    pango-dev \
    gdk-pixbuf-dev \
    libjpeg-turbo-dev \
    libwebp-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    libxcb-dev \
    harfbuzz-dev \
    fribidi-dev \
    zlib-dev \
    freetype-dev \
    libpng-dev \
    libffi-dev \
  && python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
  && mkdir -p /opt/printer/app

COPY app/ /opt/printer/app/

RUN \
  /opt/venv/bin/pip install --no-cache-dir /opt/printer/app \
  && find /opt/printer/app -type f -name '*.pyc' -delete \
  && find /opt/printer/app -type d -name '__pycache__' -delete \
  && apk del .build-deps

COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 8099

CMD ["/run.sh"]
EOF

RUN_SCRIPT_PATH="${ADDON_ROOT}/run.sh"
log "Writing ${RUN_SCRIPT_PATH}"
cat >"${RUN_SCRIPT_PATH}" <<'EOF'
#!/usr/bin/with-contenv bashio
set -euo pipefail

LABEL_OUTPUT_DIR="$(bashio::config 'label_output_dir')"
if [ -z "${LABEL_OUTPUT_DIR}" ] || [ "${LABEL_OUTPUT_DIR}" = "null" ]; then
  LABEL_OUTPUT_DIR="/share/printer-labels"
fi

export LABEL_OUTPUT_DIR
export PRINTER_OUTPUT_PATH="${LABEL_OUTPUT_DIR}/latest.png"
export FLASK_HOST="::"
export FLASK_PORT="8099"

mkdir -p "${LABEL_OUTPUT_DIR}"

BACKEND="$(bashio::config 'printer_backend')"
export PRINTER_BACKEND="${BACKEND:-file}"

if bashio::config.has_value 'brother_uri'; then
  export BROTHER_PRINTER_URI="$(bashio::config 'brother_uri')"
fi

if bashio::config.has_value 'brother_model'; then
  export BROTHER_MODEL="$(bashio::config 'brother_model')"
fi

if bashio::config.has_value 'brother_label'; then
  export BROTHER_LABEL="$(bashio::config 'brother_label')"
fi

if bashio::config.has_value 'rotate'; then
  export BROTHER_ROTATE="$(bashio::config 'rotate')"
fi

if bashio::config.has_value 'high_quality'; then
  export BROTHER_HQ="$(bashio::config 'high_quality')"
fi

if bashio::config.has_value 'cut'; then
  export BROTHER_CUT="$(bashio::config 'cut')"
fi

if bashio::config.has_value 'usb_vendor_id'; then
  export ESC_POS_VENDOR_ID="$(bashio::config 'usb_vendor_id')"
fi

if bashio::config.has_value 'usb_product_id'; then
  export ESC_POS_PRODUCT_ID="$(bashio::config 'usb_product_id')"
fi

if bashio::config.has_value 'bluetooth_mac'; then
  export ESC_POS_BLUETOOTH_MAC="$(bashio::config 'bluetooth_mac')"
fi

if bashio::config.true 'dev_reload'; then
  export PRINTER_DEV_RELOAD=1
fi

bashio::log.info "Starting Printer Service on port ${FLASK_PORT}"
exec python -m printer_service.app
EOF

README_PATH="${ADDON_ROOT}/README.md"
log "Writing ${README_PATH}"
cat >"${README_PATH}" <<'EOF'
# Printer Service Home Assistant Add-on

Local add-on that exposes the kitchen label printing Flask UI over Home Assistant ingress. It supports Brother QL network printers, ESC/POS USB or Bluetooth devices, or file-only output that saves generated labels into Home Assistant's `/share` directory.
EOF

DOCS_PATH="${ADDON_ROOT}/DOCS.md"
log "Writing ${DOCS_PATH}"
cat >"${DOCS_PATH}" <<'EOF'
# Printer Service Add-on

This add-on packages the kitchen label printing service for Home Assistant. The UI is available via ingress, and prints can be dispatched to Brother network printers, ESC/POS USB/Bluetooth devices, or saved as files.

## Installation

1. Extract the tarball from `build/home-assistant-addon/printer_service.tar.gz` to `/addons/` on your Home Assistant host (so the add-on is in `/addons/printer_service/`).
2. In Home Assistant, open **Settings → Add-ons → Add-on Store** and click **Check for updates**. The add-on appears under **Local add-ons**.
3. Install and start the add-on.

## Configuration

All options are exposed in the add-on UI. Defaults keep the service in file mode and write labels to `/share/printer-labels`.

- `printer_backend`: `file`, `brother-network`, `escpos-usb`, or `escpos-bluetooth`.
- `brother_uri`: TCP URI (e.g., `tcp://192.168.1.192:9100`) when using the Brother backend.
- `brother_model`: Brother model name (default `QL-810W`).
- `brother_label`: Label roll code (e.g., `62x29`).
- `rotate`: Rotation applied before printing (`auto`, `0`, `90`, `180`, `270`).
- `high_quality`: Use Brother high-quality mode.
- `cut`: Trigger the cutter after printing.
- `usb_vendor_id` / `usb_product_id`: IDs for ESC/POS USB printers.
- `bluetooth_mac`: MAC address for ESC/POS Bluetooth printers.
- `label_output_dir`: Directory for saved labels; defaults to `/share/printer-labels`.
- `dev_reload`: Enable the Flask reloader (development only).

The add-on requests USB access to support ESC/POS USB printers. Other host privileges remain disabled to keep the security score high. AppArmor is enabled by default via `apparmor.txt`.

## Data locations

- Generated labels: `/share/printer-labels`
- Persistent options: `/data/options.json`

## Updating

Re-run `scripts/build_ha_addon.sh` to refresh the staged add-on and copy it to `/addons/printer_service/`, then click **Check for updates** in the add-on store.

## Access

- Preferred: use the add-on ingress link (Supervisor → Printer Service → Open Web UI).
- Optional: map port 8099 in the add-on configuration to reach it via `http://<ha-host>:<port>/` if you need direct access.
EOF

CHANGELOG_PATH="${ADDON_ROOT}/CHANGELOG.md"
log "Writing ${CHANGELOG_PATH}"
cat >"${CHANGELOG_PATH}" <<EOF
## ${PACKAGE_VERSION}

- Initial Home Assistant add-on packaging for Printer Service.
EOF

APPARMOR_PATH="${ADDON_ROOT}/apparmor.txt"
log "Writing ${APPARMOR_PATH}"
cat >"${APPARMOR_PATH}" <<'EOF'
#include <tunables/global>

profile printer_service flags=(attach_disconnected,mediate_deleted) {
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

  /usr/bin/python3 ix,
  /opt/venv/bin/python ix,
  /opt/venv/bin/python3 ix,
  /opt/venv/bin/** ix,
}
EOF

TRANSLATIONS_PATH="${ADDON_ROOT}/translations/en.yaml"
log "Writing ${TRANSLATIONS_PATH}"
cat >"${TRANSLATIONS_PATH}" <<'EOF'
configuration:
  printer_backend:
    name: Printer backend
    description: Choose where to send generated labels.
  brother_uri:
    name: Brother printer URI
    description: TCP URI for Brother QL printers (tcp://host:9100).
  brother_model:
    name: Brother model
    description: Model identifier (e.g., QL-810W).
  brother_label:
    name: Label code
    description: Label roll code (e.g., 62x29).
  rotate:
    name: Rotation
    description: Override label rotation before printing.
  high_quality:
    name: High quality
    description: Enable high-quality mode on Brother printers.
  cut:
    name: Auto cut
    description: Trigger a cut after printing on Brother printers.
  usb_vendor_id:
    name: USB vendor ID
    description: Vendor ID for ESC/POS USB printers.
  usb_product_id:
    name: USB product ID
    description: Product ID for ESC/POS USB printers.
  bluetooth_mac:
    name: Bluetooth MAC
    description: MAC address for ESC/POS Bluetooth printers.
  label_output_dir:
    name: Label output directory
    description: Directory where generated labels are stored.
  dev_reload:
    name: Enable dev reload
    description: Restart Flask automatically when files change (development only).
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

def ensure_png(path: Path, width: int, height: int):
    if path.exists():
        return
    if width == 128 and height == 128:
        path.write_bytes(placeholder)
        return
    # fallback: reuse placeholder scaled by viewers
    path.write_bytes(placeholder)

ensure_png(icon, 128, 128)
ensure_png(logo, 250, 100)
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
