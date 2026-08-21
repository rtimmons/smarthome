#!/usr/bin/env bash

# Shared Home Assistant transport settings. This file is sourced by the config
# synchronization scripts; it deliberately does not inspect the ambient SSH
# agent so automated operations always use the repository-local identity.
HA_SSH_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HASS_SSH_IDENTITY="${HASS_SSH_IDENTITY:-${HA_SSH_REPO_ROOT}/.ssh/id_ed25519_codex_smarthome}"
HA_SSH_ARGS=(-i "${HASS_SSH_IDENTITY}" -o IdentitiesOnly=yes -p 22)
HA_SCP_ARGS=(-i "${HASS_SSH_IDENTITY}" -o IdentitiesOnly=yes -P 22)
printf -v HA_RSYNC_SHELL 'ssh -i %q -o IdentitiesOnly=yes -p 22' "${HASS_SSH_IDENTITY}"
