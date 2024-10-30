#!/usr/bin/env bash

set -eou pipefail

cd "/home/pi"
podman run -d \
    --restart=unless-stopped \
    -p 8091:8091    \
    -p 3000:3000    \
    --device "/dev/serial/by-id/usb-0658_0200-if00:/dev/zwave" \
    -v "/home/pi/store:/usr/src/app/store" \
    zwavejs/zwave-js-ui:latest

