# Local Development Environment

## Overview

This document describes the local development environment for all Home Assistant add-ons in this repository. The goal is to enable fast, iterative development without requiring Docker containers or a Home Assistant instance. For upstream expectations, see [`reference-repos/developers.home-assistant/docs/add-ons/testing.md`](../reference-repos/developers.home-assistant/docs/add-ons/testing.md) and [`communication.md`](../reference-repos/developers.home-assistant/docs/add-ons/communication.md) for how add-ons are validated and exposed by the Supervisor, plus [`reference-repos/developers.home-assistant/docs/supervisor/development.md`](../reference-repos/developers.home-assistant/docs/supervisor/development.md) when mirroring Supervisor APIs locally. Refer to [`reference-repos/addons/README.md`](../reference-repos/addons/README.md) for canonical add-on metadata/base-image patterns and [`reference-repos/frontend/README.md`](../reference-repos/frontend/README.md) when troubleshooting ingress/UI behavior that mirrors Home Assistant’s frontend.

## The Challenge

The smart home system consists of 4 Home Assistant add-ons:

1. **node-sonos-http-api** (port 5005) - Upstream Node.js service for Sonos control
2. **sonos-api** (port 5006) - Custom TypeScript proxy for node-sonos-http-api
3. **grid-dashboard** (port 3000) - TypeScript/Express dashboard UI with Home Assistant integration
4. **printer** (port 8099) - Python/Flask service for label printing

### Dependency Chain
```
node-sonos-http-api:5005
    ↓
sonos-api:5006
    ↓
grid-dashboard:3000

printer:8099 (standalone)
```

### Current Pain Points
- Development requires building Docker images and deploying to Home Assistant
- No local iteration cycle - changes require `just deploy` and waiting for container rebuild
- No unified way to start all services locally
- Runtime environments (Node/Python versions, env vars) differ between local dev and production
- No centralized logging or file watching

## Goals

### Primary Goal
Run `just dev` from the repository root to:
- Start all 4 services with correct runtime versions (Node v20.18.2, Python 3.10+)
- Watch for file changes and auto-reload services
- Display unified logs with `[service-name HH:MM:SS]` prefixes
- Provide localhost URLs for accessing each service
- Match production environment variables and configuration

### Secondary Goals
- Keep add-ons fully functional for `just deploy` to Home Assistant
- Minimal changes to existing add-on code
- Use native toolchains (npm, python/uv) instead of Docker
- Auto-detect runtime versions from `.nvmrc`, `.python-version`, and add-on configs

## Architecture Plan

### Service Configuration
Each add-on has its own `addon.yaml` file in its directory (e.g., `grid-dashboard/addon.yaml`). The local development configuration:
1. Discovers add-ons by globbing for `*/addon.yaml` files
2. Reads runtime requirements from individual add-on manifests
3. Sets environment variables based on `run_env` specifications
4. Exposes services on localhost with production port numbers
5. Enables file watching and auto-reload where available

This decentralized approach allows add-ons to be added via symlinks across repositories.

### Orchestration Tool
A new development orchestrator (Python script or Justfile recipes) will:
1. Discover all add-ons by finding `*/addon.yaml` files
2. Determine start order based on dependencies
3. Launch each service with appropriate runtime and env vars
4. Multiplex logs with timestamps and service prefixes
5. Handle graceful shutdown of all services

### Runtime Management
- **Node.js**: Managed by `talos/scripts/nvm_use.sh` (sources nvm itself) to ensure v20.18.2 from `.nvmrc` without shell profile tweaks
- **Python**: Use `uv` or venv with Python 3.10+ (from `.python-version` and pyproject.toml)

### File Watching
- **Node services**: Leverage existing `npm run dev` scripts with `supervisor` or `nodemon`
- **Python services**: Use Flask's built-in reload or `watchdog`
- Fall back to process restart if hot reload unavailable

## Implementation Phases

### Phase 1: Discovery and Documentation ✅
- [x] Survey all add-ons and their structure
- [x] Document dependencies and runtime requirements
- [x] Identify existing dev commands (npm run dev, etc.)
- [x] Create this documentation file

### Phase 2: Service Startup Infrastructure
- [x] Refactor to decentralized `*/addon.yaml` structure
- [ ] Create Talos dev orchestrator to discover addon.yaml files
- [ ] Implement service dependency resolution
- [ ] Add environment variable interpolation from `run_env` configs
- [ ] Create individual service launchers with correct runtimes
- [ ] Test starting each service individually

