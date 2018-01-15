#!/usr/bin/env bash

source ./ansible-env.sh

# https://www.raspberrypi.org/downloads/raspbian/
IMAGE_ZIP="$HOME/Downloads/2017-11-29-raspbian-stretch-lite.zip"
IMAGE="$HOME/Downloads/2017-11-29-raspbian-stretch-lite.img"
if [ ! -f "$IMAGE" ]; then
    unzip "$IMAGE_ZIP"
fi

# TODO: stuff to get image onto SD card

if [ -e "/Volumes/boot" ]; then
    echo "Unmount boot volume first"
    exit 1
fi

hdiutil attach "$IMAGE" >/dev/null

# touch /Volumes/boot/ssh
# echo "dtoverlay=dwc2" >> /Volumes/boot/config.txt

cat /Volumes/boot/cmdline.txt \
    | sed 's/rootwait/rootwait modules-load=dwc2,g_ether/' \
    > /tmp/cmd.txt

