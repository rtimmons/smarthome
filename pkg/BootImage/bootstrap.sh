#!/usr/bin/env bash

if [ ! -d vendor ]; then
    mkdir vendor
fi

pushd vendor >/dev/null
    if [ ! -d "pi-gen" ]; then
        git clone https://github.com/RPi-Distro/pi-gen.git
    fi
popd >/dev/null


