WIP

RyMike Smart House Dashboard
============================

- http://retropie.local/d
- Deply with `./deploy`
  
## tasks/ideas.todo

- music
	- "Play all from" join button
	- Preset music
	- mute
	- pause
	- global pause

- all to TV
- all to music

- pandora
	- thumbs-up
	- skip
	- thumbs-down

- lights
	- control any hue lights
	- control any smartthings lights

- routing
	- preset room based on `#!/${room}`
	- store secrets in url to avoid checking them in

- state management
	- periodically update track
	- periodically update volume %age

- ui foo
	- automatically compute/maximize height/width of cells based on screen size
	- why is the `<marquee>` for the status not clipping and scrolling?

- code foo
	- don't do fixed html table, just let code generate grid. Assign `x,y` values and then listeners?
	- pull hook or something to update cache.manifest since mobile safari doesn't refresh very well

# Overview

- Buy 🍓pi and sd card
	- install heatsink, put in case, plug in to tv

apt-cache

sudo apt-get update
sudo apt-get upgrade
sudo /sbin/reboot
sudo apt-get install apache2 apache2-doc apache2-utils

https://retropie.org.uk/docs/Manual-Installation/

apt-get install apache2

```
cat ./id_rsa.pub | ssh pi@rypi.local 'mkdir .ssh; cat >> .ssh/authorized_keys'
```

# Graveyard

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

# Foo

```
ansible/
	roles/
		sonos-server
		httpd
		n64
```

