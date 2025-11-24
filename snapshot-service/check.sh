#!/usr/bin/env bash
set -euo pipefail

# Quick end-to-end check (run from snapshot-service):
#  - assumes snapshot-service is running on http://localhost:4010
#  - assumes printer service is running on http://localhost:8099
#  - snapshot mode (--snapshot): renders a preview PNG from snapshot widgets into ../printer/label-output/snapshot-preview.png
#  - receipt mode (default): renders a checklist receipt PNG into ../printer/label-output/receipt-checklist.png
#  - optionally sends to /print when invoked with --print

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SNAPSHOT_URL="${SNAPSHOT_URL:-http://localhost:4010/snapshot}"
PRINTER_PREVIEW_URL="${PRINTER_PREVIEW_URL:-http://localhost:8099/labels/preview}"
PRINTER_PRINT_URL="${PRINTER_PRINT_URL:-http://localhost:8099/print}"
RECEIPT_QR_BASE="${RECEIPT_QR_BASE:-http://localhost:4010/receipt/upload}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
DO_PRINT=false
MODE="receipt"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print)
      DO_PRINT=true
      shift
      ;;
    --snapshot)
      MODE="snapshot"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing dependency: $1" >&2
    exit 1
  fi
}

require curl
require jq
require base64

if [[ "${MODE}" == "receipt" ]]; then
  today="$(date -I)"
  receipt_id="${RECEIPT_ID:-${today//-/}}"
  items_json="${RECEIPT_ITEMS:-[\"Breakfast\",\"Lunch\",\"Dinner\",\"Meds AM\",\"Meds PM\",\"Hydrate x8\",\"Exercise\",\"Notes\"]}"
  echo "Rendering receipt checklist for ${today} (receipt_id=${receipt_id})..."
  payload="$(jq -cn --arg date "${today}" --arg qr "${RECEIPT_QR_BASE}" --arg rid "${receipt_id}" --argjson items "${items_json}" '
    {template:"receipt_checklist",
     data: ( {date:$date, qr_base:$qr, receipt_id:$rid} +
             (reduce range(0; ($items|length)) as $i ({}; .["item\($i+1)"]=($items[$i]))) )
    }')"
  default_target="${REPO_ROOT}/printer/label-output/receipt-checklist.png"
  TARGET_PATH="${OUTPUT_PATH:-${default_target}}"
  echo "Upload URL embedded in QR: ${RECEIPT_QR_BASE}"
else
  echo "Fetching snapshot from ${SNAPSHOT_URL}..."
  snapshot_json="$(curl -fsSL "${SNAPSHOT_URL}")"
  widgets="$(jq -ce '.widgets // empty' <<<"${snapshot_json}" || true)"
  if [[ -z "${widgets}" ]]; then
    echo "No widgets present in snapshot; aborting." >&2
    exit 1
  fi
  payload="$(jq -cn --argjson widgets "${widgets}" '{template:"daily_snapshot",data:{widgets:$widgets}}')"
  default_target="${REPO_ROOT}/printer/label-output/snapshot-preview.png"
  TARGET_PATH="${OUTPUT_PATH:-${default_target}}"
fi

echo "Requesting preview from ${PRINTER_PREVIEW_URL}..."
preview_response="$(curl -fsSL -X POST -H "Content-Type: application/json" \
  -d "${payload}" "${PRINTER_PREVIEW_URL}")"

metrics="$(jq -c '.metrics // {}' <<<"${preview_response}")"
warnings="$(jq -c '.warnings // []' <<<"${preview_response}")"
data_url="$(jq -r '.image // empty' <<<"${preview_response}")"

if [[ -z "${data_url}" ]]; then
  echo "Preview did not return an image. Full response:" >&2
  echo "${preview_response}" >&2
  exit 1
fi

mkdir -p "$(dirname "${TARGET_PATH}")"
echo "${data_url#data:image/png;base64,}" | base64 --decode > "${TARGET_PATH}"
echo "Saved preview to ${TARGET_PATH}"
echo "Metrics: ${metrics}"
echo "Warnings: ${warnings}"

if [[ "${DO_PRINT}" == "true" ]]; then
  echo "Sending print job to ${PRINTER_PRINT_URL}..."
  print_response="$(curl -fsSL -X POST -H "Content-Type: application/json" \
    -d "${payload}" "${PRINTER_PRINT_URL}")"
  echo "Print response: ${print_response}"
else
  echo "Skipping print (pass --print to send to /print)."
fi
