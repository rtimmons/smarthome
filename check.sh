#!/usr/bin/env bash
set -euo pipefail

# Quick end-to-end check:
#  - assumes snapshot-service is running on http://localhost:4010
#  - assumes printer service is running on http://localhost:8099
#  - renders a preview PNG from snapshot widgets into printer/label-output/snapshot-preview.png
#  - optionally sends to /print when invoked with --print

SNAPSHOT_URL="${SNAPSHOT_URL:-http://localhost:4010/snapshot}"
PRINTER_PREVIEW_URL="${PRINTER_PREVIEW_URL:-http://localhost:8099/labels/preview}"
PRINTER_PRINT_URL="${PRINTER_PRINT_URL:-http://localhost:8099/print}"
OUTPUT_PATH="${OUTPUT_PATH:-printer/label-output/snapshot-preview.png}"
DO_PRINT=false

if [[ "${1-}" == "--print" ]]; then
  DO_PRINT=true
fi

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing dependency: $1" >&2
    exit 1
  fi
}

require curl
require jq
require base64

echo "Fetching snapshot from ${SNAPSHOT_URL}..."
snapshot_json="$(curl -fsSL "${SNAPSHOT_URL}")"
widgets="$(jq -ce '.widgets // empty' <<<"${snapshot_json}" || true)"
if [[ -z "${widgets}" ]]; then
  echo "No widgets present in snapshot; aborting." >&2
  exit 1
fi

payload="$(jq -cn --argjson widgets "${widgets}" '{template:"daily_snapshot",data:{widgets:$widgets}}')"

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

mkdir -p "$(dirname "${OUTPUT_PATH}")"
echo "${data_url#data:image/png;base64,}" | base64 --decode > "${OUTPUT_PATH}"
echo "Saved preview to ${OUTPUT_PATH}"
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
