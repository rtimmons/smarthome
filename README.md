So WIP I can't even tell you

RyMike Smart House Dashboard
============================

- http://retropie.local/d
- Deply with `./deploy`
 
## Refocusing...

**Goal**: `./bootstrap.sh` downloads everything needed to build a complete functioning image *without an internet connection*

- https://askubuntu.com/questions/974/how-can-i-install-software-or-packages-without-internet-offline
- https://launchpad.net/keryxproject for bootstrapping deb installs (t)
- run everything thru docker?
- https://docs.resin.io/raspberrypi/nodejs/getting-started/
- http://elinux.org/RPi_Easy_SD_Card_Setup
- http://p7zip.sourceforge.net/
- `deb apt-cacher-ng`
- resin.io
- http://elinux.org/RPi_Easy_SD_Card_Setup
- https://github.com/RPi-Distro/pi-gen
- crib the interesting stuff from davidferguson's cool [pibakery](https://github.com/davidferguson/pibakery)


# Graveyard

```
apt-cache

sudo apt-get update
sudo apt-get upgrade
sudo /sbin/reboot
sudo apt-get install apache2 apache2-doc apache2-utils

https://retropie.org.uk/docs/Manual-Installation/

apt-get install apache2

cat ./id_rsa.pub | ssh pi@rypi.local 'mkdir .ssh; cat >> .ssh/authorized_keys'
```


[Download etcher][etcher] `brew cask install etcher` 
[etcher]: https://etcher.io/

install FUSE
https://downloads.sourceforge.net/project/osxfuse/osxfuse-2.8.3/osxfuse-2.8.3.dmg?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fosxfuse%2Ffiles%2Fosxfuse-3.x%2F&ts=1499394374&use_mirror=superb-dca2

Backup info
https://raspberrypi.stackexchange.com/questions/13437/how-to-mount-a-raspbian-sd-card-on-a-mac

STEP
Download rpi 3
https://retropie.org.uk/download/
https://github.com/RetroPie/RetroPie-Setup/releases/download/4.2/retropie-4.2-rpi2_rpi3.img.gz

STEP
Download
http://downloads.raspberrypi.org/NOOBS_latest
