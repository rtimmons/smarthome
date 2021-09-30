Setup
=====

Goal is for the rpi to be [cattle not a pet](https://www.theregister.co.uk/2013/03/18/servers_pets_or_cattle_cern/), so the entire build and deploy process is designed to 

1. have a custom hostname so you can have multiple raspberry pis on your network.
2. not require **ever** plugging in a keyboard or monitor.

You will need 

1. to plug your rpi into your router's ethernet so your computer and the rpi can be on the same network (same subnet I think for the `.local` thing to work).
2. You also cannot have any existing hosts with the `raspberrypi.local` hostname since this whole process assumes that this is the hostname for the machine it's going to provision. The first step will change the hostname to whatever you want though so you can have multiple rpis on your network if they all have distinct hostnames.
3. The setup isn't in any way "offline" - your rpi will need to connect to the internet to download dependencies. I tried without luck to get the apt packages it needs pre-burned onto the SD card, but my linux-foo isn't up to par.
4. I've written/tested/designed to have this work from a mac. There's nothing inherently mac-specific here, though. Replace `brew` with whatever you use to install things and I think that's it. (Oh and whatever it takes to mount SD cards...I assume you can mount an sd card at `/Volumes/boot` which is what the mac's default behavior is here)


(Below steps are mostly formalizing [this article](http://desertbot.io/ssh-into-pi-zero-over-usb/), but modifying for Raspberry Pi 3 model B.)

First:
Download Raspbian Jessie (lite - no desktop) from [here](https://www.raspberrypi.org/downloads/raspbian/).
This redirects here for the impatient:
https://downloads.raspberrypi.org/raspbian_lite_latest
**NOTE 2021-09-30**: This doc was created when latest was "Buster".
(I've not tried other distros but I assume they'll work - we really only need systemd and `apt-get` I think.)

Burn to SD card using [etcher](https://etcher.io/).

Mount SD card to your computer.

Run this:

```sh
touch /Volumes/boot/ssh
# only for pi zero
# sed -i .bak 's/rootwait/rootwait modules-load=dwc2,g_ether/' /Volumes/boot/cmdline.txt
# echo "dtoverlay=dwc2" >> /Volumes/boot/config.txt
```

Unmount, plug card into rpi, and connect to your router using an ethernet cable. 

Then plug in power to rpi. Takes about 30 seconds to boot up. There's no obvious indicator when it's done booting other than that the next step doesn't timeout trying to find the host.

Then enable passwordless SSH:

```sh
# if necessary, install ssh-copy-id
brew install ssh-copy-id

ssh-copy-id 'pi@raspberrypi.local'
```

This will ask you to confirm adding to your `known_hosts` file.

Default password is `raspberry`.

If you've re-burned the image (starting over) or have otherwise connected to another host named `raspberrypi.local`, ssh will complain. You need to modify `~/.ssh/known_hosts` and just remove the line containing `raspberrypi.local`.

If you want to change the hostname, modify `./Ansible/vars/main.yml`.

Then:

```sh
./Ansible/setup-networking.sh

# Do a manual update of apt packages first to make the update process faster/easier.
ssh pi@raspberrypi.local
$> apt-get update --allow-releaseinfo-change
$> sudo apt-get upgrade
# Takes about 6.5 minutes :(
$> sudo /sbin/reboot -h now
# Takes about 75 seconds

./Ansible/deploy.sh
```

## 🔥

If things go funky, you can start over pretty easily.

1. Unplug rpi from power.
2. Remove any lines from  your `~/.ssh/known_hosts` file that have `raspberrypi.local` or your chosen hostname in them.
3. GOTO top of this file and start over, you ninny.

