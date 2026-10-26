# Printer Service Add-on

Read [repository guidance](../AGENTS.md) and [add-on development references](../docs/addon-development/README.md).
Configuration and hardware permissions belong in [`addon.yaml`](addon.yaml).

From this directory:

- `just setup` installs system dependencies and prepares the pinned Python environment.
- `just start` runs the development server with reload.
- `just test` runs formatting, type checks, and tests; `just visual-diff-help` lists visual review recipes.
- `just build` builds the local container; `just container-test` checks its build and import.

Use root `just ha-addon printer` or `just deploy printer` for Home Assistant packaging or deployment.
