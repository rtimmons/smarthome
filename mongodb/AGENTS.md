# Agents — MongoDB

- See repo guidance: `../AGENTS.md`.
- Port: 27017 (local dev).
- Setup/start: `just setup` installs MongoDB via Homebrew and prepares `data/`; `just start` runs `mongod` with the local data dir.
- Tests: none defined.
- Container/deploy: `just ha-addon` / `just deploy` use `talos` to build and ship the add-on.
