Setup
=====

Mostly formalizing [this article](http://desertbot.io/ssh-into-pi-zero-over-usb/).
But modifying for Raspberry Pi B.

Download Raspbian Jessie (lite - no desktop).
https://www.raspberrypi.org/downloads/raspbian/
-> https://downloads.raspberrypi.org/raspbian_lite_latest

Burn to SD card using etcher https://etcher.io/

Mount to mac

Run this:

    touch /Volumes/boot/ssh
    # only for pi zero
    # sed -i .bak 's/rootwait/rootwait modules-load=dwc2,g_ether/' /Volumes/boot/cmdline.txt
    # echo "dtoverlay=dwc2" >> /Volumes/boot/config.txt

Unmount, plug card into rpi, and connect to your computer using ethernet cable.
Takes about 30 seconds to boot up.

Then ssh in once to add to your known_hosts

    ssh pi@raspberrypi.local
    # default password is raspberry
    # just exit after logging in
    
Then enable passwordless SSH:

    ssh-copy-id pi@raspberrypi.local

Then copy`vars/secret-example.yml` to `vars/secret.yml`.
Then `./setup-wifi.sh`
Then restart without ethernet plugged in. 
    Just unplug the thing violently from power. Then more gently unplug ethernet.
    This restart takes about 45 seconds since it checks the filesystem after your senseless violence.
Then `./deploy.sh`

todo:
- user specify hostname and pi user's password to set during wifi-setup to facilitate multiple instances
