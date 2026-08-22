# Agents Guide

Guidance for humans and agents working in this repository.

## Ground rules
- Default to `just` recipes and the provided env wrappers (`.venv`, `nvm`) instead of ad-hoc commands.
- You start in a sandbox; ask before taking the git lock (`git add`, etc.).
- Runtimes are pinned by `.nvmrc` (Node) and `.python-version` (Python); use the self-contained nvm/pyenv installed by `just setup`.
- “Prepare to commit” means: stage your changes (with permission), run `just test`, and drop the proposed commit message in `./msg` without staging that file.

## Root workflows (Justfile-aligned)
- Bootstrap everything: `just setup` (installs pinned Node/Python, builds `talos` if needed).
- Create the ignored, repository-local Home Assistant SSH key with `just ha-ssh-key-create`. A human installs it on Home Assistant once with `just ha-ssh-key-copy`; agents must not run the copy recipe.
- Run the whole stack locally: `just dev`; free conflicting ports with `just kill`. Services map to localhost ports: grid-dashboard 3000, sonos-api 5006, node-sonos-http-api 5005, printer 8099, snapshot-service 4010, tinyurl-service 4100.
- Build add-ons: `just ha-addon [addon]`; list discovered add-ons with `just addons` (discovery is by `*/addon.yaml`).
- Deploy: `just deploy [addon]` builds via `talos` and deploys, then rolls out `new-hass-configs`. Use `just printer-image` to preflight the printer container build.
- Tests: `just test [addon]` runs add-on tests plus container build checks.
- `talos` lives at `talos/build/bin/talos`; build it with `./talos/build.sh` if a recipe complains.

## Reference repos
- Upstream Home Assistant references live under `reference-repos/` as submodules; see `reference-repos/AGENTS.md` for purposes, doc entry points, and refresh commands.

## Home Assistant configuration
- Everything lives under `new-hass-configs`. Common commands: `just fetch`, `just check`, `just deploy`, and `./iterate.sh` for before/after scene inventories. From the repo root, use the repository-owned `just ha-state <entity_id>`, `just ha-call <domain.service> <entity_id>`, and `just ha-inventory` commands to inspect or operate the live system; they do not depend on the Python-based `hass-cli` package.
- **SSH access**: From the repository root, use `ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local` to access Home Assistant directly. Always select this repository-local identity explicitly; do not use 1Password or another SSH-agent identity for agent access. The remote `ha` command manages Core/Supervisor lifecycle, logs, backups, and host services; it does not expose entity state or service-call commands, so use the repository API client for those. The entity registry is at `/config/.storage/core.entity_registry` for advanced device discovery.
- **SSH key setup and failures**: The private key is local-only under the Git-ignored `/.ssh/` directory. If the keypair is missing, run `just ha-ssh-key-create`, then stop and ask Ryan to run the human-only `just ha-ssh-key-copy`. If the dedicated key exists but authentication fails, stop the Home Assistant workflow immediately and ask Ryan to rerun `just ha-ssh-key-copy`; do not retry repeatedly or fall back to 1Password, another host, an IP address, a browser session, an API token, or alternate credentials.
- **Hostname failures are not authentication failures**: The Codex sandbox can fail to resolve `homeassistant.local`. Retry the same hostname-based command with the repository-local identity once outside the sandbox; do not substitute an IP address. If it still cannot resolve, stop and report the mDNS/network failure rather than changing credentials.

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
- Scenes with paired RGBW entities must keep base + `_white` lights in sync; the generator handles it via `expandLightsWithPairs()` in `new-hass-configs/config-generator/src/scene-generation.ts`.
- Operational lighting must use `script.fast_scene_<scene_id>`, never native `scene.turn_on`; restart-mode wrappers and dispatcher make the newest request authoritative while preserving health filtering, bounded Z-Wave submissions, error isolation, skipped-target reporting, and a restart-cancellable mismatch-only convergence pass. Non-Z-Wave and Z-Wave branches start together. Compatible dimmer hardware uses CC38 `zwave_js.set_value` with `wait_for_result: false` and a zero-second transition. Multicast is forbidden unless the device has a live-verified `fastSceneMulticastGroup`; the current allowlist is four Minoston MP22ZD plugs and falls back to unicast when fewer than two are eligible. See `docs/operations/zwave-scene-ops.md`.
- `new-hass-configs/scripts.yaml` is a generated, ignored deployment artifact. Edit generator sources, review `new-hass-configs/generated/scripts.yaml`, and let `just generate`, `just check`, or deployment prechecks rebuild it; do not commit or reconcile the root file.
- Outlets powering smart lights must set both `includeInAllOff: false` and `allowSceneTurnOff: false`; generated scenes must control the bulb entity and never cut its power.
- Z-Wave nodes 2 (`living_palm`) and 16 (`outdoor_cafe`) were intentionally removed on 2026-08-21. Their desired entity IDs remain in `devices.ts` with `inventoryStatus: "temporarily_removed"`; preserve that marker while they are absent, then clear it only after re-inclusion and restoration of the same entity IDs. If failed-node removal is accepted but its completion event times out, do not submit it again: restart only Z-Wave JS once, then verify the fresh controller node list and Home Assistant registries.
- Z-Wave node 23 (`guestbathroom_overhead`) changes its load but repeatedly times out during command acknowledgement, including after a successful route rebuild on 2026-08-21. Keep it last-priority, isolated, and non-waiting in scenes; if the timeout traffic persists, exclude/re-include or replace that device rather than restoring queued scene waits.

## Docs map
- Start with `docs/README.md` for the index; `docs/setup/dev-setup.md` and `docs/development/local-development.md` cover local workflows.
- Container runtime details: `docs/addon-development/container-runtime.md`.
- UniFi access and Apple TV/Bonjour troubleshooting: `docs/operations/unifi-ssh-access.md`, `docs/operations/unifi-apple-tv-remote.md`.
- Sonos architecture/routing: `docs/sonos/overview.md`, `docs/sonos/routing-guide.md`.
- Versioning and runtimes: `docs/setup/version-management.md`.
- Home Assistant ingress history/fixes: `docs/addon-development/ingress-fixes.md`.
