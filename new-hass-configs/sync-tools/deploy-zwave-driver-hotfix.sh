#!/usr/bin/env bash
set -euo pipefail
action="${1:-install}"
case "$action" in install|remove) ;; *) echo 'Usage: deploy-zwave-driver-hotfix.sh [install|remove]' >&2; exit 2;; esac
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
ssh_args=(-i "$repo_root/.ssh/id_ed25519_codex_smarthome" -o IdentitiesOnly=yes root@homeassistant.local)
config_root="$(ssh "${ssh_args[@]}" 'if [ -d /app_configs/core_zwave_js ]; then echo /app_configs/core_zwave_js; elif [ -d /addon_configs/core_zwave_js ]; then echo /addon_configs/core_zwave_js; else exit 1; fi')"
case "$config_root" in /app_configs/core_zwave_js|/addon_configs/core_zwave_js) ;; *) exit 1;; esac
if [ "$action" = install ]; then
  # The app imports this persistent file on startup; never edit its container.
  ssh "${ssh_args[@]}" "mkdir -p '$config_root/plugins'"
  ssh "${ssh_args[@]}" "cat > '$config_root/plugins/transport-service-security.cjs.next'" < "$repo_root/new-hass-configs/zwave-driver-plugins/transport-service-security.cjs"
fi
ssh "${ssh_args[@]}" bash -s -- "$config_root" "$action" <<'REMOTE'
set -euo pipefail
root="$1"
action="$2"
plugin='/config/plugins/transport-service-security.cjs'
backup="$root/backups/transport-service-security/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
cp -p "$root/settings.json" "$backup/settings.json"
if [ -f "$root/plugins/transport-service-security.cjs" ]; then
  cp -p "$root/plugins/transport-service-security.cjs" "$backup/plugin.cjs"
fi
chmod 700 "$backup"
chmod 600 "$backup/settings.json"
# Prepare and validate the entire new document before stopping the app.
if [ "$action" = install ]; then
  jq --arg plugin "$plugin" '.gateway.plugins = ((.gateway.plugins // []) | if index($plugin) then . else . + [$plugin] end)' "$root/settings.json" > "$backup/settings.next.json"
else
  jq --arg plugin "$plugin" '.gateway.plugins = ((.gateway.plugins // []) | map(select(. != $plugin)))' "$root/settings.json" > "$backup/settings.next.json"
fi
chmod 600 "$backup/settings.next.json"
ha apps stop core_zwave_js
rollback() {
  cp -p "$backup/settings.json" "$root/settings.json"
  if [ -f "$backup/plugin.cjs" ]; then
    cp -p "$backup/plugin.cjs" "$root/plugins/transport-service-security.cjs"
  fi
  ha apps start core_zwave_js || true
}
trap rollback ERR
if [ "$action" = install ]; then
  mv "$root/plugins/transport-service-security.cjs.next" "$root/plugins/transport-service-security.cjs"
fi
cp -p "$backup/settings.next.json" "$root/settings.json"
ha apps start core_zwave_js
trap - ERR
echo "Hotfix $action completed; saved configuration: $backup/settings.json"
echo 'Verify the persistent driver log confirms activation before claiming success.'
REMOTE
