# Version Consistency Diagram

## Single Source of Truth Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Version Source Files                       │
│                                                              │
│   .nvmrc                     .python-version                 │
│   ┌──────────┐              ┌───────────┐                   │
│   │ v20.18.2 │              │  3.12.12  │                   │
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
│   .nvmrc, no     │          │   ↓              │
│   shell profile  │          │                  │
│   needed)        │          │                  │
│ • pyenv install  │          │                  │
│   3.12.12        │          │                  │
│                  │          │   ↓              │
│ just dev         │          │ FROM node:       │
│   ↓              │          │ 20.18.2-alpine   │
│ dev_orchestrator │          │ FROM python:     │
│   ↓              │          │ 3.12-alpine      │
│ Runs services    │          │                  │
│ with nvm/pyenv   │          │ Deployed to      │
│ versions (no     │          │ Home Assistant   │
│ shell profile    │          │                  │
│ required)        │          │                  │
└──────────────────┘          └──────────────────┘

        ✅                              ✅
   Node v20.18.2                  Node v20.18.2
   Python 3.12.12                 Python 3.12.12
```

All local steps source the repo's bootstrap script (`talos/scripts/nvm_use.sh`) so Node is initialized without touching the user's shell profile; the only assumption is that `brew` is already on `PATH`. Python is handled by `talos/setup_dev_env.sh` using pyenv directly.

## Upgrade Flow

```
1. Update Version File
   ┌─────────────────────┐
   │ echo "v21.0.0" >    │
   │      .nvmrc         │
   └─────────────────────┘
             │
             │ Single file update
             ▼
   ┌─────────────────────────────────────┐
   │ Both environments updated           │
   │ automatically                       │
   └─────────────────────────────────────┘
             │
             ├──────────────┬────────────────┐
             ▼              ▼                ▼
      ┌──────────┐   ┌──────────┐    ┌──────────┐
      │just setup│   │just      │    │Dockerfile│
      │          │   │ha-addon  │    │updated   │
      │Installs  │   │          │    │with new  │
      │v21.0.0   │   │Rebuilds  │    │FROM      │
      │via nvm   │   │images    │    │node:21   │
      └──────────┘   └──────────┘    └──────────┘
```

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Version Definition** | Hardcoded in multiple files | Single `.nvmrc` / `.python-version` |
| **Docker Version** | Manual Dockerfile updates | Auto-read from version files |
| **Local Version** | Manual nvm/pyenv commands | Auto-installed by `just setup` |
| **Consistency** | Manual verification needed | Guaranteed by build system |
| **Upgrades** | Update 3+ locations | Update 1 file |
| **Documentation** | Manual updates | Auto-generated in Dockerfile |

## Version Propagation Timeline

```
Change .nvmrc
    ↓ (0 seconds)
Version file updated
    ↓ (immediate)
├─→ just setup (10-60 seconds)
│       ↓
│   talos/scripts/nvm_use.sh installs new Node (sources nvm itself)
│       ↓
│   just dev uses new version
│
└─→ just ha-addon (5-10 seconds)
        ↓
    Dockerfile generated with new version
        ↓
    just deploy (30-90 seconds)
        ↓
    Home Assistant running new version
```

## Verification Commands

```bash
# Check local versions match version files
$ node --version
v20.18.2                    # ← Should match .nvmrc

$ python --version
Python 3.12.12              # ← Should match .python-version

# Check Docker will use correct versions
$ just ha-addon sonos-api
$ head build/home-assistant-addon/sonos_api/Dockerfile
# Node.js version: 20.18.2 (from .nvmrc)  ← Auto-generated
FROM node:20.18.2-alpine    ← Matches .nvmrc

$ just ha-addon printer
$ head build/home-assistant-addon/printer_service/Dockerfile
# Python version: 3.12.12 (from .python-version)  ← Auto-generated
FROM python:3.12-alpine     ← Matches .python-version
```
