#!/usr/bin/env bash

virtualenv venv
source ./venv/bin/activate
pip install ansible
source ./ansible.sh
