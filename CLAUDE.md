# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Expectations (repo-wide)
- You start in a sandbox: request permission before `git add` or any command that would take the git lock.
- Prefer `just …` or the provided environment wrappers (`.venv`, `nvm`, etc.) for Python/Node tooling; avoid unmanaged binaries.
- “Prepare to commit” means stage all changes (with permission), run `just test`, and place the proposed commit message in `./msg` without staging that file.

## Project Overview

This is a smart home automation system that integrates with Home Assistant, Sonos, Hue lights, and Z-Wave devices. The system is structured as a collection of Home Assistant add-ons providing custom web interfaces and API endpoints for smart home control.

## Development Guidelines for Claude Code

### Using Just Command Wrappers

This project uses [just](https://github.com/casey/just) as a command runner. **ALWAYS prefer `just` commands over raw commands** when they are available:

**✅ Correct approach:**
- Run tests: `just test` (not `npm test` or `pytest`)
- Setup project: `just setup` (not `pip install` or `npm install`)
- Build add-ons: `just ha-addon` (not manual Docker builds)
- Deploy: `just deploy` (not manual rsync/scp)

**Justfile locations:**
- **Root Justfile** (`/Justfile`): Commands that operate on all add-ons or the entire project
  - `just test` - Run tests for all add-ons
  - `just setup` - Install all dependencies for local development
  - `just dev` - Start all services with auto-reload
  - `just ha-addon [addon]` - Build Home Assistant add-on(s)
  - `just deploy [addon]` - Deploy add-on(s) to Home Assistant

- **Add-on Justfiles**: Each add-on directory has its own Justfile with add-on-specific commands
  - `grid-dashboard/Justfile`
  - `sonos-api/Justfile`
  - `printer/Justfile`
  - `new-hass-configs/Justfile`

**When to check for Justfiles:**
1. Before running any build, test, or deployment command
2. When setting up a new development environment
3. When running common operations (tests, builds, installs)

**How to discover available commands:**
```bash
# List all available just commands in current directory
just --list

# Or simply read the Justfile
cat Justfile
```

**Exception:** Only use raw commands when:
- No `just` wrapper exists for the operation
- You're implementing a new feature that requires direct tool access
- Debugging requires bypassing the wrapper

## Architecture

The project consists of several Home Assistant add-ons and configuration tools:

1. **grid-dashboard** - Home Assistant add-on providing the main web dashboard UI (TypeScript/Node.js ExpressServer)
2. **sonos-api** - Home Assistant add-on providing a custom Sonos API wrapper
3. **node-sonos-http-api** - Home Assistant add-on for node-sonos-http-api integration
4. **printer** - Home Assistant add-on for kitchen label printing (Python/Flask)
5. **new-hass-configs** - Home Assistant configuration managed by a TypeScript generator plus manual overrides

### Add-on Configuration

Each add-on has its own `addon.yaml` file in its directory:
- `grid-dashboard/addon.yaml`
- `sonos-api/addon.yaml`
- `node-sonos-http-api/addon.yaml`
- `printer/addon.yaml`

The build system automatically discovers add-ons by globbing for `*/addon.yaml` files. This enables:
- Decentralized configuration (each add-on owns its own config)
- Cross-repository add-ons via symlinks
- Easy addition of new add-ons without central manifest updates

### Runtime Version Management

Runtime versions are managed via **single source of truth** files:
- **`.nvmrc`** - Node.js version (e.g., `v20.18.2`)
- **`.python-version`** - Python version (e.g., `3.9.0`)

These files control versions in:
- ✅ Local development (nvm/pyenv)
- ✅ Docker images (base image selection)
- ✅ Documentation (auto-generated comments)

To upgrade a runtime version, simply update the file and run `just setup` (local) or `just ha-addon` (Docker). See `docs/version-management.md` for details.

## Key Commands

### Local Development

```bash
# First-time setup (automated)
just setup

# Start all services locally with auto-reload
just dev

# Services will be available at:
# - Grid Dashboard: http://localhost:3000
# - Sonos API: http://localhost:5006
# - Node Sonos HTTP API: http://localhost:5005
# - Printer Service: http://localhost:8099
```

**First-time setup**: Run `just setup` to automatically install all dependencies. See `docs/dev-setup.md` for manual setup or troubleshooting.

**Features**:
- Auto-discovers all add-ons from `*/addon.yaml` files
- Starts services in dependency order
- Unified logs with timestamps and service-name prefixes
- File watching and auto-reload (where supported)
- Graceful shutdown with Ctrl+C
- Automatic environment variable mapping (production → localhost URLs)

### Home Assistant Configuration Management

```bash
cd new-hass-configs

# Fetch current configuration from Home Assistant
just fetch

# Validate configuration changes (dry-run)
just check

# Deploy configuration to Home Assistant and restart
just deploy
```

### Interrogating Live Home Assistant System

The `hass-cli` command is available for querying and controlling the live Home Assistant instance:

```bash
# Check entity state
hass-cli state get light.light_office_abovecouch

# List entities matching a pattern
hass-cli state list | grep abovecouch

# Trigger a scene
hass-cli service call scene.turn_on --arguments 'entity_id=scene.office_high'
```

**Use cases:**
- Verifying scene behavior on the live system
- Checking entity states for debugging
- Testing automations and services
- Comparing generated config vs. deployed state

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

## Deployment Process

1. Home Assistant runs at hostname `homeassistant.local` (accessed via SSH on port 22)
2. Add-ons are built locally into tarball packages using build scripts
3. Add-ons are deployed via rsync to Home Assistant and installed via `ha addons install`
4. Home Assistant configuration is managed via the `new-hass-configs/Justfile` recipes
5. The system requires passwordless SSH access to Home Assistant for deployment

## Important Files

- `new-hass-configs/configuration.yaml` - Main Home Assistant configuration
- `new-hass-configs/Justfile` - fetch/generate/check/deploy automation
- `new-hass-configs/config-generator/src/` - TypeScript source for devices, scenes, and automations
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

## Scene Configuration

### RGBW Device Pairing

**CRITICAL:** RGBW devices (like Zooz Zen31 dimmers) create two separate entities in Home Assistant:
- Base entity: `light.light_office_abovecouch` (controls RGB channels)
- White entity: `light.light_office_abovecouch_white` (controls white channel)

**These entities MUST be kept in sync in all scenes** to ensure consistent behavior. The scene generator automatically handles this via the `expandLightsWithPairs()` function in `config-generator/src/generate.ts:54`.

**How automatic pairing works:**
1. Define only ONE entity in a scene (either base or `_white`)
2. The generator automatically adds the paired entity with matching state/brightness
3. Both entities are included in the deployed scene configuration

**Example from `config-generator/src/scenes.ts`:**
```typescript
office_high: {
  name: "Office - High",
  lights: [
    {
      device: "office_abovecouch_white",  // Only define _white
      state: "on",
      brightness: 255
    }
    // office_abovecouch is automatically added by expandLightsWithPairs()
  ]
}
```

**Verification:**
```bash
# Check generated config includes both entities
grep -A 20 "Office - High" generated/scenes.yaml

# Verify on live system after deployment
hass-cli service call scene.turn_on --arguments 'entity_id=scene.office_high'
hass-cli state get light.light_office_abovecouch
hass-cli state get light.light_office_abovecouch_white
```

**Note:** After modifying scenes, always run `just deploy` from `new-hass-configs/` to deploy the updated configuration to Home Assistant.

## Z-Wave Device Notes

- Dimmer switch 46203 requires manual command class updates for scene support (see README.md:134-163)
- Zooz Zen31 RGBW Dimmer needs specific setting changes after adding (see README.md:165-171)