### Phase 3: Unified Logging and Process Management
- [ ] Implement log multiplexing with service name prefixes
- [ ] Add timestamp formatting `[service HH:MM:SS]`
- [ ] Handle process lifecycle (start, stop, restart)
- [ ] Graceful shutdown on Ctrl+C
- [ ] Color-coded output per service (optional enhancement)

### Phase 4: File Watching and Auto-Reload
- [ ] Enable file watching for TypeScript services (grid-dashboard, sonos-api)
- [ ] Enable file watching for Python service (printer)
- [ ] Handle node-sonos-http-api (git cloned dependency - may need special handling)
- [ ] Test auto-reload functionality

### Phase 5: Integration and Polish
- [ ] Add `just dev` command to root Justfile
- [ ] Display startup banner with service URLs
- [ ] Add `just dev-stop` for cleanup if needed
- [ ] Test full development workflow
- [ ] Document common development tasks

### Phase 6: Add-on Compatibility
- [ ] Ensure `just deploy` still works for all add-ons
- [ ] Verify add-on build process unchanged
- [ ] Test deployed add-ons on Home Assistant
- [ ] Update AGENTS.md with new development workflow

## Current Status

**Phase**: 2 (Infrastructure) ✅ Complete | Ready for Use 🎉

**Completed**:
- ✅ Surveyed all 4 add-ons (node-sonos-http-api, sonos-api, grid-dashboard, printer)
- ✅ Identified runtime requirements (Node v20.18.2, Python 3.10+)
- ✅ Mapped service dependencies
- ✅ Located existing dev scripts
- ✅ Refactored to decentralized `*/addon.yaml` structure (supports cross-repo symlinks)
- ✅ Added Talos add-on builder that discovers add-ons via globbing
- ✅ Tested build process with new structure
- ✅ Created Talos dev orchestrator with full orchestration
- ✅ Implemented add-on discovery from `*/addon.yaml`
- ✅ Dependency graph resolution and startup ordering
- ✅ Environment variable interpolation and localhost URL mapping
- ✅ Log multiplexing with service prefixes and timestamps
- ✅ Process management with graceful shutdown
- ✅ Prerequisite checking (node_modules, uv.lock)
- ✅ Added `just dev` command

**Quick Start**:
```bash
# First-time setup (automated)
just setup

# Start development environment
just dev
```

**What's Working**:
- ✅ Addon discovery and configuration parsing
- ✅ Dependency resolution (node-sonos-http-api → sonos-api → grid-dashboard)
- ✅ Unified log output with timestamps and color-coded service names
- ✅ Automatic env var mapping (production URLs → localhost URLs)
- ✅ Prerequisite validation before starting services
- ✅ Graceful shutdown on Ctrl+C

**Known Issues** (see docs/dev-setup.md for solutions):
- 🔧 printer: Requires system library `cairo` (install via `brew install cairo`)
- 🔧 node-sonos-http-api: Requires upstream git clone (one-time setup)
- 🔧 All addons: Require `npm install` or `uv sync` before first run

## Service Details

