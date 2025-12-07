# Documentation

This directory contains detailed documentation for the smarthome project. Start with `AGENTS.md` in the repo root for contributor guidance.

## Contents

### Setup & Local Development
- [setup.md](setup.md) — Raspberry Pi setup through initial deployment
- [dev-setup.md](dev-setup.md) — First-time development environment bootstrap
- [local-development.md](local-development.md) — Orchestrated local dev and service graph
- [just-dev-output-example.md](just-dev-output-example.md) — Example `just dev` output

### Architecture & Add-ons
- [sonos-addons-overview.md](sonos-addons-overview.md) — Sonos add-on architecture
- [sonos-routing-guide.md](sonos-routing-guide.md) — API routing flow

### Operations & Reference
- [container-runtime.md](container-runtime.md) — Podman/Docker runtime details
- [hooks-guide.md](hooks-guide.md) — Lifecycle hook design and usage
- [version-management.md](version-management.md) — Node/Python version sourcing
- [version-consistency-diagram.md](version-consistency-diagram.md) — Runtime pinning diagrams
- [CONSISTENCY-CHECK.md](CONSISTENCY-CHECK.md) — Current consistency verification snapshot

### Historical & Roadmap
- [ingress-fixes.md](ingress-fixes.md) — Ingress fixes and history
- [SUMMARY.md](SUMMARY.md) — Local dev implementation summary
- [TODO.md](TODO.md) — Modernization roadmap and open work

## Quick Links

For project overview and quick starts, see the repo root [README.md](../README.md). For contributor/agent guidance, start with [AGENTS.md](../AGENTS.md).

## Upstream Home Assistant references (from `reference-repos/`)
- Add-on development standards and tutorial: [`reference-repos/developers.home-assistant/docs/add-ons.md`](../reference-repos/developers.home-assistant/docs/add-ons.md) and the deep-dive sections under `add-ons/` (configuration, communication, testing, publishing).
- Supervisor architecture and developer flow: [`reference-repos/developers.home-assistant/docs/supervisor.md`](../reference-repos/developers.home-assistant/docs/supervisor.md) plus [`supervisor/development.md`](../reference-repos/developers.home-assistant/docs/supervisor/development.md) for host/service expectations.
- Dev environment expectations: [`reference-repos/developers.home-assistant/docs/development_environment.mdx`](../reference-repos/developers.home-assistant/docs/development_environment.mdx) for upstream tooling, devcontainer defaults, and lint/test hooks.
- Operating System internals and kernel notes: [`reference-repos/operating-system/Documentation/README.md`](../reference-repos/operating-system/Documentation/README.md) (links through to kernel and build docs).
- Home Assistant OS install steps and recovery: [`reference-repos/home-assistant.io/source/installation/raspberrypi.markdown`](../reference-repos/home-assistant.io/source/installation/raspberrypi.markdown) and [`troubleshooting.markdown`](../reference-repos/home-assistant.io/source/installation/troubleshooting.markdown).
- Official add-on base images and metadata conventions: [`reference-repos/addons/README.md`](../reference-repos/addons/README.md) plus the individual add-on `README.md` files for examples.
- Frontend source and ingress/UI expectations: [`reference-repos/frontend/README.md`](../reference-repos/frontend/README.md) and the linked frontend developer guide for build/debug instructions.
