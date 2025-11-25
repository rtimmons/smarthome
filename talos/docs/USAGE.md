# Talos Usage Guide

This guide covers common talos operations and workflows for developing and deploying Home Assistant add-ons.

## Table of Contents

- [Installation](#installation)
- [CLI Commands](#cli-commands)
- [Common Workflows](#common-workflows)
- [Add-on Configuration](#add-on-configuration)
- [Environment Management](#environment-management)
- [Troubleshooting](#troubleshooting)

## Installation

### Quick Start

From the repository root:

```bash
# Automated setup (recommended)
just setup
```

This runs `talos/setup_dev_env.sh` which:
- Installs system dependencies (Homebrew, cairo, etc.)
- Installs and configures nvm for Node.js version management
- Installs and configures pyenv for Python version management
- Installs correct Node.js version from `.nvmrc`
- Installs correct Python version from `.python-version`
- Builds talos CLI into `talos/build/bin/talos`
- Runs `pre_setup` hooks for all add-ons
- Installs dependencies for each add-on

### Manual Talos Build

If you only need to rebuild talos:

```bash
cd talos
./build.sh
```

This creates an isolated Python virtualenv in `talos/build/venv` and installs talos as an editable package.

### Using Talos Directly

Optionally add talos to your PATH for direct access:

```bash
export PATH="$PWD/talos/build/bin:$PATH"
talos --help
```

Otherwise, invoke via the `just` commands which automatically ensure talos is built.

## CLI Commands

### Add-on Commands

#### List Add-ons

```bash
talos addon list
```

Shows all discovered add-ons with their slugs and ports.

#### Get Add-on Names

```bash
# Human-readable
talos addon names

# JSON array (for scripting)
talos addon names --json
```

#### Build Add-on

```bash
talos addon build <name>
```

Builds a Home Assistant add-on:
1. Discovers `<name>/addon.yaml`
2. Reads runtime versions from `.nvmrc` and `.python-version`
3. Renders Jinja2 templates (Dockerfile, config.yaml, run.sh, etc.)
4. Copies source files
5. Creates tarball in `build/home-assistant-addon/<slug>.tar.gz`

**Example:**
```bash
talos addon build grid-dashboard
# Output: build/home-assistant-addon/grid_dashboard.tar.gz
```

#### Deploy Add-on

```bash
talos addon deploy <name> [options]
```

Deploys an add-on to Home Assistant:
1. Builds the add-on (if not already built)
2. SCPs tarball to Home Assistant host
3. Extracts to `/addons/<slug>/`
4. Stops running instance (if exists)
5. Runs `ha addons reload`
6. Rebuilds or installs the add-on
7. Starts the add-on

**Options:**
- `--ha-host <host>` - Home Assistant hostname (default: `homeassistant.local`)
- `--ha-port <port>` - SSH port (default: `22`)
- `--ha-user <user>` - SSH user (default: `root`)
- `--dry-run` - Print commands without executing

**Example:**
```bash
# Deploy with defaults
talos addon deploy printer

# Deploy to custom host
talos addon deploy printer --ha-host 192.168.1.100 --ha-user admin

# Dry run to see what would happen
talos addon deploy printer --dry-run
```

**Environment variables** (as fallback to options):
- `HA_HOST` - Home Assistant hostname
- `HA_PORT` - SSH port
- `HA_USER` - SSH username

#### Test Add-on

```bash
talos addon test <name>
```

Runs tests defined in the add-on's `addon.yaml` file under the `tests` key.

**Example:**
```bash
talos addon test grid-dashboard
# Runs: npm test && npm run check (from addon.yaml)
```

### Batch Operations

#### Run Just Recipe Across Add-ons

```bash
talos addons run <recipe> [addon1 addon2 ...]
```

Runs a Just recipe for each add-on that has it defined.

**Examples:**
```bash
# Run 'ha-addon' recipe for all add-ons
talos addons run ha-addon

# Run 'test' recipe for specific add-ons
talos addons run test grid-dashboard sonos-api

# Run 'deploy' recipe (includes pre-deploy steps: generate, build, test, ha-addon)
talos addons run deploy
```

**Special handling for `deploy` recipe**: Automatically runs these pre-deploy recipes if they exist:
1. `generate`
2. `build`
3. `test`
4. `ha-addon`
5. `deploy`

### Development Commands

#### Start Development Environment

```bash
talos dev
```

Starts all add-ons locally with:
- Dependency resolution and ordered startup
- Prerequisite checking (node_modules, venv, etc.)
- Environment variable mapping (production URLs → localhost)
- Unified log output with timestamps
- Graceful shutdown on Ctrl+C

**Example output:**
```
🚀 Starting smart home development environment...
Discovered 4 addon(s)
Startup order: node-sonos-http-api → sonos-api → grid-dashboard → printer

Starting services...
[node-sonos-http-api 10:30:15] Starting: npm start
[node-sonos-http-api 10:30:18] Listening on http://localhost:5005
[sonos-api 10:30:20] Starting: npm run dev
[sonos-api 10:30:23] Listening on http://localhost:5006

✨ Running services
   • Grid Dashboard         http://localhost:3000
   • Sonos API             http://localhost:5006
   • Node Sonos HTTP API   http://localhost:5005
   • Printer Service       http://localhost:8099

Press Ctrl+C to stop all services.
```

### Port Management

#### List Port Usage

```bash
talos ports list
```

Shows which processes are using add-on ports.

#### Kill Processes on Add-on Ports

```bash
talos ports kill

# Force kill (SIGKILL instead of SIGTERM)
talos ports kill --force
```

Useful when `just dev` reports port conflicts.

### Lifecycle Hooks

#### Run Hook

```bash
talos hook run <addon> <hook> [--if-missing-ok]
```

Manually runs a lifecycle hook for an add-on.

**Available hooks:**
- `pre_setup` - Run before installing dependencies
- `pre_start` - Run before starting service in dev mode

**Examples:**
```bash
# Run pre_setup hook for node-sonos-http-api
talos hook run node-sonos-http-api pre_setup

# Run hook but don't fail if it doesn't exist
talos hook run printer pre_start --if-missing-ok
```

## Common Workflows

### First-Time Setup

```bash
# From repository root
just setup
```

This is a wrapper for `talos/setup_dev_env.sh` which handles everything.

### Daily Development

```bash
# Start all services
just dev

# In another terminal, make code changes
# Services auto-reload on file changes

# Run tests
just test

# Stop services
# (Ctrl+C in the terminal running 'just dev')
```

### Build and Deploy Single Add-on

```bash
# Build locally
just ha-addon grid-dashboard

# Deploy to Home Assistant
just deploy grid-dashboard
```

### Build and Deploy All Add-ons

```bash
# Build all
just ha-addon

# Deploy all (also deploys Home Assistant configs)
just deploy
```

### Test Before Deploy

```bash
# Run tests for specific add-on
just test grid-dashboard

# Run tests for all add-ons
just test
```

### Fix Port Conflicts

```bash
# List what's using add-on ports
just ports list

# Kill all processes on add-on ports
just kill

# Try dev again
just dev
```

### Upgrade Runtime Versions

```bash
# Update Node.js version
echo "v20.19.0" > .nvmrc

# Update Python version
echo "3.13.0" > .python-version

# Rebuild local environment
just setup

# Rebuild Docker images (picks up new versions)
just ha-addon

# Deploy
just deploy
```

## Add-on Configuration

### Anatomy of addon.yaml

```yaml
# Basic metadata
slug: my_addon                    # Slug for Home Assistant (underscores, not hyphens)
name: My Addon                    # Display name
description: What this addon does # Brief description
url: https://github.com/user/repo # Repository URL (optional)

# Source configuration
source_subdir: src                # If source is in subdirectory (optional)
copy:                             # Files/directories to include in Docker image
  - src
  - package.json
  - package-lock.json

# Runtime selection
python: false                     # true for Python addons, false for Node.js
python_module: my_addon.app       # Python module to run (if python: true)
npm_build: false                  # Run 'npm run build' during Docker build

# Container configuration
container_workdir: /opt/my-addon/app
homeassistant_min: "2024.6.0"     # Minimum Home Assistant version

# Networking
host_network: false               # Use host network mode (usually false)
ports:
  "8080": 8080                    # Container port: host port
ports_description:
  "8080": "HTTP API port"

# Ingress (Home Assistant sidebar integration)
ingress: true                     # Enable ingress
ingress_entry: "/"                # Entry path for ingress
panel_icon: "mdi:view-dashboard"  # Icon for sidebar
panel_title: "My Addon"           # Title for sidebar

# Permissions
homeassistant_api: true           # Access to Home Assistant API
auth_api: false                   # Require Home Assistant auth
usb: false                        # USB device access
audio: false                      # Audio device access
gpio: false                       # GPIO access

# Volume mappings
map:
  - type: share                   # Map /share directory
    read_only: false

# Options (user-configurable)
options:
  some_setting: "default_value"
schema:
  some_setting: "str?"            # Type validation

# Environment variables (for both dev and production)
run_env:
  - env: PORT                     # Static value
    value: "8080"
  - env: API_URL                  # Value from user options
    from_option: api_url
    default: "http://localhost:5000"
    optional: false               # Fail if not provided

# Git clone (for upstreams like node-sonos-http-api)
git_clone:
  repo: https://github.com/user/repo.git
  target: upstream                # Directory to clone into
  ref: main                       # Branch/tag/commit (optional)

# Tests (run by 'talos addon test <name>')
tests:
  - npm test
  - npm run lint
```

### Common Patterns

#### Node.js Add-on

```yaml
slug: my_node_addon
name: My Node Addon
python: false
copy:
  - src
  - package.json
  - package-lock.json
ports:
  "3000": 3000
run_env:
  - env: PORT
    value: "3000"
tests:
  - npm test
```

#### Python Add-on with uv

```yaml
slug: my_python_addon
name: My Python Addon
python: true
python_module: my_addon.app
copy:
  - src
  - pyproject.toml
  - uv.lock
ports:
  "8000": 8000
run_env:
  - env: PORT
    value: "8000"
tests:
  - just test  # Runs: uv run pytest
```

#### Add-on with Dependencies

```yaml
slug: dashboard
name: Dashboard
python: false
copy:
  - src
  - package.json
ports:
  "3000": 3000
run_env:
  - env: PORT
    value: "3000"
  - env: API_URL                           # Depends on another add-on
    from_option: api_url
    default: "http://local-api-addon:5000" # Production URL
    # In dev mode, talos converts to: http://localhost:5000
```

## Environment Management

### Version Management

Talos reads runtime versions from:
- **`.nvmrc`** - Node.js version (e.g., `v20.18.2`)
- **`.python-version`** - Python version (e.g., `3.12.12`)

These files control:
1. Local development (via nvm/pyenv)
2. Docker base images (via template rendering)
3. Documentation comments in generated files

### Environment Variables in Development

When running `talos dev`, environment variables are set according to `run_env` in `addon.yaml`, with automatic URL substitution:

| Production URL | Development URL |
|----------------|-----------------|
| `http://local-<slug>:<port>` | `http://localhost:<port>` |
| `/share/path` | `/tmp/path` |
| `mongodb://mongodb:27017` | `mongodb://localhost:27017` |

### Environment Variables in Production

In production (Docker containers), environment variables come from:
1. `environment` - Static env vars in Dockerfile
2. `run_env` with `from_option` - User-configurable via Home Assistant UI
3. Home Assistant supervisor - Ingress paths, API tokens, etc.

## Troubleshooting

### Talos Not Found

```bash
# Rebuild talos
./talos/build.sh

# Or via just
just setup
```

### Add-on Not Discovered

Check that:
1. Add-on directory is at repository root level
2. `addon.yaml` file exists in add-on directory
3. `addon.yaml` is valid YAML

```bash
# List discovered add-ons
talos addon list
```

### Build Fails - Missing Source Files

Check the `copy` list in `addon.yaml` includes all necessary files:

```yaml
copy:
  - src                 # Include src directory
  - package.json        # Include package.json
  - package-lock.json   # Include lockfile
```

### Deploy Fails - SSH Connection

Check SSH access:

```bash
# Test SSH manually
ssh -p 22 root@homeassistant.local

# If this fails, add your SSH key to Home Assistant
# In Home Assistant: Supervisor → SSH Server → Configuration → Authorized keys
```

### Dev Fails - Port Conflict

```bash
# See what's using the ports
talos ports list

# Kill processes on add-on ports
talos ports kill

# Retry
talos dev
```

### Dev Fails - Missing Dependencies

```bash
# Run setup for specific add-on
cd <addon-directory>
npm install  # or: uv sync

# Or run full setup
just setup
```

### Template Error During Build

If you see Jinja2 template errors, check:
1. All required fields are in `addon.yaml`
2. No syntax errors in `addon.yaml`
3. Templates in `talos/src/talos/templates/` are valid

```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('<addon>/addon.yaml'))"
```

### Service Won't Start in Dev Mode

Check logs for:
1. Missing environment variables
2. Incorrect working directory
3. Failed pre_start hook

Enable debug mode for more verbose output (edit `talos/src/talos/dev.py` and set log level).

### Wrong Runtime Version

```bash
# Check current versions
node --version
python --version

# Check expected versions
cat .nvmrc
cat .python-version

# Reinstall correct versions
just setup
```

## Advanced Usage

### Custom Dockerfile

If you need a custom Dockerfile instead of the generated one:

```yaml
# In addon.yaml
custom_dockerfile: true
```

Then create `<addon>/Dockerfile` which will be copied instead of generated.

### Custom run.sh

Create `<addon>/run.sh` (must be executable) and it will be used instead of the generated one.

### Adding New Lifecycle Hooks

Create executable scripts in `<addon>/local-dev/hooks/`:

```bash
mkdir -p my-addon/local-dev/hooks
cat > my-addon/local-dev/hooks/pre_start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Running pre-start checks..."
# Your checks here
exit 0
EOF
chmod +x my-addon/local-dev/hooks/pre_start.sh
```

### Running Talos Tests

```bash
cd talos
build/venv/bin/python -m pip install -e '.[test]'
build/venv/bin/python -m pytest tests
```

## See Also

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Talos design and internals
- [IMPROVEMENTS.md](./IMPROVEMENTS.md) - Recent improvements and recommendations
- [../../docs/hooks-guide.md](../../docs/hooks-guide.md) - Lifecycle hooks guide
- [../../docs/version-management.md](../../docs/version-management.md) - Runtime version management
- [../../docs/dev-setup.md](../../docs/dev-setup.md) - Development environment setup
- [../../CLAUDE.md](../../CLAUDE.md) - Full repository development guide
