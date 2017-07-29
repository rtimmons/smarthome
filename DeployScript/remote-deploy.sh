#!/usr/bin/env bash

git status
git push
ssh pi@retropie.local './dashboard/pkg/DeployScript/local-deploy.sh'
