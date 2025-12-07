Smarthome Dashboard
===================

Smart home system packaged as Home Assistant add-ons (UI, Sonos control, printers, utilities) plus the generated Home Assistant configuration that ties everything together.

## Stack overview
- **grid-dashboard** — Main dashboard UI (`grid-dashboard`)
- **sonos-api** — Custom Sonos proxy (`sonos-api`)
- **node-sonos-http-api** — Upstream Sonos service with local patches (`node-sonos-http-api`)
- **printer** — Kitchen label printer service (`printer`)
- **snapshot-service** — Camera snapshot helper (`snapshot-service`)
- **tinyurl-service** — URL shortener backed by MongoDB (`tinyurl-service`)
- **mongodb** — MongoDB add-on used by utilities (`mongodb`)
- **Home Assistant config** — Generated + curated config (`new-hass-configs`)

## Getting started
- Install dependencies and build the toolchain: `just setup` (uses repo-local nvm/pyenv).
- Run everything locally: `just dev`; if a port is busy run `just kill` and retry. Services listen on localhost: 3000 (grid-dashboard), 5006 (sonos-api), 5005 (node-sonos-http-api), 8099 (printer), 4010 (snapshot-service), 4100 (tinyurl-service).
- See available recipes: `just --list` or `just addons` to view discovered add-ons.

## Deploying to Home Assistant
- Build add-ons: `just ha-addon` (or `just ha-addon <addon>`).
- Deploy add-ons and Home Assistant config: `just deploy` (or target an add-on with `just deploy <addon>`). Defaults: `HA_HOST=homeassistant.local`, `HA_PORT=22`, `HA_USER=root`.
- Printer container preflight: `just printer-image` (optionally `PRINTER_DOCKER_PLATFORM=linux/arm64 just printer-image`).

## Home Assistant configuration (`new-hass-configs`)
```bash
cd new-hass-configs
just fetch   # Pull current config from Home Assistant
just check   # Validate generated + manual changes
just deploy  # Deploy and restart Home Assistant
./iterate.sh # Capture before/after inventories while applying a scene
```

## Documentation
- **[AGENTS.md](AGENTS.md)** — Developer guide and operational procedures
- **[docs/README.md](docs/README.md)** — Complete documentation index
- **[docs/operations/improvements.md](docs/operations/improvements.md)** — Comprehensive improvements roadmap
- **[docs/setup/dev-setup.md](docs/setup/dev-setup.md)** — Development environment setup
- **[docs/development/local-development.md](docs/development/local-development.md)** — Local development workflow
