# Apply the Home Assistant Local Add-on Kit

This kit is symlinked into a separate Node.js app repository. Follow the
[manual installation and operational model](README.md) to copy and adapt its
templates there; do not change smarthome or copy app source into it.

## Constraints

- Use a Supervisor-managed local add-on, never unmanaged Docker on Home Assistant OS.
- Keep permissions minimal. `full_access`, `privileged`, `host_network`, Docker socket,
  USB, GPIO, and audio require demonstrated need and explicit user acceptance.
- Store mutable production data in `/data`, never the source tree.
- Preserve an existing app `Justfile`; merge the template recipes.
- Stop and ask before adding private npm registry credentials or build-secret handling.
- Prefer a separate Supervisor-managed database add-on for MongoDB/PostgreSQL;
  SQLite belongs under `/data`.

## Implementation and acceptance

1. Inspect `package.json`, build/start scripts, HTTP port, and storage needs.
2. Copy the templates following the README. Replace every `TODO_*`; use a lowercase
   snake-case slug (`local_<slug>` is the add-on ID). Enable ingress for web UIs
   unless API-only, remove unused options, and adapt the Dockerfile to the app.
3. Bind to `0.0.0.0`, read `PORT`, and use `DATA_DIR` defaulting to `/data`.
   Make `ha-addon/run.sh` and `scripts/deploy-ha-addon.sh` executable.
4. Run app tests and `just package-ha-addon` (or the deploy script's `--package-only`);
   inspect the package before deploying with `just deploy-ha-addon`.

Keep the deploy script a thin Talos wrapper. Deployment replaces `/addons/<slug>`
source, preserves Supervisor-managed data, and verifies the add-on started.
Report changed files, slug/ID, deploy command, runtime assumptions, and whether
only packaging or deployment was completed.
