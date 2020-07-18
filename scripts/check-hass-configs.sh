#!/usr/bin/env bash

set -eo pipefail

cd "$(dirname "$0")" || exit 1

pushd MetaHassConfig >/dev/null 2>&1 || exit 1
    if [ ! -d venv ]; then
        python3 -mvenv venv
    fi
    export VIRTUAL_ENV_DISABLE_PROMPT=1
    # shellcheck disable=SC1091
    source ./venv/bin/activate
        python3 ./setup.py develop >/dev/null
        pip install -r ./requirements.txt
        pushd ../HomeAssistantConfig >/dev/null 2>&1 || exit 1
            hassmetagen ./metaconfig.yaml
        popd >/dev/null 2>&1 || exit 1
    deactivate
popd >/dev/null 2>&1 || exit 1

python3 -m pip install homeassistant  -q -q

hash -r

hass -c "$PWD/HomeAssistantConfig" --script check_config
