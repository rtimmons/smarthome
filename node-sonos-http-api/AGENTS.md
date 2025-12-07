# Agents — Node Sonos HTTP API

- Read the repo-wide guidance first: `../AGENTS.md`.
- Port: 5005; sonos-api depends on this service.
- Setup: `just setup` runs the multicast pre-setup hook and clones upstream `jishi/node-sonos-http-api` if missing, then installs via repo nvm.
- Tests: none defined here.
- Builds/deploys: `just ha-addon` / `just deploy` to build and push the patched add-on; runtime patches live in `patches/` and are applied during container builds.
