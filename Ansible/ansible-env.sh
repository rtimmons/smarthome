#!/usr/bin/env bash

if [ ! -d "venv" ]; then
    pip install virtualenv
    virtualenv venv
    source ./venv/bin/activate
    pip install ansible
fi

source ./venv/bin/activate
