#!/usr/bin/env bash

docker build -t     dashboardui-ansible .
docker run          dashboardui-ansible ./ansible.sh
