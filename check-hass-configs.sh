#!/usr/bin/env bash

cd "$(dirname "$0")" || exit 1

if [ ! -d venv ]; then
    python3 -m pip install virtualenv
    virtualenv venv
fi

# shellcheck disable=SC1091
source ./venv/bin/activate

hass -c "$PWD/HomeAssistantConfig" --script check_config

