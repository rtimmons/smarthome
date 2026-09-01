#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_dir="${repo_dir}/zwave-device-configs"

expected_files=(
  "fibaro-fgrgbw-442-disable-auto-refresh.json"
  "zooz-zen31-disable-auto-refresh.json"
)

for filename in "${expected_files[@]}"; do
  file="${config_dir}/${filename}"
  test -f "${file}"
  jq -e '
    type == "object" and
    (."$import" | type == "string") and
    (."$import" | test("^~/0x[0-9a-f]{4}/")) and
    .compat.disableAutoRefresh == true
  ' "${file}" >/dev/null
done

actual_count="$(find "${config_dir}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')"
test "${actual_count}" = "${#expected_files[@]}"
