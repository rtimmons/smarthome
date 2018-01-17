#!/usr/bin/env bash

source ./ansible-env.sh

ansible-playbook \
    -v \
    -i inventory.ini \
    "$PWD"/setup-wifi.yml
