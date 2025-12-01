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

# Create journal directory in tmpfs and symlink it to /data
mkdir -p /tmp/mongodb/journal
ln -sf /tmp/mongodb/journal /data/journal

log_info "Starting MongoDB Community Edition ${MONGODB_VERSION}"
log_info "Database directory: /data"
log_info "Journal directory (tmpfs): /tmp/mongodb/journal"
log_info "Initial database: ${MONGO_INITDB_DATABASE}"

# Start MongoDB as root (Home Assistant addon security model)
# Run with --bind_ip_all to allow connections from other addons
# Use /data directly as dbpath (not /data/db) to avoid permission issues
exec mongod --bind_ip_all --dbpath /data
