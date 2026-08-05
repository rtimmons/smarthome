#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"

log_info() {
  echo "[INFO] $*"
}

config_get() {
  local key="$1"
  if [ -f "${OPTIONS_FILE}" ] && command -v jq >/dev/null 2>&1; then
    jq -er --arg key "${key}" '.[$key] // empty' "${OPTIONS_FILE}" 2>/dev/null || true
  else
    echo ""
  fi
}

PORT="5006"
export PORT
APP_PORT="5006"
export APP_PORT
SONOS_BASE_URL="$(config_get 'sonos_base_url')"
if [ -z "$SONOS_BASE_URL" ]; then
  SONOS_BASE_URL="http://local-node-sonos-http-api:5005"
fi
export SONOS_BASE_URL

cd /opt/sonos-api/app
log_info "Starting Sonos API on port ${PORT}"
# Keep Node as PID 1 so SIGTERM reaches its graceful shutdown handler.
exec node dist/server/index.js
