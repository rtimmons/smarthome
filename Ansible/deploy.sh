#!/usr/bin/env bash

source ./ansible-env.sh

ansible-playbook \
    -v \
    -i inventory.ini \
    "$PWD"/playbook.yml
