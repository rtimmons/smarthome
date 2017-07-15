#!/usr/bin/env bash
set -eou pipefail

# if [ ! -e "/Applications/PiBakery.app" ]; then
#     brew cask install pibakery
# fi

# https://github.com/davidferguson/pibakery
if [ ! -d vendor ]; then
    mkdir vendor
fi

if [ ! -d "/Library/Application Support/PiBakery/os" ]; then
    # become sudo
    sudo mkdir -p "/Library/Application Support/PiBakery/os"
fi

pushd vendor >/dev/null
    if [ ! -d pibakery ]; then
        git clone https://github.com/davidferguson/pibakery.git
    fi
    pushd pibakery >/dev/null
        npm install
        npm run setup
    popd >/dev/null
    pushd "/Library/Application Support/PiBakery/os" >/dev/null
        f="raspbian-lite-pibakery.7z"
        if [ ! -e "$f" ]; then
            os="https://github.com/davidferguson/pibakery-raspbian/releases/download/v0.5.0/$f"
            sudo wget "$os"
        fi
    popd >/dev/null
popd

sudo cp images.json "/Library/Application Support/PiBakery/os"