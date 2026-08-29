#!/usr/bin/env bash

# Shared Home Assistant transport settings. This file is sourced by the config
# synchronization scripts; it deliberately does not inspect the ambient SSH
# agent so automated operations always use the repository-local identity.
HA_SSH_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -z "${HASS_SSH_IDENTITY:-}" ]]; then
  HASS_SSH_IDENTITY="${HA_SSH_REPO_ROOT}/.ssh/id_ed25519_codex_smarthome"
  if [[ ! -f "${HASS_SSH_IDENTITY}" ]]; then
    HA_SSH_COMMON_GIT_DIR="$(
      git -C "${HA_SSH_REPO_ROOT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true
    )"
    HA_SSH_COMMON_IDENTITY="$(dirname "${HA_SSH_COMMON_GIT_DIR:-/missing/.git}")/.ssh/id_ed25519_codex_smarthome"
    if [[ -f "${HA_SSH_COMMON_IDENTITY}" ]]; then
      HASS_SSH_IDENTITY="${HA_SSH_COMMON_IDENTITY}"
    fi
  fi
fi
HA_SSH_ARGS=(-i "${HASS_SSH_IDENTITY}" -o IdentitiesOnly=yes -p 22)
HA_SCP_ARGS=(-i "${HASS_SSH_IDENTITY}" -o IdentitiesOnly=yes -P 22)
printf -v HA_RSYNC_SHELL 'ssh -i %q -o IdentitiesOnly=yes -p 22' "${HASS_SSH_IDENTITY}"
