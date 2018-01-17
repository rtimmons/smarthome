#!/usr/bin/env bash

source ./ansible-env.sh

ansible-playbook \
    -vv \
    -i inventory.ini \
    "$PWD"/deploy.yml \
