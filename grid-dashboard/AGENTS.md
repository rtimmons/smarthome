# Grid Dashboard Add-on

Read [repository guidance](../AGENTS.md) and [add-on development references](../docs/addon-development/README.md).

- App code is in `ExpressServer/`; configuration belongs in [`addon.yaml`](addon.yaml).
- From this directory, use `just setup`, `just dev`, and `just test` (tests and TypeScript checks).
- Use root `just ha-addon grid-dashboard`, `just deploy grid-dashboard`, and `just test grid-dashboard` for packaging, deployment, and container checks.

## Lighting Scene Contract

- Dashboard lighting routes map `/scenes/scene_<room>_<preset>` to `script.fast_scene_<room>_<preset>`; never call native `scene.turn_on`.
- Preserve the one-second identical-request gate in `ExpressServer/src/server/hass.ts`, the delayed/cancelled single-versus-double press behavior, and explicit `lightSceneRooms` mappings.
- The authenticated Core API boundary starts the wrapper with `script.turn_on`; generated and manual Home Assistant automations instead call the fast script directly so their `mode: single` execution stays blocking.
- The standalone `HASS_WEBHOOK_BASE` fallback waits up to 60 seconds because its webhook automation blocks until the queued fast-scene dispatcher completes; do not restore the shared HTTP client's 10-second default for this path.
- Run `just test` after lighting-route changes. The suite verifies request coalescing/failure release, route validation, every dashboard room's generated scripts, and single-versus-double press cancellation.
