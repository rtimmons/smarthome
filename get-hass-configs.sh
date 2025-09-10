#!/usr/bin/env bash

cd "$(dirname "$0")"
scp -r 'pi@smarterhome5.local:/home/pi/repo/HomeAssistantConfig/*.xml' ./HomeAssistantConfig
scp -r 'pi@smarterhome5.local:/home/pi/repo/HomeAssistantConfig/*.yaml' ./HomeAssistantConfig
scp -r 'pi@smarterhome5.local:/home/pi/repo/HomeAssistantConfig/.storage' ./HomeAssistantConfig

cd HomeAssistantConfig
git clean -dfx .
