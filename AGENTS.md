# Agents Guide

Guidance for humans and agents working in this repository.

## Ground rules
- Default to `just` recipes and the provided env wrappers (`.venv`, `nvm`) instead of ad-hoc commands.
- You start in a sandbox; ask before taking the git lock (`git add`, etc.).
- Runtimes are pinned by `.nvmrc` (Node) and `.python-version` (Python); use the self-contained nvm/pyenv installed by `just setup`.
- “Prepare to commit” means: stage your changes (with permission), run `just test`, and drop the proposed commit message in `./msg` without staging that file.

## Root workflows (Justfile-aligned)
- Bootstrap everything: `just setup` (installs pinned Node/Python, builds `talos` if needed).
- Run the whole stack locally: `just dev`; free conflicting ports with `just kill`. Services map to localhost ports: grid-dashboard 3000, sonos-api 5006, node-sonos-http-api 5005, printer 8099, snapshot-service 4010, tinyurl-service 4100.
- Build add-ons: `just ha-addon [addon]`; list discovered add-ons with `just addons` (discovery is by `*/addon.yaml`).
- Deploy: `just deploy [addon]` builds via `talos` and deploys, then rolls out `new-hass-configs`. Use `just printer-image` to preflight the printer container build.
- Tests: `just test [addon]` runs add-on tests plus container build checks.
- `talos` lives at `talos/build/bin/talos`; build it with `./talos/build.sh` if a recipe complains.

## Reference repos
- Upstream Home Assistant references live under `reference-repos/` as submodules; see `reference-repos/AGENTS.md` for purposes, doc entry points, and refresh commands.

## Home Assistant configuration
- Everything lives under `new-hass-configs`. Common commands: `just fetch`, `just check`, `just deploy`, and `./iterate.sh` for before/after scene inventories. Access the live system with `hass-cli` when you need to inspect entities or trigger scenes.

## Add-ons at a glance
- `grid-dashboard` (port 3000) — Main dashboard UI. See `grid-dashboard/AGENTS.md`.
- `sonos-api` (port 5006) — Custom Sonos proxy. See `sonos-api/AGENTS.md`.
- `node-sonos-http-api` (port 5005) — Upstream Sonos service plus local patches. See `node-sonos-http-api/AGENTS.md`.
- `printer` (port 8099) — Label printer service. See `printer/AGENTS.md`.
- `snapshot-service` (port 4010) — Camera snapshot helper. See `snapshot-service/AGENTS.md`.
- `tinyurl-service` (port 4100) — URL shortener backed by MongoDB. See `tinyurl-service/AGENTS.md`.
- `mongodb` — MongoDB add-on; local dev uses Homebrew for the daemon. See `mongodb/AGENTS.md`.

## Operational notes
- Lifecycle hooks live in `local-dev/hooks/` per add-on and are documented in `docs/addon-development/hooks-guide.md`; `node-sonos-http-api` checks Sonos multicast reachability and `printer` validates cairo/pkg-config for label rendering.
- Sonos reliability patches are in `node-sonos-http-api/patches` and are applied during container builds; adjust those patches if you change upstream Sonos behavior.
- Scenes with paired RGBW entities must keep base + `_white` lights in sync; the generator handles it via `expandLightsWithPairs()` in `new-hass-configs/config-generator/src/generate.ts`.

## Docs map
- Start with `docs/README.md` for the index; `docs/setup/dev-setup.md` and `docs/development/local-development.md` cover local workflows.
- Container runtime details: `docs/addon-development/container-runtime.md`.
- Sonos architecture/routing: `docs/sonos/overview.md`, `docs/sonos/routing-guide.md`.
- Versioning and runtimes: `docs/setup/version-management.md`.
- Home Assistant ingress history/fixes: `docs/addon-development/ingress-fixes.md`.
