
Setup WPA2 Over USB
-------------------

Mostly formalizing [this article](http://desertbot.io/ssh-into-pi-zero-over-usb/).

Download Raspbian Jessie (lite - no desktop).
https://www.raspberrypi.org/downloads/raspbian/
-> https://downloads.raspberrypi.org/raspbian_lite_latest

Burn to SD card using etcher https://etcher.io/

Mount to mac

Run this:

    touch /Volumes/boot/ssh

    cat /Volumes/boot/cmdline.txt \
        | sed 's/rootwait/rootwait modules-load=dwc2,g_ether/' \
        > /tmp/cmd.txt
    mv /tmp/cmd.txt /Volumes/boot/cmdline.txt

    echo "dtoverlay=dwc2" >> /Volumes/boot/config.txt

Unmount, plug card into rpi, and connect via usb.

    ssh-keygen -R raspberrypi.local
    ssh pi@raspberrypi.local

