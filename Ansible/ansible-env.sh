#!/usr/bin/env bash

if [[ ! -d "venv" || ! -e "venv/setup3" ]]; then
    rm -rf "venv"
    pyenv install -s
    python3 -mvenv venv
    # shellcheck source=/dev/null
    set +u
        VIRTUAL_ENV_DISABLE_PROMPT=true source ./venv/bin/activate
            python3 -m pip install --upgrade pip
            python3 -m pip install ansible
            python3 -m pip install yamllint
            touch venv/setup3
        deactivate
    set -u
fi

set +u
    # shellcheck source=/dev/null
    source ./venv/bin/activate
set -u
