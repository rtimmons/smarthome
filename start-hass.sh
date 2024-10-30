#!/usr/bin/env bash

set -eou pipefail

cd /home/pi
mkdir -p newconfig
device="/dev/serial/by-id/usb-0658_0200-if00"
podman run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  -e TZ=MY_TIME_ZONE \
  -v /home/pi/newconfig:/config \
  -v /run/dbus:/run/dbus:ro \
  --network=host \
  --device "$device:$device" \
  ghcr.io/home-assistant/home-assistant:stable

