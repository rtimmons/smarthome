# Grid Dashboard Add-on

Home Assistant add-on providing a dashboard UI with Sonos shortcuts and webhook helpers.

## Home Assistant Add-on Development

This add-on follows [Home Assistant add-on development standards](../reference-repos/developers.home-assistant/docs/add-ons.md). For official guidance:

- **[Add-on Development Guide](../reference-repos/developers.home-assistant/docs/add-ons.md)** — Official development standards
- **[Add-on Configuration](../reference-repos/developers.home-assistant/docs/add-ons/configuration.md)** — config.yaml reference
- **[Add-on Testing](../reference-repos/developers.home-assistant/docs/add-ons/testing.md)** — Testing with devcontainer (recommended)

## Development

### Prerequisites
- Read the repo-wide guide first: [`../AGENTS.md`](../AGENTS.md)
- Run `just setup` from repo root to install dependencies

### Local Development Options

#### Option 1: Home Assistant Devcontainer (Recommended)
Follow the [official devcontainer setup](../reference-repos/developers.home-assistant/docs/add-ons/testing.md) for full Home Assistant integration testing.

#### Option 2: Local Development (Fast Iteration)
- **Port**: 3000 (served via `just dev` from repo root)
- **Setup**: `just setup` then `just test` from this directory
- **Local UI dev**: `cd ExpressServer && npm run dev` (after `just setup`)
- **App code**: Lives in `ExpressServer/`

### Building & Deployment
- **Local build**: `just ha-addon` (from this directory or repo root)
- **Deploy**: `just deploy` (builds and deploys to Home Assistant)
- **Container test**: Included in `just test`

### Add-on Configuration
See [`addon.yaml`](addon.yaml) for complete configuration. Key features:
- **Ingress**: Enabled with Home Assistant sidebar integration
- **Port**: 3000 (optional direct access)
- **Environment**: Node.js with TypeScript/Express
- **Dependencies**: Requires `sonos-api` add-on
