# Smarthome

Home Assistant add-ons, generated household configuration and infrastructure runbooks.

## Getting started

Read [AGENTS.md](AGENTS.md) for contributor rules, then use
[development setup](docs/setup/dev-setup.md). Durable controller inputs live outside
Git; [disposable checkout recovery](docs/setup/disposable-checkout.md) explains how
to prepare a fresh checkout.

The printer application is a separate private repository cloned at `printer/`.
Clone it before setup or testing using the [development setup](docs/setup/dev-setup.md#private-printer-checkout).
The parent commands operate on both working trees; coordinated changes follow
the [paired repository rules](AGENTS.md#paired-printer-repository).

- `just setup` installs the pinned toolchain.
- `just dev` runs local services; see [local development](docs/development/local-development.md).
- `just test` runs repository checks, add-on tests and container checks.
- `just --list` lists commands; `just addons` discovers add-ons from their manifests.
- `just deploy [addon]` deploys add-ons and Home Assistant configuration; follow the [contributor rules](AGENTS.md) for credentials and validation.

## Documentation

- [Smarthome field guide](https://wiki.home.rytim.com/) — Household instructions and generated configuration reference
- [Documentation index](docs/README.md) — Development guides, operations and plans
- [Wiki operations](docs/operations/wiki.md) — Authoring, publication and LAN recovery addresses
- [Home Assistant configuration](new-hass-configs/README.md) — Generator and configuration workflow
