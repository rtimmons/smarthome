# Sonos API Home Assistant Add-on

This is a Home Assistant add-on that provides a proxy API for node-sonos-http-api with custom routes and helper endpoints for controlling Sonos speakers.

## Dependencies

This add-on requires the **Node Sonos HTTP API** add-on to be installed and running. The Node Sonos HTTP API add-on provides the underlying Sonos control functionality, while this add-on adds custom convenience routes on top of it.

## Features

- Proxy all node-sonos-http-api endpoints via `/sonos/*`
- Custom convenience routes:
  - `/pause`, `/play` - Basic playback control
  - `/tv` - Switch all speakers to TV mode
  - `/07` - Play Zero 7 Radio
  - `/quiet` - Set group volume to 7
  - `/same/:room` - Sync all volumes in a room's zone
  - `/down`, `/up` - Smart volume control (pause/play when appropriate)
- Minimal Express server focused on Sonos control
- Runs on port 5006 by default

## Building and Deployment

### Build the add-on

```bash
just ha-addon
```

This creates the add-on package in `build/home-assistant-addon/sonos_api/`.

### Deploy to Home Assistant

```bash
just deploy
```

This will:
1. Build the add-on
2. Copy it to your Home Assistant host (via SSH)
3. Install and start the add-on

By default, it deploys to `homeassistant.local`. Override with environment variables:

```bash
HA_HOST=smarterhome5.local just deploy
```

## Configuration

The add-on accepts the following configuration options:

- `sonos_base_url`: Base URL for the upstream node-sonos-http-api service (default: `http://node-sonos-http-api:5005`)
  - This should point to the hostname of the Node Sonos HTTP API add-on
  - If you installed the Node Sonos HTTP API add-on with the default slug, the default value should work

## API Routes

- `GET /health` - Health check endpoint
- `GET /pause` - Pause playback
- `GET /play` - Resume playback
- `GET /tv` - Switch all speakers to TV mode
- `GET /07` - Play Zero 7 Radio
- `GET /quiet` - Set group volume to 7
- `GET /same/:room` - Sync all room volumes in the same zone as `:room`
- `GET /down` - Smart volume down (pause if volume <= 3 and playing)
- `GET /up` - Smart volume up (play if paused, otherwise increase volume)
- `GET /sonos/*` - Proxy any request to the underlying node-sonos-http-api

## Development

### Local Development

```bash
npm install
npm run dev
```

The server will start on port 5006 and auto-reload on changes.

### Environment Variables

- `PORT` or `APP_PORT`: Server port (default: 5006)
- `SONOS_BASE_URL` or `SONOS_URL`: Base URL for node-sonos-http-api (default: http://localhost:5005)

## Project Structure

```
sonos-api/
├── src/
│   ├── server/
│   │   ├── index.ts      # Main Express server
│   │   ├── config.ts     # Configuration handling
│   │   └── sonos.ts      # Sonos routes
│   └── types/
│       └── sonos/
│           └── index.ts  # TypeScript type definitions
├── scripts/
│   ├── build_ha_addon.sh   # Build script
│   └── deploy_ha_addon.sh  # Deployment script
├── package.json
├── tsconfig.json
├── Justfile
└── README.md
```
