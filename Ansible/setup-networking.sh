#!/usr/bin/env bash

cd "$(dirname "$0")"

source ./ansible-env.sh

ansible-playbook \
    -v \
    -i pre_init.ini \
    "$PWD"/setup-networking.yml
