#!/usr/bin/env bash

cd "$(dirname "$0")" || exit 1

source ./ansible-env.sh

yamllint ./*.yml
yamllint vars
yamllint roles
