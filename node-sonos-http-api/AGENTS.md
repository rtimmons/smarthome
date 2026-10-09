# Agents — Node Sonos HTTP API

- Read the repo-wide guidance first: `../AGENTS.md`.
- Disabled pending retirement: retain code and installed data for rollback. `disabled: true` keeps deployment and local development from starting this service. Do not re-enable without user direction.
- Former port: 5005; the live sonos-api uses Home Assistant.
- Setup: `just setup` runs the multicast pre-setup hook and clones upstream `jishi/node-sonos-http-api` if missing, then installs via repo nvm.
- Tests: run `just setup` once, then `just test`; it reapplies the current overlays/patches and verifies every server-side runtime import resolves from the production lock.
- Builds/deploys: `just ha-addon` / `just deploy` to build and push the patched add-on; runtime patches live in `patches/` and are applied during container builds.
- The production dependency manifest runs `overlay/tools/check-runtime-dependencies.js` after install. Keep this scanner enabled whenever dependencies or upstream patches change so undeclared imports fail during the build rather than after the live add-on is stopped.
