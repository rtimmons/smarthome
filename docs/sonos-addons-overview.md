# Sonos Home Assistant Add-ons Overview

This project now includes two Home Assistant add-ons for Sonos control:

## 1. Node Sonos HTTP API Add-on

**Location:** `node-sonos-http-api/`

This add-on wraps the official [node-sonos-http-api](https://github.com/jishi/node-sonos-http-api) project.

### What it does:
- Runs the actual node-sonos-http-api server
- Discovers and controls Sonos speakers on your network
- Provides the base HTTP API for Sonos control
- Runs on port 5005
- Uses host networking to discover Sonos devices

### Building:
```bash
cd node-sonos-http-api
just ha-addon
```

### Deploying:
```bash
cd node-sonos-http-api
just deploy
# Or with custom host:
HA_HOST=smarterhome5.local just deploy
```

### Configuration:
- `sonos_discovery_timeout`: Timeout in seconds for discovering Sonos speakers (default: 5)
- `presets.json`: Place at `/config/node-sonos-http-api/presets.json` (auto-linked). If missing, the add-on
  will create and use `/data/node-sonos-http-api/presets.json` so presets persist across restarts. If nothing is present,
  the bundled `presets.example.json` is copied there on first start. Per-preset files in `/config/node-sonos-http-api/presets/`
  are also supported.
- Default TV presets from the legacy Ansible install are stored in `node-sonos-http-api/presets/`
  and combined in `node-sonos-http-api/presets.example.json` for quick copy into `/config/node-sonos-http-api/`.

### Access:
- External: `http://<ha-host>:5005`
- From other add-ons: `http://node-sonos-http-api:5005`

## 2. Sonos API Add-on

**Location:** `sonos-api/`

This add-on is a TypeScript/Express proxy that adds custom convenience routes on top of node-sonos-http-api.

### What it does:
- Proxies all node-sonos-http-api endpoints via `/sonos/*`
- Adds custom convenience routes:
  - `/pause`, `/play` - Basic playback control
  - `/tv` - Switch all speakers to TV mode
  - `/07` - Play Zero 7 Radio
  - `/quiet` - Set group volume to 7
  - `/same/:room` - Sync all volumes in a room's zone
  - `/down`, `/up` - Smart volume control
- Runs on port 5006

### Dependencies:
**IMPORTANT:** This add-on requires the Node Sonos HTTP API add-on to be installed and running first.

### Building:
```bash
cd sonos-api
just ha-addon
```

### Deploying:
```bash
cd sonos-api
just deploy
```

### Configuration:
- `sonos_base_url`: Base URL for node-sonos-http-api (default: `http://node-sonos-http-api:5005`)

### Access:
- External: `http://<ha-host>:5006`
- From other add-ons: `http://sonos-api:5006`

## Installation Order

1. **First**, install and start the **Node Sonos HTTP API** add-on
2. **Then**, install and start the **Sonos API** add-on

The Sonos API add-on will automatically connect to the Node Sonos HTTP API add-on using the hostname `node-sonos-http-api`.

## Architecture

```
┌─────────────────────────────────────────┐
│  Home Assistant                         │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Sonos API Add-on                 │  │
│  │ Port: 5006                       │  │
│  │ Custom convenience routes        │  │
│  └──────────┬───────────────────────┘  │
│             │                           │
│             │ http://node-sonos-http-api:5005
│             │                           │
│  ┌──────────▼───────────────────────┐  │
│  │ Node Sonos HTTP API Add-on       │  │
│  │ Port: 5005                       │  │
│  │ Discovers & controls Sonos       │  │
│  └──────────┬───────────────────────┘  │
│             │                           │
└─────────────┼───────────────────────────┘
              │ Host Network
              │ SSDP/UPnP Discovery
              ▼
    ┌──────────────────┐
    │ Sonos Speakers   │
    │ on local network │
    └──────────────────┘
```

## Development

### Node Sonos HTTP API Add-on
This add-on clones and runs the upstream node-sonos-http-api directly from GitHub, so no local development is needed. The upstream project is maintained at: https://github.com/jishi/node-sonos-http-api

### Sonos API Add-on
For local development of the custom proxy:

```bash
cd sonos-api
npm install
npm run dev
```

Set environment variables to point to your node-sonos-http-api instance:
```bash
export SONOS_BASE_URL=http://localhost:5005
export PORT=5006
npm run dev
```
