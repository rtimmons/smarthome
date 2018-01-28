#!/usr/bin/env bash

source ./ansible-env.sh

ansible-playbook \
    -vv \
    -i post_init.ini \
    "$PWD"/deploy.yml \
