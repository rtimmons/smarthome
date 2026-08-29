#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HASS_SSH_IDENTITY="/tmp/test-home-assistant-key"
source "${SCRIPT_DIR}/ha-ssh.sh"

[[ "${HA_SSH_ARGS[*]}" == "-i /tmp/test-home-assistant-key -o IdentitiesOnly=yes -p 22" ]]
[[ "${HA_SCP_ARGS[*]}" == "-i /tmp/test-home-assistant-key -o IdentitiesOnly=yes -P 22" ]]
[[ "${HA_RSYNC_SHELL}" == "ssh -i /tmp/test-home-assistant-key -o IdentitiesOnly=yes -p 22" ]]

grep -Fq 'git -C "${HA_SSH_REPO_ROOT}" rev-parse --path-format=absolute --git-common-dir' "${SCRIPT_DIR}/ha-ssh.sh"
grep -Fq '.ssh/id_ed25519_codex_smarthome' "${SCRIPT_DIR}/ha-ssh.sh"
grep -Fq 'IdentitiesOnly=yes' "${SCRIPT_DIR}/ha-ssh.sh"

echo "Home Assistant SSH transport tests passed"
