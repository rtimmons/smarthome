Smarthome Dashboard
============================

## Setup and Install

- Buy 🍓pi 3 and sd card
    - pi3 is the only one tested for now. Zero W should work with minor tweaks to ansible code, though.
    - don't get a cheap sd card. Pay the extra $5.
	- install heatsink, put in case, plug into wall. Heatsink is apparently necessary.
- Follow [setup steps](./setup.md)

## TODO

- 2022-11-28: Maybe try out Phoenix personal radio station thing https://github.com/pncnmnp/phoenix10.1

- Debounce track next button(s): pressing it once can sometimes skip 2 tracks.

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

- flic buttons (they run on Bluetooth LTE) are setup in their own Flic iOS app

- known bug / issue with openzwave starting to bork
  https://github.com/home-assistant/core/issues/5501
  "Hass crashes Aeotec Gen 5 zwave stick #5501"

## System Ideas / Dumping Ground

- Look at what @opsnlops has:
  https://github.com/opsnlops/ha-config

- Deploy/run with [piku](https://github.com/piku/piku)?

- Maybe M5Stack e-ink tablets
  https://m5stack-store.myshopify.com/collections/black-friday/products/m5paper-esp32-development-kit-960x540-4-7-eink-display-235-ppi

- Look into methods to offload from SD Card to prevent burning it out over time
  https://news.ycombinator.com/item?id=24474309

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

## Setting up double/triple tap scene for dimmer switch 46203
The device's command class must be manually updated. If not done correctly you will see this warning in zwave logs:
```
2023-11-12 19:34:55.638 Info, Node041, Received Basic set from node 41: level=255.  Sending event notification.
2023-11-12 19:34:55.638 Detail, Node041, Notification: NodeEvent
2023-11-12 19:34:58.807 Detail, Node041,   Received: 0x01, 0x0b, 0x00, 0x04, 0x00, 0x29, 0x05, 0x5b, 0x03, 0x1f, 0x83, 0x01, 0x19
2023-11-12 19:34:58.807 Detail,
2023-11-12 19:34:58.807 Info, Node041, Received Central Scene set from node 41: scene id=1 in 7860 seconds. Sending event notification.
2023-11-12 19:34:58.807 Warning, Node041, No ValueID created for Scene 1
```


1. Add device as usual
2. Update the scene command class as follows:
```
<CommandClass id="91" name="COMMAND_CLASS_CENTRAL_SCENE" version="1" request_flags="4" innif="true" scenecount="2">
				<Instance index="1" />
				<Value type="int" genre="system" instance="1" index="0" label="Scene Count" units="" read_only="true" write_only="false" verify_changes="false" poll_intensity="0" min="-2147483648" max="2147483647" value="2" />
				<Value type="int" genre="user" instance="1" index="1" label="Top Button Scene" units="" read_only="false" write_only="false" verify_changes="false" poll_intensity="0" min="-2147483648" max="2147483647" value="7860" />
				<Value type="int" genre="user" instance="1" index="2" label="Bottom Button Scene" units="" read_only="false" write_only="false" verify_changes="false" poll_intensity="0" min="-2147483648" max="2147483647" value="7860" />
</CommandClass>
3. The metaconfig.yaml entry should have double/triple properties:
```
- name: office_switch_main
  type: dimmer switch 46203
  node_id: 41
  on_up_double: scene_office_high
  on_down_double: scene_office_off
  on_triple_up: scene_all_high
  on_triple_down: scene_all_off
```