#!/usr/bin/env bash

if [[ ! -d "venv" || ! -e "venv/setup3" ]]; then

    declare -a crypto_cmd
    crypto_cmd=()
    if [[ "$(uname)" == "Darwin" ]]; then
        brew install "openssl@3"
        crypto_cmd=(
            env OPENSSL_DIR="$(brew --prefix openssl@3)"
        )
    fi

    crypto_cmd=("${crypto_cmd[@]}" pip install cryptography)

    rm -rf "venv"
    python3 -mvenv venv
    # shellcheck source=/dev/null
    set +u
    set -x
        VIRTUAL_ENV_DISABLE_PROMPT=true source ./venv/bin/activate
            python3 -m pip install --upgrade pip
            echo "${crypto_cmd[@]}"
            "${crypto_cmd[@]}"
            python3 -m pip install ansible
            python3 -m pip install yamllint
            touch venv/setup3
        deactivate
    set +x
    set -u
fi

set +u
    # shellcheck source=/dev/null
    source ./venv/bin/activate
set -u
