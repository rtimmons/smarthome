#!/usr/bin/env bash

if [[ ! -d "venv" || ! -e "venv/setup" ]]; then
    rm -rf "venv"
    python3 -mvenv venv
    # shellcheck source=/dev/null
    export VIRTUAL_ENV_DISABLE_PROMPT=1
    source ./venv/bin/activate
        python3 -m pip install ansible
        python3 -m pip install yamllint
        touch venv/setup
    deactivate
fi

# shellcheck source=/dev/null
source ./venv/bin/activate
