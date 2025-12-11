# Documentation

This directory contains project-specific documentation for the smarthome repository. For contributor guidance and workflow overview, start with [`AGENTS.md`](../AGENTS.md) in the repo root.

## Quick Start

- **New contributors**: Start with [`AGENTS.md`](../AGENTS.md), then [`setup/dev-setup.md`](setup/dev-setup.md)
- **Local development**: Run `just setup` then `just dev` (see [`development/local-development.md`](development/local-development.md))
- **Add-on development**: See [Add-on Development](#add-on-development) and [Home Assistant Add-on Development](#home-assistant-add-on-development) sections below

## 📁 Documentation Structure

### 🚀 [Setup](setup/) - Getting Started & Installation
*Everything needed to get from zero to a working development environment*

- [**dev-setup.md**](setup/dev-setup.md) — First-time development environment bootstrap
- [**homeassistant-installation.md**](setup/homeassistant-installation.md) — Home Assistant OS installation guide
- [**version-management.md**](setup/version-management.md) — Node/Python version sourcing and consistency

### 💻 [Development](development/) - Active Development Workflow
*Day-to-day development activities and local environment*

- [**local-development.md**](development/local-development.md) — Orchestrated local dev and service graph
- [**configuration-sync.md**](development/configuration-sync.md) — Bidirectional Home Assistant configuration sync
- [**development-environment-summary.md**](development/development-environment-summary.md) — Implementation details and architecture

### 🔧 [Add-on Development](addon-development/) - Home Assistant Integration
*Add-on specific development concerns and Home Assistant integration*

- [**hooks-guide.md**](addon-development/hooks-guide.md) — Lifecycle hook design and usage
- [**container-runtime.md**](addon-development/container-runtime.md) — Podman/Docker runtime details
- [**ingress-fixes.md**](addon-development/ingress-fixes.md) — Home Assistant ingress integration fixes

### 🔍 [Operations](operations/) - Maintenance & Planning
*System maintenance, verification, and strategic planning*

- [**system-verification.md**](operations/system-verification.md) — System consistency verification procedures
- [**improvements.md**](operations/improvements.md) — **Comprehensive improvements roadmap**

### 🎵 [Sonos](sonos/) - Domain-Specific Architecture
*Sonos integration architecture and routing*

- [**overview.md**](sonos/overview.md) — Sonos add-on architecture
- [**routing-guide.md**](sonos/routing-guide.md) — API routing flow

## Home Assistant Add-on Development

This project follows Home Assistant add-on development standards. **Always refer to the official documentation first:**

### Essential References
- **[Add-on Development Guide](../reference-repos/developers.home-assistant/docs/add-ons.md)** — Start here for add-on development
- **[Add-on Tutorial](../reference-repos/developers.home-assistant/docs/add-ons/tutorial.md)** — Step-by-step first add-on
- **[Add-on Configuration](../reference-repos/developers.home-assistant/docs/add-ons/configuration.md)** — Complete config.yaml reference
- **[Add-on Testing](../reference-repos/developers.home-assistant/docs/add-ons/testing.md)** — Local testing with devcontainer
- **[Add-on Communication](../reference-repos/developers.home-assistant/docs/add-ons/communication.md)** — Inter-add-on networking
- **[Add-on Publishing](../reference-repos/developers.home-assistant/docs/add-ons/publishing.md)** — Container registry publishing

### Official Examples
- **[Official Add-ons Repository](../reference-repos/addons/README.md)** — Production add-on examples
- **[Example Add-on Repository](https://github.com/home-assistant/addons-example)** — Template repository

### Development Environment
- **[Development Environment Setup](../reference-repos/developers.home-assistant/docs/development_environment.mdx)** — Official dev environment guide
- **[Supervisor Development](../reference-repos/developers.home-assistant/docs/supervisor/development.md)** — Supervisor API and host behavior

## Home Assistant Installation & OS

- **[Raspberry Pi Installation](../reference-repos/home-assistant.io/source/installation/raspberrypi.markdown)** — Official installation guide
- **[Installation Troubleshooting](../reference-repos/home-assistant.io/source/installation/troubleshooting.markdown)** — Recovery and SSH setup
- **[Operating System Documentation](../reference-repos/operating-system/Documentation/README.md)** — OS internals and kernel details

## Build Tools & Workflows

### Just Command Runner
- **[Just Manual](../reference-repos/just/README.md)** — Complete just documentation and quick start
- **[Just Online Manual](https://just.systems/man/en/)** — Official online documentation
- **[Just Cheatsheet](https://cheatography.com/linux-china/cheat-sheets/justfile/)** — Syntax overview

#### Project Justfile Patterns
This repository uses `just` extensively for development workflows. Key patterns:
- **Root Justfile**: Main orchestration (`just setup`, `just dev`, `just deploy`)
- **Add-on Justfiles**: Per-add-on builds and tests (`just ha-addon`, `just test`)
- **Imported modules**: Shared functionality (e.g., `talos/just/nvm.just`)
- **Environment handling**: Automatic nvm/pyenv integration
- **Parallel execution**: Multi-add-on operations

### Frontend Development
- **[Frontend Development](../reference-repos/frontend/README.md)** — Home Assistant frontend development guide
