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

PORT="3000"
export PORT
APP_PORT="3000"
export APP_PORT
SONOS_BASE_URL="$(config_get 'sonos_base_url')"
if [ -z "$SONOS_BASE_URL" ]; then
  SONOS_BASE_URL="http://local-sonos-api:5006"
fi
export SONOS_BASE_URL
LEDGRID_URL="$(config_get 'ledgrid_base_url')"
if [ -z "$LEDGRID_URL" ]; then
  LEDGRID_URL="http://ledwallleft.local:5000"
fi
export LEDGRID_URL
HASS_WEBHOOK_BASE="$(config_get 'webhook_base')"
if [ -z "$HASS_WEBHOOK_BASE" ]; then
  HASS_WEBHOOK_BASE=""
fi
if [ -n "$HASS_WEBHOOK_BASE" ]; then
  export HASS_WEBHOOK_BASE
fi

cd /opt/grid-dashboard/app

attempt=0
while true; do
  attempt=$((attempt + 1))
  log_info "Starting Grid Dashboard on port ${PORT} (attempt ${attempt})"

  if npm start; then
    log_info "Grid Dashboard exited cleanly"
    exit 0
  else
    exit_code=$?
  fi

  # Crash loop protection: let Supervisor take over if we fail repeatedly.
  if [ "$attempt" -ge 10 ]; then
    log_info "Grid Dashboard crashed ${attempt} times; exiting so Supervisor can apply restart policy"
    exit "$exit_code"
  fi

  log_info "Grid Dashboard exited with code ${exit_code}; restarting in 2s"
  sleep 2
done
