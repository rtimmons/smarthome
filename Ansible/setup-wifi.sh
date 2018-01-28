#!/usr/bin/env bash

source ./ansible-env.sh

ansible-playbook \
    -v \
    -i pre_init.ini \
    "$PWD"/setup-wifi.yml
