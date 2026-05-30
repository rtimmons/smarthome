#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"

config_get() {
  local key="$1"
  if [ -f "${OPTIONS_FILE}" ] && command -v jq >/dev/null 2>&1; then
    jq -er --arg key "${key}" '.[$key] // empty' "${OPTIONS_FILE}" 2>/dev/null || true
  fi
}

PORT="$(config_get port)"
if [ -z "${PORT}" ]; then
  PORT="3000"
fi

PUBLIC_BASE_URL="$(config_get public_base_url)"

export NODE_ENV="${NODE_ENV:-production}"
export HOST="${HOST:-0.0.0.0}"
export PORT
export DATA_DIR="${DATA_DIR:-/data}"

if [ -n "${PUBLIC_BASE_URL}" ]; then
  export PUBLIC_BASE_URL
fi

cd /opt/app
exec npm start

