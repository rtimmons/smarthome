#!/usr/bin/env bash
set -eou pipefail

cd "$(dirname "$0")" || exit 1

../check-hass-configs.sh

source ./ansible-env.sh

ansible-playbook \
    -vvv \
    -i post_init.ini \
    "$PWD"/deploy.yml \
