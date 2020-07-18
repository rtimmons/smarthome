#!/usr/bin/env bash

if [[ ! -d "venv" || ! -e "venv/setup" ]]; then
    rm -rf "venv"

    python3 -m pip install virtualenv
    python3 -m virtualenv venv
    # shellcheck source=/dev/null
    source ./venv/bin/activate
    python3 -m pip install ansible
    python3 -m pip install yamllint
    touch venv/setup
fi

# shellcheck source=/dev/null
source ./venv/bin/activate
