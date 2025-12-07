# Printer Service Add-on

Home Assistant add-on for generating and printing kitchen labels via Brother/ESC/POS printers.

## Home Assistant Add-on Development

This add-on follows [Home Assistant add-on development standards](../reference-repos/developers.home-assistant/docs/add-ons.md). For official guidance:

- **[Add-on Development Guide](../reference-repos/developers.home-assistant/docs/add-ons.md)** — Official development standards
- **[Add-on Configuration](../reference-repos/developers.home-assistant/docs/add-ons/configuration.md)** — config.yaml reference
- **[Add-on Testing](../reference-repos/developers.home-assistant/docs/add-ons/testing.md)** — Testing with devcontainer (recommended)

## Development

### Prerequisites
- Start with the repo guide: [`../AGENTS.md`](../AGENTS.md)
- Run `just setup` from repo root (installs system deps via Homebrew and creates `.venv`)

### Local Development Options

#### Option 1: Home Assistant Devcontainer (Recommended)
Follow the [official devcontainer setup](../reference-repos/developers.home-assistant/docs/add-ons/testing.md) for full Home Assistant integration testing.

#### Option 2: Local Development (Fast Iteration)
- **Port**: 8099 for local dev
- **Start server**: `just start` (Flask dev server with auto-reload)
- **Tests**: `just test` (runs ruff/mypy/pytest)
- **Visual diff**: `visual-diff*` recipes for UI regression testing

### Building & Deployment
- **Local container**: `just build` (builds local container image)
- **Home Assistant build**: `just ha-addon` (builds HA add-on)
- **Deploy**: `just deploy` (builds and deploys to Home Assistant)

### Add-on Configuration
See [`addon.yaml`](addon.yaml) for complete configuration. Key features:
- **Ingress**: Enabled with Home Assistant sidebar integration
- **USB**: Supports USB printer access
- **Share**: Access to `/share` directory for label output
- **Environment**: Python with Flask/uv
- **Backends**: Brother network, ESC/POS USB/Bluetooth, file output
