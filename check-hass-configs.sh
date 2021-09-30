#!/usr/bin/env bash

set -eo pipefail

cd "$(dirname "$0")" || exit 1

# Create venv for MetaHassConfig
pushd MetaHassConfig >/dev/null 2>&1 || exit 1
    if [[ ! -d "venv" || ! -e "venv/setup3" ]]; then
        rm -rf "venv"
        python3 -mvenv venv
        # shellcheck source=/dev/null
        VIRTUAL_ENV_DISABLE_PROMPT=true source ./venv/bin/activate
            python3 -m pip install --upgrade pip
            python3 ./setup.py develop >/dev/null
            python3 -m pip install -r ./requirements.txt
            python3 -m pip install 'homeassistant==2021.9.7'  -q -q
            touch venv/setup3
        deactivate
    fi
popd >/dev/null 2>&1 || exit 1

# Run `hass` in the HomeAssistantConfig dir.
pushd HomeAssistantConfig >/dev/null 2>&1 || exit 1
    # shellcheck source=/dev/null
    VIRTUAL_ENV_DISABLE_PROMPT=true source ../MetaHassConfig/venv/bin/activate
        hash -r
        hassmetagen ./metaconfig.yaml
        hass -c "$PWD" --script check_config
    deactivate
popd >/dev/null 2>&1 || exit 1

echo "Checked home-assistant config at $PWD/HomeAssistantConfig."