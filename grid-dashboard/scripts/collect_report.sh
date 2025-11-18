#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HA_HOST="${HA_HOST:-homeassistant.local}"
HA_PORT="${HA_PORT:-22}"
REPORT_PATH="${REPO_ROOT}/report.txt"

log() {
  echo "[$(date +"%H:%M:%S")] $*"
}

log "Collecting Home Assistant add-on diagnostics from ${HA_HOST}:${HA_PORT}"

ssh -p "${HA_PORT}" "root@${HA_HOST}" bash <<'REMOTE' >"${REPORT_PATH}" 2>&1
set -euo pipefail

echo "== Host info ==" 
date
uname -a
echo "HA_HOST=${HA_HOST:-unknown} HA_PORT=${HA_PORT:-unknown}"

echo
echo "== Key paths =="
echo "/addons realpath: $(realpath /addons 2>/dev/null || echo missing)"
echo "/data/addons realpath: $(realpath /data/addons 2>/dev/null || echo missing)"
echo "/root/addons realpath: $(realpath /root/addons 2>/dev/null || echo missing)"
ls -la /addons 2>/dev/null || true
ls -la /addons/local 2>/dev/null || true
ls -la /data/addons 2>/dev/null || true
ls -la /data/addons/local 2>/dev/null || true
ls -la /root/addons 2>/dev/null || true
ls -la /root/addons/local 2>/dev/null || true

echo
echo "== Symlinks under /data/addons and /root/addons (following links) =="
find -L /data/addons -maxdepth 4 -type l -ls 2>/dev/null || true
find -L /root/addons -maxdepth 4 -type l -ls 2>/dev/null || true

echo
echo "== Grid dashboard add-on structure =="
if [ -d /addons/grid_dashboard ]; then
  echo "Found /addons/grid_dashboard"
  ls -laR /addons/grid_dashboard 2>/dev/null | head -n 200
else
  echo "NOT FOUND: /addons/grid_dashboard"
fi

echo
echo "== Grid dashboard config files =="
for p in \
  /addons/grid_dashboard/config.yaml \
  /data/addons/local/grid_dashboard/config.yaml \
  /root/addons/local/grid_dashboard/config.yaml; do
  if [ -f "$p" ]; then
    echo "-- $p --"
    cat "$p"
  fi
done

echo
echo "== Grid dashboard Dockerfile =="
if [ -f /addons/grid_dashboard/Dockerfile ]; then
  cat /addons/grid_dashboard/Dockerfile
else
  echo "NOT FOUND: /addons/grid_dashboard/Dockerfile"
fi

echo
echo "== Grid dashboard rootfs structure =="
if [ -d /addons/grid_dashboard/rootfs ]; then
  find /addons/grid_dashboard/rootfs -type f -ls 2>/dev/null || true
else
  echo "NOT FOUND: /addons/grid_dashboard/rootfs"
fi

echo
echo "== Grid dashboard service run script =="
if [ -f /addons/grid_dashboard/rootfs/etc/services.d/grid-dashboard/run ]; then
  echo "-- Permissions --"
  ls -la /addons/grid_dashboard/rootfs/etc/services.d/grid-dashboard/run
  echo "-- Content --"
  cat /addons/grid_dashboard/rootfs/etc/services.d/grid-dashboard/run
else
  echo "NOT FOUND: /addons/grid_dashboard/rootfs/etc/services.d/grid-dashboard/run"
fi

echo
echo "== Printer service structure (for comparison) =="
if [ -d /addons/printer_service ]; then
  echo "Found /addons/printer_service"
  ls -la /addons/printer_service 2>/dev/null || true
  if [ -f /addons/printer_service/Dockerfile ]; then
    echo "-- Dockerfile --"
    cat /addons/printer_service/Dockerfile
  fi
  if [ -f /addons/printer_service/run.sh ]; then
    echo "-- run.sh --"
    ls -la /addons/printer_service/run.sh
    cat /addons/printer_service/run.sh
  fi
else
  echo "NOT FOUND: /addons/printer_service"
fi

echo
echo "== Supervisor addons list =="
ha addons list || true

echo
echo "== Grid dashboard add-on info =="
ha addons info local_grid_dashboard 2>&1 || true

echo
echo "== Grid dashboard add-on logs (last 100 lines) =="
ha addons logs local_grid_dashboard 2>&1 | tail -n 100 || echo "No logs available"

echo
echo "== Supervisor logs (last 100 lines) =="
ha supervisor logs 2>&1 | tail -n 100 || true
REMOTE

log "Report written to ${REPORT_PATH}"
