# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a smart home automation system that integrates with Home Assistant, Sonos, Hue lights, and Z-Wave devices. The system is structured as a collection of Home Assistant add-ons providing custom web interfaces and API endpoints for smart home control.

## Architecture

The project consists of several Home Assistant add-ons and configuration tools:

1. **grid-dashboard** - Home Assistant add-on providing the main web dashboard UI (TypeScript/Node.js ExpressServer)
2. **sonos-api** - Home Assistant add-on providing a custom Sonos API wrapper
3. **node-sonos-http-api** - Home Assistant add-on for node-sonos-http-api integration
4. **new-hass-configs** - Home Assistant configuration files including automations and scenes
5. **new-hass-configs/MetaHassConfig** - Python tool that generates Home Assistant configuration from a metaconfig.yaml file
6. **new-hass-configs/HomeAssistantConfig** - Legacy Home Assistant configs (being phased out in favor of new-hass-configs)

## Key Commands

### Home Assistant Configuration Management

```bash
cd new-hass-configs

# Fetch current configuration from Home Assistant
just fetch

# Validate configuration changes (dry-run)
just check

# Deploy configuration to Home Assistant and restart
just push
```

### Grid Dashboard Development & Deployment

```bash
cd grid-dashboard

# Install dependencies
cd ExpressServer && npm install

# Run development server with auto-reload
cd ExpressServer && npm run dev

# Run tests
cd ExpressServer && npm test

# Build Home Assistant add-on
just ha-addon

# Deploy add-on to Home Assistant
just deploy

# Collect diagnostic report
just report
```

### Sonos API Add-on Development & Deployment

```bash
cd sonos-api

# Build Home Assistant add-on
just ha-addon

# Deploy add-on to Home Assistant
just deploy
```

### MetaHassConfig Development (Legacy)

```bash
cd new-hass-configs/MetaHassConfig
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py develop
hassmetagen ../HomeAssistantConfig/metaconfig.yaml  # Generate Home Assistant config
```

## Deployment Process

1. Home Assistant runs at hostname `homeassistant.local` (accessed via SSH on port 22)
2. Add-ons are built locally into tarball packages using build scripts
3. Add-ons are deployed via rsync to Home Assistant and installed via `ha addons install`
4. Home Assistant configuration is managed via the `new-hass-configs/Justfile` recipes
5. The system requires passwordless SSH access to Home Assistant for deployment

## Important Files

- `new-hass-configs/metaconfig.yaml` - Legacy master configuration for Home Assistant entities
- `new-hass-configs/configuration.yaml` - Main Home Assistant configuration
- `grid-dashboard/ExpressServer/src/server/index.ts` - Main Express server entry point for dashboard
- `sonos-api/src/server/index.ts` - Sonos API wrapper entry point
- `docs/` - Documentation including setup guides, Sonos routing, and ingress fixes

## Error Handling and Stability

### Sonos API Error Handling

The system includes error handling to prevent crashes from transient Sonos API failures:

1. **node-sonos-http-api patches**: Runtime patches are applied during Docker build to handle SOAP errors gracefully
   - `node-sonos-http-api/patches/group-error-handling.patch` - Adds retry logic (3 attempts, 1s delay) for join operations
   - `node-sonos-http-api/patches/server-crash-prevention.patch` - Global uncaught exception handler
   - Patches use `-p1` format and are applied via the Dockerfile template

2. **grid-dashboard error handling**: HTTP proxy includes error handlers to catch 500 status codes from sonos API
   - Implemented in `grid-dashboard/ExpressServer/src/server/sonos.ts`
   - Returns JSON error responses instead of crashing

### Modifying Error Handling Patches

When updating patches for node-sonos-http-api:
- Clone the upstream repo: `git clone https://github.com/jishi/node-sonos-http-api.git`
- Make changes to the cloned files
- Generate patches with `diff -Naur a/ b/` format (for `-p1` compatibility)
- Place patch files in `node-sonos-http-api/patches/`
- Patches are auto-applied during Docker build via `tools/templates/Dockerfile.j2`
- Bump version in `node-sonos-http-api/package.json` to force Docker image rebuild
- Use `ha addons rebuild local_node_sonos_http_api` to force rebuild without version change

## Z-Wave Device Notes

- Dimmer switch 46203 requires manual command class updates for scene support (see README.md:134-163)
- Zooz Zen31 RGBW Dimmer needs specific setting changes after adding (see README.md:165-171)

