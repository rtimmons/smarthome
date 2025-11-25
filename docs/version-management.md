# Runtime Version Management

## Overview

This project uses **single source of truth** files for runtime versions to ensure consistency across all environments:

- **`.nvmrc`** - Defines Node.js version for all environments
- **`.python-version`** - Defines Python version for all environments

## Version Files

### `.nvmrc`
```
v20.18.2
```

Controls Node.js version for:
- ✅ Local development (via nvm)
- ✅ Docker images (via base image selection)
- ✅ CI/CD pipelines (if configured)

### `.python-version`
```
3.12.12
```

Controls Python version for:
- ✅ Local development (via Homebrew + pyenv)
- ✅ Docker images (via base image selection)
- ✅ CI/CD pipelines (if configured)

**Note**: Older Python versions (3.9.x) may fail to build on modern macOS due to architecture changes. The setup script installs the requested version via Homebrew (fast prebuilt bottles), links it into pyenv, and only compiles from source when Homebrew isn't available.

## How It Works

### Local Development

**Setup script (`just setup`):**
1. Reads `.nvmrc` to determine required Node.js version
2. Uses nvm to install and activate that version
3. Reads `.python-version` to determine required Python version
4. Uses Homebrew to install and link that version into pyenv (and compiles from source only if Homebrew isn't available)

**Dev orchestrator (`just dev`):**
- Services run with the versions installed by nvm/pyenv
- No manual version switching required

### Docker/Production

**Build process (`just ha-addon`, `just deploy`):**
1. `talos addon build` reads `.nvmrc` and `.python-version`
2. Passes versions to Dockerfile template
3. Dockerfile uses specific base images:
   - Node addons: `FROM node:20.18.2-alpine`
   - Python addons: `FROM python:3.12-alpine`

**Resulting Dockerfiles include version comments:**
```dockerfile
# Version pinning based on .nvmrc and .python-version
# Node.js version: 20.18.2 (from .nvmrc)
# Python version: 3.12.12 (from .python-version)

FROM node:20.18.2-alpine
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
echo "3.13.0" > .python-version

# Rebuild locally
just setup  # Installs new Python version via pyenv
just dev    # Uses new version

# Rebuild Docker images
just ha-addon  # Generates Dockerfiles with new version
just deploy    # Deploys to Home Assistant
```

## Version Consistency Guarantees

### ✅ Guaranteed Consistency

- **Node.js version** in Docker exactly matches `.nvmrc`
- **Python version** in Docker exactly matches `.python-version` (minor version)
- **Local development** uses same versions as Docker (when nvm/pyenv available)
- **All add-ons** use the same runtime versions

### 📝 Minor Version Matching

- Python Docker images use minor version (3.12) from `.python-version` (3.12.12)
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
# Node.js version: 20.18.2 (from .nvmrc)
FROM node:20.18.2-alpine
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
- Node.js: 20.18.2
- Python: 3.12.12

Create the files to override:
```bash
echo "v20.18.2" > .nvmrc
echo "3.12.12" > .python-version
```
