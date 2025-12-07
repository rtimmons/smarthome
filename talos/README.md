# Talos CLI

Talos is the isolated build/deployment/dev toolchain for this repository. It owns all
Python-based orchestration, add-on packaging, and shared Justfile helpers.

## Quick Start

From the repository root:

```bash
# Automated setup (recommended)
just setup

# Start development environment
just dev

# Build an add-on
just ha-addon grid-dashboard

# Deploy an add-on
just deploy grid-dashboard
```

All `just` commands automatically ensure talos is built.
They also source the repo's nvm/pyenv wrappers themselves, so nothing in your shell profile is required beyond `brew` being on `PATH`.

## Manual Build

```bash
cd talos
./build.sh
export PATH="$PWD/build/bin:$PATH"  # optional convenience for direct talos usage
```

The build uses its own virtualenv under `talos/build/venv` so it never conflicts with
add-on runtimes.

## Core Commands

### Add-on Operations
- `talos addon list` — list all discovered add-ons
- `talos addon names [--json]` — output add-on names (optionally as JSON array)
- `talos addon build <name>` — render an add-on payload to `build/home-assistant-addon/`
- `talos addon deploy <name>` — scp + install the add-on on Home Assistant
- `talos addon test <name>` — run add-on-defined test hooks

### Batch Operations
- `talos addons run <recipe> [addons…]` — run a Just recipe for each add-on (used by `just ha-addon`, `just deploy`, `just test`)

### Development
- `talos dev` — start all add-ons locally with orchestration/log mux
- `talos ports list` — inspect occupied add-on ports
- `talos ports kill [--force]` — free occupied add-on ports

### Lifecycle Hooks
- `talos hook run <addon> <hook> [--if-missing-ok]` — execute local-dev hooks (e.g., `pre_setup`)

## Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Design principles, component architecture, and extension points
- **[USAGE.md](docs/USAGE.md)** — Complete command reference, common workflows, and troubleshooting

## Key Concepts

### Auto-Discovery
Talos discovers add-ons by globbing for `*/addon.yaml` files at the repository root. This enables:
- Decentralized configuration (each add-on owns its config)
- Cross-repository add-ons via symlinks
- Zero-config addition of new add-ons

### Single Source of Truth
Runtime versions come from repo-root files:
- **`.nvmrc`** — Node.js version (e.g., `v20.18.2`)
- **`.python-version`** — Python version (e.g., `3.12.12`)

These control both local development (via nvm/pyenv) and Docker base images.

### Template-Based Builds
Dockerfiles, configs, and run scripts are generated from Jinja2 templates in `talos/src/talos/templates/`,
ensuring consistency across all add-ons.

### Lifecycle Hooks
Add-ons can provide executable hooks in `<addon>/local-dev/hooks/`:
- `pre_setup` — run during `just setup`
- `pre_start` — run before starting service in `just dev`

## Project Structure

```
talos/
├── build.sh                    # Builds talos CLI into isolated venv
├── setup_dev_env.sh           # Automated first-time environment setup
├── README.md                   # This file
├── docs/
│   ├── ARCHITECTURE.md         # Design and internals
│   └── USAGE.md                # Command reference and workflows
├── pyproject.toml             # Python package definition
├── build/
│   ├── venv/                   # Isolated Python environment
│   └── bin/talos → venv/bin/talos
├── src/talos/
│   ├── cli.py                  # CLI entry point
│   ├── paths.py                # Path constants
│   ├── addon_builder.py        # Build, deploy logic
│   ├── dev.py                  # Dev orchestrator
│   ├── hooks.py                # Hook execution
│   ├── addons_runner.py        # Batch operations
│   ├── manage_ports.py         # Port management
│   └── templates/              # Jinja2 templates
├── just/
│   └── nvm.just                # Shared justfile include
├── scripts/
│   └── nvm_use.sh              # nvm loader script
└── tests/                      # Pytest tests
```

## Development Notes

- **Isolated build environment**: Talos runs in its own venv to avoid conflicts with add-on runtimes
- **Templates**: Located in `talos/src/talos/templates/` and packaged via `pyproject.toml`
- **Justfile helpers**: Shared includes in `talos/just/`
- **Tests**: Run with `pytest` from the Talos venv:
  ```bash
  cd talos
  build/venv/bin/python -m pip install -e '.[test]'
  build/venv/bin/python -m pytest tests
  ```

## See Also

- [../AGENTS.md](../AGENTS.md) — Full repository development guide
- [../docs/version-management.md](../docs/version-management.md) — Runtime version management
- [../docs/dev-setup.md](../docs/dev-setup.md) — Development environment setup
