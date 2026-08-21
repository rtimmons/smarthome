#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/ha-ssh.sh"
TMP_DIR="${HASS_CONFIG_TMP_DIR:-/tmp/new-hass-configs}"
REMOTE="${HASS_CONFIG_REMOTE:-root@homeassistant.local}"
REMOTE_CONFIG="${HASS_CONFIG_REMOTE_DIR:-/config}"

RSYNC_PROTECT_FILTERS=(
  "--filter=protect .storage/***"
  "--filter=protect .cloud/***"
  "--filter=protect .cache/***"
  "--filter=protect .ssh/***"
  "--filter=protect ssh/***"
  "--filter=protect ssl/***"
  "--filter=protect addons/***"
  "--filter=protect addon_configs/***"
  "--filter=protect share/***"
  "--filter=protect media/***"
  "--filter=protect www/***"
  "--filter=protect custom_components/***"
  "--filter=protect deps/***"
  "--filter=protect tts/***"
  "--filter=protect esphome/***"
)

LOCAL_REPO_EXCLUDES=(
  "--exclude=config-generator/***"
  "--exclude=backups/***"
  "--exclude=inventory_snapshots/***"
)

DEPLOY_FILTERS=(
  "--include=*/"
  "--include=*.yaml"
  "--include=*.yml"
  "--include=*.json"
  "--include=*.sh"
  "--exclude=.git/"
  "--exclude=.cloud/"
  "--exclude=.storage/"
  "--exclude=deps/"
  "--exclude=tts/"
  "--exclude=secrets.yaml"
  "--exclude=*.db*"
  "--exclude=*.log"
  "--exclude=*.pickle"
  "--exclude=*.uuid"
  "--exclude=*~"
  "--exclude=*.pyc"
  "--exclude=__pycache__/"
  "--exclude=*"
)

monotonic_ms() {
  python3 -c 'import time; print(round(time.monotonic() * 1000))'
}

run_metric() {
  local phase="$1"
  shift
  local started_ms finished_ms exit_code status
  started_ms="$(monotonic_ms)"
  set +e
  "$@"
  exit_code=$?
  set -e
  finished_ms="$(monotonic_ms)"
  status="ok"
  if [ "$exit_code" -ne 0 ]; then status="error"; fi
  printf '__TALOS_CONFIG_METRIC__\t%s\t%s\t%s\t%s\n' \
    "$phase" "$started_ms" "$finished_ms" "$status" >&2
  return "$exit_code"
}

require_tools() {
  for bin in python3 rsync ssh; do
    if ! command -v "$bin" >/dev/null 2>&1; then
      echo "Missing required tool: $bin" >&2
      exit 1
    fi
  done
}

rsync_config() {
  rsync "$@" \
    "${RSYNC_PROTECT_FILTERS[@]}" \
    --prune-empty-dirs \
    "${LOCAL_REPO_EXCLUDES[@]}" \
    "${DEPLOY_FILTERS[@]}"
}

generate() {
  cd "$CONFIG_DIR"
  just generate
}

precheck() {
  cd "$CONFIG_DIR"
  run_metric "config.generate" generate
  run_metric "config.sync_check" just sync-check
  echo "Config deployment precheck passed"
}

needed() {
  cd "$CONFIG_DIR"
  local raw_changes
  raw_changes="$(run_metric "config.rsync_dry_run" \
    rsync_config -anic --delete -e "${HA_RSYNC_SHELL}" . "${REMOTE}:${REMOTE_CONFIG}/")"

  if printf '%s\n' "$raw_changes" | awk 'NF && !($2 == "./" && substr($1, 1, 2) == ".d") && $1 !~ /^[.]f[.][.]t/ { found = 1 } END { exit found ? 0 : 1 }'; then
    printf 'true\n'
  else
    printf 'false\n'
  fi
}

apply_config() {
  cd "$CONFIG_DIR"
  local remote_rsync_args
  printf -v remote_rsync_args '%q ' "${RSYNC_PROTECT_FILTERS[@]}" "${DEPLOY_FILTERS[@]}"
  run_metric "config.prepare_staging" \
    ssh "${HA_SSH_ARGS[@]}" "$REMOTE" "rm -rf \"${TMP_DIR}\" && mkdir -p \"${TMP_DIR}\""
  run_metric "config.upload_staging" \
    rsync_config -av --delete -e "${HA_RSYNC_SHELL}" . "${REMOTE}:${TMP_DIR}/"
  run_metric "config.copy_secrets" \
    ssh "${HA_SSH_ARGS[@]}" "$REMOTE" "if [ -f ${REMOTE_CONFIG}/secrets.yaml ]; then cp ${REMOTE_CONFIG}/secrets.yaml \"${TMP_DIR}\"/; fi"
  run_metric "config.backup" ssh "${HA_SSH_ARGS[@]}" "$REMOTE" "\
    backup_dir=\"/tmp/hass-config-backup\" && \
    rm -rf \"\${backup_dir}\" && \
    mkdir -p \"\${backup_dir}\" && \
    rsync -a --delete ${REMOTE_CONFIG}/ \"\${backup_dir}\"/"
  run_metric "config.sync" ssh "${HA_SSH_ARGS[@]}" "$REMOTE" "\
    rsync -av --delete --prune-empty-dirs \
      ${remote_rsync_args} \
      \"${TMP_DIR}\"/ ${REMOTE_CONFIG}/"
  run_metric "config.backup_cleanup" \
    ssh "${HA_SSH_ARGS[@]}" "$REMOTE" "rm -rf /tmp/hass-config-backup"
  run_metric "config.core_restart" ssh "${HA_SSH_ARGS[@]}" "$REMOTE" \
    'for attempt in 1 2 3 4 5 6 7 8 9 10; do if ha core restart >/tmp/ha-core-restart.out 2>&1; then rm -f /tmp/ha-core-restart.out; exit 0; fi; if ! grep -q "Another job is running for job group home_assistant_core" /tmp/ha-core-restart.out; then cat /tmp/ha-core-restart.out >&2; rm -f /tmp/ha-core-restart.out; exit 1; fi; sleep 3; done; cat /tmp/ha-core-restart.out >&2; rm -f /tmp/ha-core-restart.out; exit 1'
  run_metric "config.staging_cleanup" \
    ssh "${HA_SSH_ARGS[@]}" "$REMOTE" "rm -rf \"${TMP_DIR}\""
}

deploy() {
  precheck
  if [ "$(needed)" = "true" ]; then
    apply_config
  else
    echo "Home Assistant configs unchanged; skipping config deploy and restart."
  fi
}

main() {
  require_tools
  case "${1:-}" in
    precheck) precheck ;;
    needed) needed ;;
    apply) apply_config ;;
    deploy) deploy ;;
    *)
      echo "Usage: $0 {precheck|needed|apply|deploy}" >&2
      exit 2
      ;;
  esac
}

main "$@"
