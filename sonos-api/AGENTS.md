# Agents — Sonos API

- Start with the root guide: `../AGENTS.md`.
- Port: 5006. Backend mode defaults to `node`; `shadow` serves/writes through node while comparing Home Assistant reads, and `home_assistant` uses only the allowlisted native media-player entities.
- Setup/tests: `just setup` then `just test` here use the repo nvm wrapper and run the TypeScript build.
- Builds/deploys: `just ha-addon` / `just deploy` from this directory or the repo root.
- Never mirror writes in shadow mode, expose the Supervisor token, accept arbitrary entity IDs, or infer topology while Home Assistant state is stale/unknown.
- Keep node available for rollback until the observation and explicit retirement gates in `docs/plan-replace-sonos-node-api.md` pass.
