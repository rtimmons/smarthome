#!/usr/bin/env bash

cat inventory.template \
    | sed -E "s,PWD,$PWD,g" \
    >  inventory.ini



docker build -t     rtimmons-dashboardui-ansible .
docker run          rtimmons-dashboardui-ansible
