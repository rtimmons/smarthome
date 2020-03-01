#!/usr/bin/env bash
set -eou pipefail


cd "$(dirname "$0")" || exit 1

export VIRTUAL_ENV_DISABLE_PROMPT=1

if ! ssh -o PasswordAuthentication=no -o BatchMode=yes pi@smarterhome.local exit &>/dev/null; then
    echo -e "Need passwordless ssh:\n\n    ssh-copy-id pi@smarterhome.local\n"
    exit 1
fi

pushd MetaHassConfig >/dev/null 2>&1 || exit 1
    if [ ! -d venv ]; then
        python3 -m pip install virtualenv
        virtualenv venv
    fi
    # shellcheck disable=SC1091
    source ./venv/bin/activate
        python3 ./setup.py develop >/dev/null
        pushd ../HomeAssistantConfig >/dev/null 2>&1 || exit 1
            hassmetagen ./metaconfig.yaml
        popd >/dev/null 2>&1 || exit 1
    deactivate
popd >/dev/null 2>&1 || exit 1

./check-hass-configs.sh

echo "Stopping home-assistant"
ssh -o PasswordAuthentication=no -o BatchMode=yes pi@smarterhome.local \
    'sudo systemctl stop home-assistant.service'

pushd HomeAssistantConfig >/dev/null 2>&1 || exit 1
    scp ./zwcfg_0xef979358.xml pi@smarterhome.local:/home/pi/repo/HomeAssistantConfig/ >/dev/null
    scp ./automations.yaml pi@smarterhome.local:/home/pi/repo/HomeAssistantConfig/ >/dev/null
    scp ./scenes.yaml pi@smarterhome.local:/home/pi/repo/HomeAssistantConfig/ >/dev/null
popd >/dev/null 2>&1 || exit 1

echo "Restarting home-assistant for new changes to take effect"
ssh -o PasswordAuthentication=no -o BatchMode=yes pi@smarterhome.local \
    'sudo systemctl restart home-assistant.service'

echo -e "Home-assistant is now restarting. Check Z-Wave at\n    http://smarterhome.local:8123\n"
