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

- Incorporate [mozilla open gateway][moz].

 [moz]: https://techcrunch.com/2018/02/06/mozilla-announces-an-open-framework-for-the-internet-of-things/