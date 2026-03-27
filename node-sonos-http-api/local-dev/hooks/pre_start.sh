#!/usr/bin/env bash
set -euo pipefail

"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pre_setup.sh"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
addon_dir="$(cd "${script_dir}/../.." && pwd)"
upstream_dir="${addon_dir}/node-sonos-http-api"
patch_dir="${addon_dir}/patches"

if [ ! -d "${upstream_dir}/.git" ]; then
    echo "[node-sonos-http-api] Upstream checkout missing at ${upstream_dir}; run just setup." >&2
    exit 1
fi

shopt -s nullglob
for patch_file in "${patch_dir}"/*.patch; do
    patch_name="$(basename "${patch_file}")"

    if git -C "${upstream_dir}" apply --reverse --check "${patch_file}" >/dev/null 2>&1; then
        echo "[node-sonos-http-api] Patch already applied: ${patch_name}" >&2
        continue
    fi

    if git -C "${upstream_dir}" apply --check "${patch_file}" >/dev/null 2>&1; then
        echo "[node-sonos-http-api] Applying patch: ${patch_name}" >&2
        git -C "${upstream_dir}" apply "${patch_file}"
        continue
    fi

    echo "[node-sonos-http-api] Failed to apply patch cleanly: ${patch_name}" >&2
    exit 1
done