### node-sonos-http-api
- **Type**: Node.js (upstream git clone)
- **Port**: 5005
- **Source**: `node-sonos-http-api/` (git clone from https://github.com/jishi/node-sonos-http-api.git)
- **Runtime**: Node v20.18.2
- **Start**: Clone repo → `npm install` → `npm start`
- **Env vars**: `PORT=5005`, `SONOS_DISCOVERY_TIMEOUT=5`
- **Watch**: May need nodemon or supervisor (not in upstream)
- **Dependencies**: None

### sonos-api
- **Type**: TypeScript/Node.js
- **Port**: 5006
- **Source**: `sonos-api/`
- **Runtime**: Node v20.18.2
- **Start**: `npm run dev` (uses supervisor)
- **Env vars**: `PORT=5006`, `APP_PORT=5006`, `SONOS_BASE_URL=http://localhost:5005`
- **Watch**: ✅ Built-in via supervisor
- **Dependencies**: node-sonos-http-api

### grid-dashboard
- **Type**: TypeScript/Node.js/Express
- **Port**: 3000
- **Source**: `grid-dashboard/ExpressServer/`
- **Runtime**: Node v20.18.2
- **Start**: `npm run dev` (uses supervisor)
- **Env vars**: `PORT=3000`, `APP_PORT=3000`, `SONOS_BASE_URL=http://localhost:5006`, `HASS_WEBHOOK_BASE=`, `INGRESS_ENTRY=`, `NODE_OPTIONS=--enable-source-maps`
- **Watch**: ✅ Built-in via supervisor
- **Dependencies**: sonos-api

### printer
- **Type**: Python/Flask
- **Port**: 8099
- **Source**: `printer/`
- **Runtime**: Python 3.10+
- **Start**: `uv run printer-service` or activate venv + `printer-service`
- **Env vars**:
  - `FLASK_HOST=0.0.0.0`
  - `FLASK_PORT=8099`
  - `LABEL_OUTPUT_DIR=/tmp/printer-labels` (local override)
  - `PRINTER_BACKEND=file`
  - `PRINTER_DEV_RELOAD=1` (enables Flask auto-reload)
- **Watch**: ✅ Flask built-in reload with `PRINTER_DEV_RELOAD=1`
- **Dependencies**: None

## Technical Decisions

### Why Not Docker Compose?
The goal is to avoid containers entirely and run natively on macOS for faster iteration. This also ensures the local environment closely matches what runs in the add-on containers.

### Why Python for Orchestration?
- Talos build tooling already uses Python
- Excellent process management libraries (subprocess, asyncio)
- Easy log multiplexing and formatting
- YAML parsing for add-on manifests

### Local vs Production Environment Differences
| Aspect | Production (Add-on) | Local Development |
|--------|---------------------|-------------------|
| Sonos API URL | `http://local-sonos-api:5006` | `http://localhost:5006` |
| Node Sonos URL | `http://local-node-sonos-http-api:5005` | `http://localhost:5005` |
| Printer output | `/share/printer-labels` | `/tmp/printer-labels` |
| Home Assistant API | Available via supervisor | Not available (mock or skip) |
| Ingress | Via HA supervisor | Direct port access |

### Runtime Version Management
- **Node**: Use the repo wrapper (`talos/scripts/nvm_use.sh`) which sources nvm directly and pins to `.nvmrc` (v20.18.2) without requiring shell init files
- **Python**: Use `uv` with `pyproject.toml` requirements, or fallback to venv with `.python-version`

## Configuration Structure

Each add-on now has its own `addon.yaml` file:

```
grid-dashboard/
  addon.yaml          # Add-on config
  ExpressServer/      # Actual source (referenced via source_subdir)
sonos-api/
  addon.yaml          # Add-on config
  src/                # Source is in same directory
node-sonos-http-api/
  addon.yaml          # Add-on config
  patches/            # Patches to apply
printer/
  addon.yaml          # Add-on config
  src/                # Source is in same directory
```

The Talos add-on builder discovers add-ons by globbing `*/addon.yaml`, enabling:
- Decentralized configuration (each add-on owns its config)
- Cross-repository symlinks (symlink an external add-on directory)
- Easier per-addon development

## Open Questions

1. **node-sonos-http-api setup**: Should we git clone on first run, or require manual setup?
2. **Home Assistant API mocking**: Do we need to mock supervisor API calls for local dev?
3. **Ingress simulation**: Should we add a reverse proxy for ingress paths, or just use direct ports?
4. **Sonos hardware**: Can node-sonos-http-api discover Sonos speakers from macOS, or do we need mocks?
5. **Parallel vs Sequential startup**: Start all services in parallel, or wait for dependencies?

## Example: Target User Experience

```bash
$ just dev

🚀 Starting smart home development environment...

[init 10:15:33] Checking runtimes: Node v20.18.2 ✓, Python 3.10 ✓
[init 10:15:33] Resolving dependencies: node-sonos-http-api → sonos-api → grid-dashboard, printer
[init 10:15:34] Starting services...

[node-sonos-http-api 10:15:35] Installing dependencies...
[node-sonos-http-api 10:15:42] Listening on http://localhost:5005
[sonos-api 10:15:43] Installing dependencies...
[sonos-api 10:15:48] Listening on http://localhost:5006
[grid-dashboard 10:15:49] Installing dependencies...
[grid-dashboard 10:15:55] Listening on http://localhost:3000
[printer 10:15:56] Installing dependencies...
[printer 10:15:59] Listening on http://localhost:8099

✨ All services running!
   • Grid Dashboard:      http://localhost:3000
   • Sonos API:          http://localhost:5006
   • Node Sonos HTTP API: http://localhost:5005
   • Printer Service:     http://localhost:8099

Press Ctrl+C to stop all services.

[grid-dashboard 10:16:15] File changed: src/server/index.ts
[grid-dashboard 10:16:16] Restarting...
[grid-dashboard 10:16:18] Listening on http://localhost:3000
```

## Future Enhancements

- Service health checks and readiness probes
- Parallel log file output for debugging
- Integration tests that run against local services
- VS Code tasks.json for one-click debugging
- Service-specific configuration overrides via `.env.local`
