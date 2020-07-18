#!/usr/bin/env bash
set -eou pipefail


cd "$(dirname "$0")" || exit 1

export VIRTUAL_ENV_DISABLE_PROMPT=1

if ! ssh -o PasswordAuthentication=no -o BatchMode=yes pi@smarterhome.local exit &>/dev/null; then
    echo -e "Need passwordless ssh:\n\n    ssh-copy-id pi@smarterhome.local\n"
    exit 1
fi

./check-hass-configs.sh

echo "Stopping home-assistant"
ssh -o PasswordAuthentication=no -o BatchMode=yes pi@smarterhome.local \
    'sudo systemctl stop home-assistant.service'

pushd HomeAssistantConfig >/dev/null 2>&1 || exit 1
    scp ./*.yaml pi@smarterhome.local:/home/pi/repo/HomeAssistantConfig/ >/dev/null
    scp ./*.xml pi@smarterhome.local:/home/pi/repo/HomeAssistantConfig/ >/dev/null
    # scp -r .storage pi@smarterhome.local:/home/pi/repo/HomeAssistantConfig >/dev/null
popd >/dev/null 2>&1 || exit 1

echo "Restarting home-assistant for new changes to take effect"
ssh -o PasswordAuthentication=no -o BatchMode=yes pi@smarterhome.local \
    'sudo systemctl restart home-assistant.service'

echo -e "Home-assistant is now restarting. Check Z-Wave at\n    http://smarterhome.local:8123/lovelace\n"
