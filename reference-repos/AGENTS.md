# Reference repos

Upstream Home Assistant repos tracked here as read-only submodules for quick reference.

## Working with them
- Re-init after a fresh clone or if you `rm -rf reference-repos/*`: `git submodule update --init --recursive reference-repos`
- Refresh to the latest default branch (branches pinned in `.gitmodules`): `git submodule update --remote reference-repos/<name>`
- Keep changes out of tree; these are for reading and cross-referencing only.

## Repo quick facts
- `reference-repos/developers.home-assistant` — Source for the developer docs site (developers.home-assistant.io). Docs entry: `README.md` for local tooling; content lives under `docs/` and `blog/` (Docusaurus). Add-on development entry point: `docs/add-ons.md` (tutorial, config, comms, testing, publishing).
- `reference-repos/home-assistant.io` — Source for the public website and user docs (Jekyll). Docs entry: `README.md`; documentation lives under `source/` (notably `_docs/` and `_integrations/`).
- `reference-repos/operating-system` — Home Assistant Operating System Buildroot tree and tooling. Docs entry: `Documentation/README.md` (plus the top-level `README.md` overview).
- `reference-repos/supervisor` — Home Assistant Supervisor runtime and host management. Docs entry: `README.md`, repo `AGENTS.md`, and developer guide at https://developers.home-assistant.io/docs/supervisor/development.
