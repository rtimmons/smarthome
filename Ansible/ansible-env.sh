#!/usr/bin/env bash

if [[ ! -d "venv" || ! -e "venv/setup2" ]]; then
    rm -rf "venv"
    python3 -mvenv venv
    # shellcheck source=/dev/null
    set +u
        VIRTUAL_ENV_DISABLE_PROMPT=true source ./venv/bin/activate
            python3 -m pip install ansible
            python3 -m pip install yamllint
            touch venv/setup2
        deactivate
    set -u
fi

set +u
    # shellcheck source=/dev/null
    source ./venv/bin/activate
set -u
