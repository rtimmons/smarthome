#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CONFIG_DIR}/.." && pwd)"
SCRIPTS_PATH="new-hass-configs/scripts.yaml"

cd "$REPO_ROOT"

git check-ignore -q "$SCRIPTS_PATH"
if git ls-files --error-unmatch "$SCRIPTS_PATH" >/dev/null 2>&1; then
    echo "scripts.yaml must be generated and untracked" >&2
    exit 1
fi

grep -q 'generated/scripts.yaml' "${CONFIG_DIR}/Justfile"
grep -q '^script: !include scripts.yaml$' "${CONFIG_DIR}/configuration.yaml"

echo "generated configuration policy tests passed"
