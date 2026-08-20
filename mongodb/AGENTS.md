# Agents — MongoDB

- See repo guidance: `../AGENTS.md`.
- Port: 27017 (local dev).
- Setup/start: `just setup` installs MongoDB via Homebrew and prepares `data/`; `just start` runs `mongod` with the local data dir.
- Tests: none defined.
- Container/deploy: `just ha-addon` / `just deploy` use `talos` to build and ship the add-on.
- The live data directory has MongoDB feature compatibility version 8.2. Keep the exact image pin on the 8.2 line; MongoDB Community Edition cannot safely start that data with an 8.0 binary.
