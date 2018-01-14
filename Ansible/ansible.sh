#!/usr/bin/env bash

ansible-playbook \
    -vvv \
    -i inventory.ini \
    "$PWD"/playbook.yml
