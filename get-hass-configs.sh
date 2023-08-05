#!/usr/bin/env bash

cd "$(dirname "$0")"
scp -r 'udoobolt@smarterudoo.local:/home/udoobolt/repo/HomeAssistantConfig/*.xml' ./HomeAssistantConfig
scp -r 'udoobolt@smarterudoo.local:/home/udoobolt/repo/HomeAssistantConfig/*.yaml' ./HomeAssistantConfig
scp -r 'udoobolt@smarterudoo.local:/home/udoobolt/repo/HomeAssistantConfig/.storage' ./HomeAssistantConfig

cd HomeAssistantConfig
git clean -dfx .
