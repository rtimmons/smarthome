#!/usr/bin/env bash

set -eo pipefail

cd "$(dirname "$0")" || exit 1

# Create venv for MetaHassConfig
pushd MetaHassConfig >/dev/null 2>&1 || exit 1
    if [[ ! -d "venv" || ! -e "venv/setup4" ]]; then

        declare -a ssl_prefix
        ssl_prefix=()
        if [[ "$(uname)" == "Darwin" ]]; then
            brew install "openssl@3"
            ssl_prefix=(
                env OPENSSL_DIR="$(brew --prefix openssl@3)"
            )
            OPENSSL_DIR="$(brew --prefix openssl@3)"
            export OPENSSL_DIR
        fi
        hass_cmd=(  "${ssl_prefix[@]}" python3 -m pip install 'homeassistant==2021.9.7'  -q -q)
        crypto_cmd=("${ssl_prefix[@]}" python3 -m pip install "cryptography==3.3.2")

        rm -rf "venv"
        python3 -mvenv venv
        # shellcheck source=/dev/null
        VIRTUAL_ENV_DISABLE_PROMPT=true source ./venv/bin/activate
            export PIP_CONSTRAINT="$PWD/venv/constraints.txt"
            echo "cython < 3.0" > "${PIP_CONSTRAINT}"
            python3 -m pip install --upgrade pip
            echo "${crypto_cmd[@]}"
            "${crypto_cmd[@]}"
            python3 ./setup.py develop >/dev/null
            python3 -m pip install -r ./requirements.txt
            echo "${hass_cmd[@]}"
            "${hass_cmd[@]}"
            touch venv/setup4
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