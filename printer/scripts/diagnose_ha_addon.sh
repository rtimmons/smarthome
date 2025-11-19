#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_FILE="${REPO_ROOT}/report.txt"

HA_HOST="${HA_HOST:-homeassistant.local}"
HA_PORT="${HA_PORT:-22}"
HA_USER="${HA_USER:-root}"

log() {
  echo "[$(date +"%H:%M:%S")] $*"
}

log "Gathering diagnostics from ${HA_USER}@${HA_HOST}..."

ssh -p "${HA_PORT}" "${HA_USER}@${HA_HOST}" bash <<'EOF' > "${REPORT_FILE}" 2>&1
set -euo pipefail

echo "========================================="
echo "HOME ASSISTANT ADD-ON DIAGNOSTIC REPORT"
echo "Generated: $(date)"
echo "========================================="
echo ""

echo "=== 1. Directory Structure: /addons/ ==="
if [ -d "/addons" ]; then
  echo "Directory /addons exists"
  ls -laR /addons/ 2>&1 || echo "Failed to list /addons/"
else
  echo "Directory /addons does NOT exist"
fi
echo ""

echo "=== 2. Directory Structure: /addons/printer_local/ ==="
if [ -d "/addons/printer_local" ]; then
  echo "Directory /addons/printer_local exists"
  ls -la /addons/printer_local/ 2>&1 || echo "Failed to list"
else
  echo "Directory /addons/printer_local does NOT exist"
fi
echo ""

echo "=== 3. repository.yaml content ==="
if [ -f "/addons/printer_local/repository.yaml" ]; then
  cat /addons/printer_local/repository.yaml
else
  echo "File /addons/printer_local/repository.yaml does NOT exist"
fi
echo ""

echo "=== 4. printer_service/config.yaml content ==="
if [ -f "/addons/printer_local/printer_service/config.yaml" ]; then
  cat /addons/printer_local/printer_service/config.yaml
else
  echo "File /addons/printer_local/printer_service/config.yaml does NOT exist"
fi
echo ""

echo "=== 5. Available add-ons (ha addons) ==="
ha addons 2>&1 || echo "Failed to run 'ha addons'"
echo ""

echo "=== 6. Add-on info (ha addons info printer_service) ==="
ha addons info printer_service 2>&1 || echo "Add-on 'printer_service' not found or command failed"
echo ""

echo "=== 7. Supervisor info ==="
ha supervisor info 2>&1 || echo "Failed to get supervisor info"
echo ""

echo "=== 8. Check for any local add-on repositories ==="
echo "Checking common local add-on paths:"
for path in /addons /usr/share/hassio/addons/local /data/addons/local; do
  echo "  - ${path}:"
  if [ -d "${path}" ]; then
    ls -la "${path}" 2>&1 | head -20
  else
    echo "    Does not exist"
  fi
done
echo ""

echo "=== 9. Supervisor logs (last 50 lines) ==="
ha supervisor logs 2>&1 | tail -50 || echo "Failed to get supervisor logs"
echo ""

echo "=== 10. Check repository files in all /addons subdirectories ==="
find /addons -name "repository.yaml" -o -name "config.yaml" 2>&1 | while read file; do
  echo "Found: ${file}"
done
echo ""

echo "========================================="
echo "END OF DIAGNOSTIC REPORT"
echo "========================================="
EOF

log "Diagnostic report saved to: ${REPORT_FILE}"
log "Please review the report and share relevant sections."
