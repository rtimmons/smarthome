# Agents — TinyURL Service

- Start with `../AGENTS.md` for repo-wide expectations.
- Port: 4100 (requires MongoDB at `mongodb://localhost:27017/tinyurl` in dev).
- Setup/dev: `just setup` to install deps, `just dev` for local server; `just test`, `just lint`, `just fmt`, and `just typecheck` wrap the npm scripts (uses repo nvm).
- Builds/deploys: `just ha-addon` / `just deploy` for the Home Assistant add-on; `just container-run` builds and runs the container locally for debugging.
