# Sonos API Home Assistant Add-on

This Home Assistant add-on preserves the Grid Dashboard's Sonos HTTP contract while allowing control to move from `node-sonos-http-api` to Home Assistant's native Sonos integration.

## Dependencies

`node-sonos-http-api` is required only in `node` and `shadow` modes. It remains installed during the staged migration so configuration-only rollback is fast. In `home_assistant` mode, reads and writes use the allowlisted Home Assistant media-player entities and the Supervisor token remains inside the add-on.

## Features

- Three explicit backend modes: `node`, read-only comparison `shadow`, and native `home_assistant`
- Stable `/sonos/*` read, playback, favorite, grouping, volume, and preset routes for the Dashboard
- Serialized topology operations with observable status at `/intents/sonos/status`
- Authenticated, size-bounded raster artwork proxying without exposing Home Assistant tokens
- Retained `/same/:room`, `/down`, and `/up` convenience policies
- Explicit `410` responses for the unused legacy `/pause`, `/play`, `/tv`, `/07`, and `/quiet` roots in `home_assistant` mode, with exact node pass-through retained in `node` and `shadow` for rollback
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

- `backend_mode`: `node`, `shadow`, or `home_assistant` (default: `node` for safe upgrades)
- `sonos_base_url`: node service URL used only by `node` and `shadow` modes (default: `http://local-node-sonos-http-api:5005`)

`shadow` serves and writes through node while comparing Home Assistant reads. It never mirrors a write to Home Assistant. `home_assistant` requires the add-on's `homeassistant_api` permission and a live snapshot containing every configured room and source.

Backend rollback is an option change followed by a separate add-on restart; no rebuild is required. Use the exact Supervisor POST, restart, restart-evidence, health, topology, action, and household-restoration procedure in [`docs/plan-replace-sonos-node-api.md`](../docs/plan-replace-sonos-node-api.md#rollback). Do not treat Supervisor's unchanged `started` state alone as proof that the new mode launched.

## API Routes

- `GET /health` - Health check endpoint
- `GET /sonos/zones` and `GET /sonos/:room/state` - Canonical topology and media state
- `GET /sonos/:room/artwork` - Authenticated raster artwork
- `GET /sonos/:room/{play,pause,playpause,next}` - Playback control
- `GET /sonos/:room/favorite/:name` - Allowlisted favorite selection
- `GET /sonos/:room/{join/:target,leave}` - Serialized topology mutations
- `GET /sonos/:room/groupVolume/:value` - Group volume policy
- `GET /sonos/:room/preset/:name` - Repository-owned TV presets
- `POST /intents/sonos/group-all` and `GET /intents/sonos/status` - Join-all lifecycle
- `GET /same/:room` - Sync all room volumes in the same zone as `:room`
- `GET /down` - Smart volume down (pause if volume <= 3 and playing)
- `GET /up` - Legacy smart volume up (resume `PAUSED_PLAYBACK`; otherwise increase group volume)

The deprecated root routes `/pause`, `/play`, `/tv`, `/07`, and `/quiet` intentionally have a mode-dependent migration contract: normalized `410` with zero writes in `home_assistant`, exact upstream pass-through in `node` and `shadow` until node retirement.

## Development

### Local Development

Run `just setup`, then `just dev` from this directory.

The server will start on port 5006 and auto-reload on changes.

### Environment Variables

- `PORT` or `APP_PORT`: Server port (default: 5006)
- `SONOS_BACKEND_MODE`: `node`, `shadow`, or `home_assistant`
- `SONOS_BASE_URL` or `SONOS_URL`: node URL for `node`/`shadow` development (default: `http://localhost:5005`)
- `HOME_ASSISTANT_REST_URL`, `HOME_ASSISTANT_WEBSOCKET_URL`, and `HOME_ASSISTANT_TOKEN`: non-committed local-development connection values; Supervisor supplies its own token in the add-on

## Project Structure

```
sonos-api/
├── src/
│   └── server/              # Express routers, HA client/state/actions, and tests
├── scripts/
│   └── run-tests.cjs        # Discovers and runs every server spec
├── addon.yaml               # Home Assistant add-on metadata and options
├── run.sh                   # Packaged add-on launcher
├── package.json
├── tsconfig.json
├── Justfile
└── README.md
```
