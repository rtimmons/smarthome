#!/usr/bin/env bash

cd "$(dirname "$0")" || exit 1

source ./ansible-env.sh

ansible-playbook \
    -vv \
    -i post_init.ini \
    "$PWD"/deploy.yml \
