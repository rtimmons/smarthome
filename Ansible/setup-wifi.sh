#!/usr/bin/env bash

source ./ansible-env.sh

ansible-playbook \
    -v \
    -i post_init.ini \
    "$PWD"/setup-wifi.yml
