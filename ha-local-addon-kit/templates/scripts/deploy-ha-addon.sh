#!/usr/bin/env bash
set -euo pipefail

TALOS="${TALOS:-/Users/rtimmons/Projects/smarthome/talos/build/bin/talos}"
APP_DIR="${APP_DIR:-.}"
ADDON_DIR="${ADDON_DIR:-ha-addon}"
PACKAGE_ONLY="false"
ARGS=()

usage() {
  cat <<USAGE
Usage: $0 [--package-only] [--dry-run] [--verbose]

Environment:
  TALOS=${TALOS}
  APP_DIR=${APP_DIR}
  ADDON_DIR=${ADDON_DIR}
  HA_HOST=${HA_HOST:-homeassistant.local}
  HA_USER=${HA_USER:-root}
  HA_PORT=${HA_PORT:-22}
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --package-only)
      PACKAGE_ONLY="true"
      ;;
    --dry-run|--verbose|-v)
      ARGS+=("$1")
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ ! -x "${TALOS}" ]; then
  echo "Talos executable not found: ${TALOS}" >&2
  echo "Build it with: cd /Users/rtimmons/Projects/smarthome && just setup" >&2
  exit 1
fi

if [ "${PACKAGE_ONLY}" = "true" ]; then
  exec "${TALOS}" addon package-external --app-dir "${APP_DIR}" --addon-dir "${ADDON_DIR}" "${ARGS[@]}"
fi

exec "${TALOS}" addon deploy-external --app-dir "${APP_DIR}" --addon-dir "${ADDON_DIR}" "${ARGS[@]}"

