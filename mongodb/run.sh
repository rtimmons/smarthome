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

# Get MongoDB version from options (default to 8)
MONGODB_VERSION="$(config_get 'mongodb_version')"
if [ -z "${MONGODB_VERSION}" ]; then
  MONGODB_VERSION="8"
fi

# Get initial database name from options (default to smarthome)
MONGO_INITDB_DATABASE="$(config_get 'mongo_initdb_database')"
if [ -z "${MONGO_INITDB_DATABASE}" ]; then
  MONGO_INITDB_DATABASE="smarthome"
fi
export MONGO_INITDB_DATABASE

# Ensure data directory exists and has correct permissions
mkdir -p /data/db
chown -R mongodb:mongodb /data/db

log_info "Starting MongoDB Community Edition ${MONGODB_VERSION}"
log_info "Database directory: /data/db"
log_info "Initial database: ${MONGO_INITDB_DATABASE}"

# Start MongoDB
exec mongod --bind_ip_all --dbpath /data/db
