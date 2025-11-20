# Development Environment Setup

This guide helps you set up the local development environment for the first time.

## Quick Setup (Automated)

The easiest way to get started:

```bash
just setup
```

This will automatically:
- ✓ Check for and install Homebrew (if on macOS)
- ✓ Check for and install system dependencies (cairo)
- ✓ Check for and install `nvm` (Node Version Manager)
- ✓ Check for and install `pyenv` (Python Version Manager)
- ✓ Install correct Node.js version (v20.18.2) via nvm
- ✓ Install correct Python version (from `.python-version`) via Homebrew (and link it into pyenv)
- ✓ Install `uv` package manager via Homebrew or pip
- ✓ Clone node-sonos-http-api upstream repository
- ✓ Install all npm dependencies for each service
- ✓ Sync Python dependencies with uv
- ✓ Create Python virtual environment

If the setup completes successfully, you're ready to run `just dev`!

## Manual Setup (If Needed)

If `just setup` encounters issues or you prefer manual setup:

### Prerequisites (All Installed by `just setup`)

The setup script will automatically install:
- **Homebrew**: macOS package manager
- **nvm**: Node Version Manager
- **pyenv**: Python Version Manager
- **Node.js**: v20.18.2 (via nvm)
- **Python**: 3.12.12 or compatible (via Homebrew + pyenv)
- **npm**: Comes with Node.js
- **uv**: Python package manager
- **cairo**: System library for printer service

### 1. Install System Dependencies

```bash
# Install Homebrew (macOS)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install cairo
brew install cairo

# Install nvm if you don't have it
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Install the correct Node version
nvm install
nvm use
```

### 2. Install Python Dependencies

```bash
# From repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

This command uses the `.venv` created during setup, so there's no need to activate it manually. If you
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

### Port already in use

Another instance may be running. Run:

```bash
just kill
```

This command scans every add-on port defined in `*/addon.yaml` files and terminates whatever is
currently bound to them. Then re-run `just dev`. If you prefer to inspect manually, you can still use
`lsof -i :<port>` and `kill <pid>`.
