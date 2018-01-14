#!/usr/bin/env bash

ansible-playbook \
    -v \
    -i inventory.ini \
    "$PWD"/playbook.yml
