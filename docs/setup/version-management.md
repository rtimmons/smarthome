# Runtime Version Management

## Overview

This project uses **single source of truth** files for runtime versions to ensure consistency across all environments:

- **`.nvmrc`** - Defines Node.js version for all environments
- **`.python-version`** - Defines Python version for all environments

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   Version Source Files                       │
│                                                              │
│   .nvmrc                     .python-version                 │
│   ┌──────────┐              ┌───────────┐                   │
│   │ v24.18.0 │              │  3.14.6  │                   │
│   └──────────┘              └───────────┘                   │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ Read by all tools
                        ▼
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│ Local Dev        │          │ Docker/Prod      │
│                  │          │                  │
│ just setup       │          │ just ha-addon    │
│   ↓              │          │   ↓              │
│ setup_dev_env.sh │          │ addon_builder.py │
│   ↓              │          │   ↓              │
│ • talos/scripts/ │          │ read_runtime_    │
│   nvm_use.sh     │          │ versions()       │
│   (installs      │          │   ↓              │
│   Node from      │          │ Dockerfile.j2    │
│   .nvmrc)        │          │ templates        │
│                  │          │                  │
│ • talos/scripts/ │          │ FROM node:{{ ... │
│   pyenv_use.sh   │          │ FROM python:{{ ..│
│   (installs      │          │                  │
│   Python from    │          │                  │
│   .python-ver)   │          │                  │
└──────────────────┘          └──────────────────┘
```

## Version Files

### `.nvmrc`
```
v24.18.0
```

Controls Node.js version for:
- Local development (via nvm)
- Docker images (via base image selection)
- CI/CD pipelines (if configured)

`node-sonos-http-api` is an explicit compatibility exception: its upstream
package declares Node `<23`, so Talos builds that app with the per-app
`node_version` in its `addon.yaml` while maintained local services use the
repository-wide Node 24 pin.

### `.python-version`
```
3.14.6
```

Controls Python version for:
- Local development (via pyenv)
- Docker images (via base image selection)
- CI/CD pipelines (if configured)

## How It Works

### Local Development

**Setup script (`just setup`):**
1. Installs nvm (via Homebrew) if not available
2. Reads `.nvmrc` to determine required Node.js version
3. Uses nvm to install and activate that version
4. Installs pyenv (via Homebrew) if not available
5. Reads `.python-version` to determine required Python version
6. Uses pyenv to install and activate that version

**No shell profile modifications required** - nvm and pyenv are initialized automatically by the setup and dev scripts.

**Dev orchestrator (`just dev`):**
- Services run with the versions installed by nvm/pyenv
- No manual version switching required

### Docker/Production

**Build process (`just ha-addon`, `just deploy`):**
1. `talos addon build` reads `.nvmrc` and `.python-version`
2. Passes versions to Dockerfile template
3. Dockerfile uses specific base images:
   - Node addons: `FROM node:24.18.0-alpine`
   - Python addons: `FROM python:3.14-alpine`

**Resulting Dockerfiles include version comments:**
```dockerfile
# Version pinning based on .nvmrc and .python-version
# Node.js version: 24.18.0 (from .nvmrc)
# Python version: 3.14.6 (from .python-version)

FROM node:24.18.0-alpine
```

## Upgrading Runtime Versions

To upgrade Node.js or Python across **all environments**, simply update the version files:

### Upgrade Node.js

```bash
# Update .nvmrc
echo "v20.19.0" > .nvmrc

# Rebuild locally
just setup  # Installs new Node version via nvm
just dev    # Uses new version

# Rebuild Docker images
just ha-addon  # Generates Dockerfiles with new version
just deploy    # Deploys to Home Assistant
```

### Upgrade Python

```bash
# Update .python-version
echo "<new-python-version>" > .python-version

# Rebuild locally
just setup  # Installs new Python version via pyenv
just dev    # Uses new version

# Rebuild Docker images
just ha-addon  # Generates Dockerfiles with new version
just deploy    # Deploys to Home Assistant
```

## Version Consistency Guarantees

### Guaranteed Consistency

- **Node.js version** in Docker exactly matches `.nvmrc`
- **Python version** in Docker exactly matches `.python-version` (minor version)
- **Local development** uses same versions as Docker (when nvm/pyenv available)
- **Per-app runtime overrides** are explicit in `addon.yaml`

### 📝 Minor Version Matching

- Python Docker images use minor version (3.14) from `.python-version` (3.14.6)
- This allows patch updates in Docker base images while maintaining compatibility

## Verification

Check what versions are being used:

```bash
# Check local versions
node --version   # Should match .nvmrc
python --version # Should match .python-version

# Check Docker build versions
just ha-addon sonos-api
cat build/home-assistant-addon/sonos_api/Dockerfile | head -10
```

Output should show:
```dockerfile
# Node.js version: 24.18.0 (from .nvmrc)
FROM node:24.18.0-alpine
```

## Benefits

1. **Single Source of Truth**: Update one file, changes everywhere
2. **No Version Drift**: Local and production always match
3. **Easy Upgrades**: Change one file to upgrade across all services
4. **Documented**: Dockerfiles include comments showing version source
5. **Automated**: Setup script handles installation automatically

## Troubleshooting

### Local version doesn't match

```bash
# Force reinstall with correct versions
just setup
```

### Docker using wrong version

```bash
# Rebuild add-ons to pick up new versions
just ha-addon all
```

### Version file doesn't exist

The build system uses defaults if files are missing:
- Node.js: 24.18.0
- Python: 3.14.6

Create the files to override:
```bash
echo "v24.18.0" > .nvmrc
echo "3.14.6" > .python-version
```
