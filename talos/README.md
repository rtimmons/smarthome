# Talos CLI

Talos is the isolated build/deployment/dev toolchain for this repository. It owns all
Python-based orchestration, add-on packaging, and shared Justfile helpers.

## Install / Build

```bash
cd talos
./build.sh
export PATH="$PWD/build/bin:$PATH"  # optional convenience for direct talos usage
```

The build uses its own virtualenv under `talos/build/venv` so it never conflicts with
add-on runtimes.

## Commands

- `talos addon build <name>` — render an add-on payload to `build/home-assistant-addon/`
- `talos addon deploy <name>` — scp + install the add-on on Home Assistant
- `talos addon test <name>` — run add-on-defined test hooks
- `talos addons run <recipe> [addons…]` — run a Just recipe for each add-on (used by `just ha-addon`, `just deploy`, `just test`)
- `talos dev` — start all add-ons locally with orchestration/log mux
- `talos ports list|kill` — inspect or free occupied add-on ports
- `talos hook run <addon> <hook>` — execute local-dev hooks (e.g., `pre_setup`)

## Development Notes

- Runtime versions come from repo-root `.nvmrc` and `.python-version`.
- Templates live in `talos/src/talos/templates`.
- Justfile helpers live in `talos/just/`.
- Tests for Talos live in `talos/tests/` (run with `pytest` from the Talos venv).
