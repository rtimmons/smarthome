Smarthome Dashboard
============================

## Setup and Install

- Buy 🍓pi 3 and sd card
    - pi3 is the only one tested for now. Zero W should work with minor tweaks to ansible code, though.
    - don't get a cheap sd card. Pay the extra $5.
	- install heatsink, put in case, plug into wall. Heatsink is apparently necessary.
- Follow [setup steps](./setup.md)

## TODO

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

- state management
	- periodically update volume %age

- ui foo
	- why is the `<marquee>` for the status not clipping and scrolling?

- code foo
	- don't do fixed html table, just let code generate grid. Assign `x,y` values and then listeners?
	- pull hook or something to update cache.manifest since mobile safari doesn't refresh very well


## System Ideas / Dumping Ground



- Look into [HomeBridge](https://github.com/nfarina/homebridge)

- Look into [openHab](http://www.openhab.org/)

- Look into "Home Assistant" as detailed by holman [here][ha]
  [ha]: https://stackshare.io/holman/decisions/101735320676191302

- Look into [Nekmo/amazon-dash](https://github.com/Nekmo/amazon-dash) as an
  alternative to Dasher

- Incorporate [mozilla open gateway][moz]. OR: [node-red][nr]?

 [moz]: https://techcrunch.com/2018/02/06/mozilla-announces-an-open-framework-for-the-internet-of-things/
 [nr]:  https://nodered.org/

Scrub for ideas <https://news.ycombinator.com/item?id=16874208>:

> I basically followed this guide for the web camera parts: https://pimylifeup.com/raspberry-pi-webcam-server/

> I setup my pi without keyboard and monitor (ssh only), and used this guide to set it up itself: https://www.losant.com/blog/getting-started-with-the-raspber...

> Here's the list of my hardware: https://www.canakit.com/raspberry-pi-zero-wireless.html https://www.canakit.com/raspberry-pi-camera-v2-8mp.html
