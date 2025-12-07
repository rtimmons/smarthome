# Development Environment Setup

This guide helps you set up the local development environment for the first time.

## Home Assistant Development Standards

This project follows Home Assistant add-on development standards. **Read the official documentation first:**

- **[Home Assistant Development Environment](../reference-repos/developers.home-assistant/docs/development_environment.mdx)** — Official dev environment setup
- **[Add-on Development Guide](../reference-repos/developers.home-assistant/docs/add-ons.md)** — Add-on development standards
- **[Add-on Testing](../reference-repos/developers.home-assistant/docs/add-ons/testing.md)** — Testing with devcontainer (recommended)
- **[Supervisor Development](../reference-repos/developers.home-assistant/docs/supervisor/development.md)** — Supervisor API reference

## Development Approaches

### Option 1: Home Assistant Devcontainer (Recommended)

The **recommended** approach for Home Assistant add-on development is using the official devcontainer:

1. Follow the [official devcontainer setup guide](../reference-repos/developers.home-assistant/docs/add-ons/testing.md)
2. Copy the [devcontainer.json](https://github.com/home-assistant/devcontainer/raw/main/addons/devcontainer.json) to `.devcontainer/devcontainer.json`
3. Copy the [tasks.json](https://github.com/home-assistant/devcontainer/raw/main/addons/tasks.json) to `.vscode/tasks.json`
4. Open in VS Code and "Rebuild and Reopen in Container"
5. Run the "Start Home Assistant" task to bootstrap Supervisor and Home Assistant
6. Access Home Assistant at `http://localhost:7123/`

**Benefits:**
- Full Home Assistant + Supervisor environment
- Matches production exactly
- Official testing approach
- All add-ons available as local add-ons

### Option 2: Local Development (This Repository)

This repository provides a **custom local development environment** for faster iteration without containers:

#### Quick Setup (Automated)

```bash
just setup
```

This will automatically:
- ✓ Check for and install Homebrew (if on macOS)
- ✓ Check for and install system dependencies (cairo)
- ✓ Check for and install `nvm` (Node Version Manager) via Homebrew
- ✓ Check for and install `pyenv` (Python Version Manager) via Homebrew
- ✓ Install correct Node.js version (from `.nvmrc`) via nvm
- ✓ Install correct Python version (from `.python-version`) via pyenv
- ✓ Install `uv` package manager via Homebrew or pip
- ✓ Clone node-sonos-http-api upstream repository
- ✓ Install all npm dependencies for each service
- ✓ Sync Python dependencies with uv
- ✓ Create Python virtual environment

**No shell profile modifications required** - the setup script handles nvm/pyenv initialization automatically.

If the setup completes successfully, you're ready to run `just dev`!

**Benefits:**
- Fast iteration without containers
- Native toolchain performance
- Unified logging and file watching
- Matches production environment variables

**Limitations:**
- Doesn't include full Home Assistant instance
- No Supervisor API access
- Limited to add-on development only

## Manual Setup (If Needed)

If `just setup` encounters issues or you prefer manual setup:

### Prerequisites (All Installed by `just setup`)

The setup script will automatically install:
- **Homebrew**: macOS package manager
- **nvm**: Node Version Manager (via Homebrew)
- **pyenv**: Python Version Manager (via Homebrew)
- **Node.js**: v20.18.2 (via nvm)
- **Python**: 3.12.12 (via pyenv)
- **npm**: Comes with Node.js
- **uv**: Python package manager
- **cairo**: System library for printer service

### 1. Install System Dependencies

```bash
# Install Homebrew (macOS)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install system dependencies
brew install cairo nvm pyenv xz

# Install the correct Node version
# Note: nvm and pyenv are initialized automatically by just commands - no shell profile setup needed
```

### 2. Build the Talos Tooling

Talos is the isolated Python toolchain that handles add-on builds and orchestration. See `talos/README.md` for details, but the quick path is:

```bash
cd talos
./build.sh
export PATH="$PWD/build/bin:$PATH"  # optional convenience
cd ..
```

### 3. Set Up Each Add-on

#### node-sonos-http-api (Special Case)

This addon requires cloning the upstream repository:

```bash
cd node-sonos-http-api
git clone https://github.com/jishi/node-sonos-http-api.git
cd node-sonos-http-api
npm install
cd ../..
```

#### sonos-api

```bash
cd sonos-api
npm install
cd ..
```

#### grid-dashboard

```bash
cd grid-dashboard/ExpressServer
npm install
cd ../..
```

#### printer

```bash
cd printer
uv sync
cd ..
```

## Running the Development Environment

Once setup is complete, you can start all services:

```bash
just dev
```

This command uses the Talos CLI installed under `talos/build/bin`, so there's no need to activate a
virtualenv manually.
see a port conflict, run `just kill` to terminate any leftover processes that are holding the add-on
ports open, then retry `just dev`.

This will:
- Discover all add-ons
- Check prerequisites
- Start services in dependency order
- Display unified logs with timestamps
- Show service URLs

Press `Ctrl+C` to stop all services.

## Troubleshooting

### Service won't start - missing node_modules

```bash
cd <addon-directory>
npm install
```

### Service won't start - missing Python dependencies

```bash
cd <addon-directory>
uv sync
```

### node-sonos-http-api not found

Make sure you've cloned the upstream repo inside the `node-sonos-http-api` directory:

```bash
cd node-sonos-http-api
git clone https://github.com/jishi/node-sonos-http-api.git
```

### node-sonos-http-api never discovers speakers on macOS

Symptoms:

- `just dev` leaves the Node Sonos HTTP API spamming `No system has yet been discovered.`
- `node node-sonos-http-api/tools/check_sonos_multicast.js` (run automatically from `just setup` via the add-on's `pre_setup` hook) reports `EHOSTUNREACH` when it tries to send SSDP probes.

Modern macOS VPN / ZeroTrust clients (Tailscale, WARP, enterprise VPNs, etc.) install `utun` interfaces that steal the 239.255.255.250 and 255.255.255.255 routes. When that happens, macOS refuses to send the broadcast packets that Sonos uses for discovery and the HTTP API never sees your players even though you can `curl` them by IP.

Fix:

1. Disconnect or pause the VPN/ZeroTrust client so the extra `utun*` routes disappear **or** update its settings so it does not own multicast/broadcast traffic on your LAN interface.
2. On macOS Sonoma+, also disable **Private Wi-Fi Address** _and_ **Limit IP Address Tracking** for your current Wi-Fi network (System Settings → Wi-Fi → Details…). These features quietly route packets through Apple’s network extension and block SSDP.
3. Re-run `just setup` (or manually `node node-sonos-http-api/tools/check_sonos_multicast.js`) until it reports `SSDP probe ... sent`.
4. Retry `just dev`.

If you cannot disable the VPN, add static routes pointing 239.255.255.250/32 and 255.255.255.255/32 at your Wi-Fi interface (e.g. `en0`). That requires administrator privileges (`sudo route -nv change ...`) and is outside this repo's tooling, but the new setup check will confirm when the fix works.

### Local dev hooks

Each add-on can expose lifecycle hooks under `<addon>/local-dev/hooks/`. Hooks provide a lightweight interface for add-ons to participate in repo-wide workflows without hardcoding paths into `just` recipes or the orchestrator. The following hooks are currently recognized:

- `pre_setup` — executed during `just setup` via `talos hook run <addon> pre_setup --if-missing-ok`. Use this for dependency or environment validation (e.g., Sonos multicast reachability).
- `pre_start` — executed by `just dev` immediately before an add-on process is spawned.

Hooks are ordinary executables (shell scripts, Python, etc.) and should exit non-zero to block the workflow with a helpful error message. See `node-sonos-http-api/local-dev/hooks/` for an example.

### Port already in use

Another instance may be running. Run:

```bash
just kill
```

This command scans every add-on port defined in `*/addon.yaml` files and terminates whatever is
currently bound to them. Then re-run `just dev`. If you prefer to inspect manually, you can still use
`lsof -i :<port>` and `kill <pid>`.
