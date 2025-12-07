# Agents — Printer

- Start with the repo guide: `../AGENTS.md`.
- Port: 8099 for local dev.
- Setup: `just setup` installs system deps (via Homebrew) and creates `.venv`.
- Run/tests: `just start` for the dev server; `just test` runs ruff/mypy/pytest. Visual diff helpers live under the `visual-diff*` recipes.
- Container builds/deploys: `just build` for a local image, `just ha-addon` / `just deploy` to build and ship the Home Assistant add-on.
