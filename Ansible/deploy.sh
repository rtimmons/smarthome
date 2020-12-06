#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

../check-hass-configs.sh

source ./ansible-env.sh

set -eou pipefail

ansible-playbook \
    -vv \
    -i post_init.ini \
    "$PWD"/deploy.yml \
