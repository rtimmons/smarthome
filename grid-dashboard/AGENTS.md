# Agents — Grid Dashboard

- Read the repo-wide guide first: `../AGENTS.md`.
- Port: 3000 (served via `just dev` from repo root).
- Setup/tests: `just setup` then `just test` from this directory uses repo nvm (`talos/just/nvm.just`); app code lives in `ExpressServer/`.
- Local UI dev: `cd ExpressServer && npm run dev` (after `just setup`).
- Builds/deploys: `just ha-addon` / `just deploy` here or from the repo root to build/deploy the Home Assistant add-on.
