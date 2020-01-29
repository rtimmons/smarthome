Smarthome Dashboard
============================

## Setup and Install

- Buy 🍓pi 3 and sd card
    - pi3 is the only one tested for now. Zero W should work with minor tweaks to ansible code, though.
    - don't get a cheap sd card. Pay the extra $5.
	- install heatsink, put in case, plug into wall. Heatsink is apparently necessary.
- Follow [setup steps](./setup.md)

## TODO

- Fix sonos discovery bug (bug in dependency):

    ```
    /home/pi/node-sonos-http-api/node_modules/sonos-discovery/lib/models/Player.js:188
    get: () => getState(state, _this.coordinator._state, _this.hasSub ? _this.sub : null)
    ^
    TypeError: Cannot read property '_state' of undefined
    at Player.get (/home/pi/node-sonos-http-api/node_modules/sonos-discovery/lib/models/Player.js:188:50)
    at Object.state (/home/pi/node-sonos-http-api/lib/actions/state.js:4:33)
    at handleAction (/home/pi/node-sonos-http-api/lib/sonos-http-api.js:117:35)
    at HttpAPI.requestHandler (/home/pi/node-sonos-http-api/lib/sonos-http-api.js:94:21)
    at /home/pi/node-sonos-http-api/server.js:52:13
    at Server.finish (/home/pi/node-sonos-http-api/node_modules/node-static/lib/node-static.js:111:13)
    at finish (/home/pi/node-sonos-http-api/node_modules/node-static/lib/node-static.js:170:14)
    at /home/pi/node-sonos-http-api/node_modules/node-static/lib/node-static.js:144:17
    at FSReqCallback.oncomplete (fs.js:169:21)
    ```

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

- make development more sustainable
    - UI
        - webpack/babel (https://www.evernote.com/l/AAGQBWjMhuBLYqbDMKJfcYJ6hrRv73LLnxE)
        - consider react but meh
        - def want typescript
    - ExpressServer
        - mocha testing
        - better live-reload situation
    - JS in general (UI and ExpressServer)
        - lint and format js
    - repo
        - plugin model (all the ui stuff together including ansible, etc)
    - ansible
        - remove deprecations
        - lint yaml
        - figure out if there is anything running as root that shouldn't be
    - integrations
        - Grafana for metrics

## System Ideas / Dumping Ground

- Look into home-assistant.io?
  [See HN Thread for other things to consider too](https://news.ycombinator.com/item?id=21665125)

- Maybe [Lutron Caséta][lc]?

- Look into [HomeBridge](https://github.com/nfarina/homebridge)

- Look into [openHab](http://www.openhab.org/)

- Look into "Home Assistant" as detailed by holman [here][ha]
  [ha]: https://stackshare.io/holman/decisions/101735320676191302

- Incorporate [mozilla open gateway][moz]. OR: [node-red][nr]?

 [moz]: https://techcrunch.com/2018/02/06/mozilla-announces-an-open-framework-for-the-internet-of-things/
 [nr]:  https://nodered.org/
 [lc]:  http://www.lutron.com/en-US/Products/Pages/SingleRoomControls/CasetaWireless/Overview.aspx


Scrub for ideas <https://news.ycombinator.com/item?id=16874208>:

> I basically followed this guide for the web camera parts: https://pimylifeup.com/raspberry-pi-webcam-server/

> I setup my pi without keyboard and monitor (ssh only), and used this guide to set it up itself: https://www.losant.com/blog/getting-started-with-the-raspber...

> Here's the list of my hardware: https://www.canakit.com/raspberry-pi-zero-wireless.html https://www.canakit.com/raspberry-pi-camera-v2-8mp.html
