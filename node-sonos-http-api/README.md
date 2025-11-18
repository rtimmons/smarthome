# Node Sonos HTTP API Home Assistant Add-on

This is a Home Assistant add-on that wraps the [node-sonos-http-api](https://github.com/jishi/node-sonos-http-api) project, providing a simple HTTP API for controlling Sonos speakers.

## Building

```bash
just ha-addon
```

This will create the add-on package in `build/home-assistant-addon/node_sonos_http_api/` and a tarball at `build/home-assistant-addon/node_sonos_http_api.tar.gz`.

## Deploying

```bash
just deploy
```

Or with custom Home Assistant host:

```bash
HA_HOST=homeassistant.local just deploy
```

## Configuration

The add-on exposes the following configuration options:

- `sonos_discovery_timeout`: Timeout in seconds for discovering Sonos speakers (default: 5)

## Architecture

This add-on:
- Runs on port 5005
- Uses host networking to discover Sonos devices on your network
- Clones and runs the official node-sonos-http-api from GitHub
- Is accessible to other add-ons via `http://node-sonos-http-api:5005`

## API Documentation

For full API documentation, see: https://github.com/jishi/node-sonos-http-api
