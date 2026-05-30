# Agent Instructions: Make a Node.js App Deployable as a Home Assistant Local Add-on

You are working in a separate Node.js app repository that contains this directory as a symlink. Your task is to add a small Home Assistant local add-on wrapper and a simple SSH deploy flow.

## Non-Negotiable Constraints

- Do not deploy this app as an unmanaged Docker container on Home Assistant OS.
- Do not require changes in `/Users/rtimmons/Projects/smarthome`.
- Do not copy app source into the smarthome repo.
- Keep Home Assistant add-on permissions minimal.
- Do not enable `full_access`, `privileged`, `host_network`, Docker socket access, USB, GPIO, or audio unless the app demonstrably requires it and the user explicitly accepts that risk.
- Mutable production data must live in `/data` inside the add-on container.

## Target Outcome

The app repo should gain:

- `ha-addon/config.yaml`
- `ha-addon/Dockerfile`
- `ha-addon/run.sh`
- `ha-addon/package-excludes.txt`
- `scripts/deploy-ha-addon.sh`, a thin wrapper around Talos
- optional `Justfile` targets for packaging, deployment, logs, and status

After implementation, the user should be able to run:

```sh
just deploy-ha-addon
```

or:

```sh
./scripts/deploy-ha-addon.sh
```

The deployment should call Talos:

```sh
/Users/rtimmons/Projects/smarthome/talos/build/bin/talos addon deploy-external --app-dir . --addon-dir ha-addon
```

Talos packages the current repo, uploads it to `root@homeassistant.local`, installs/rebuilds the local add-on, starts it, and verifies Supervisor reports it as started.

## Implementation Steps

1. Inspect the app:
   - read `package.json`
   - identify the start command
   - identify whether there is a build step
   - identify the HTTP port
   - identify storage needs

2. Choose add-on metadata:
   - slug: lowercase snake case, for example `my_node_app`
   - add-on ID will be `local_<slug>`
   - default port: use the app's existing port or `3000`
   - ingress: enable for web UI apps unless the app is API-only

3. Copy templates from this kit into the app repo:
   - copy `templates/ha-addon/*` to `ha-addon/`
   - copy `templates/scripts/deploy-ha-addon.sh` to `scripts/deploy-ha-addon.sh`
   - copy `templates/Justfile` to `Justfile` if the repo does not already have one
   - if a `Justfile` exists, merge the targets instead of replacing it

4. Edit copied files:
   - replace all `TODO_*` placeholders
   - set `ingress_port`, `ports`, `ports_description`, and `PORT`
   - set `panel_title`, `panel_icon`, and description
   - remove unused options from `config.yaml`
   - adapt `Dockerfile` if the app uses a nonstandard build/start layout
   - set `ha_addon_slug` in `Justfile`, if using the template
   - leave `scripts/deploy-ha-addon.sh` as a Talos wrapper unless the Talos path differs

5. Make the deploy script executable:

```sh
chmod +x scripts/deploy-ha-addon.sh
```

6. Update the app for add-on runtime expectations if needed:
   - bind HTTP server to `0.0.0.0`
   - read port from `process.env.PORT`
   - read filesystem data location from `process.env.DATA_DIR || "/data"`
   - avoid writing to the source tree at runtime

7. Verify locally where possible:
   - run the app's tests
   - run `just package-ha-addon` or `./scripts/deploy-ha-addon.sh --package-only`
   - inspect the generated package contents if needed

8. Deploy only after the wrapper is coherent:

```sh
just deploy-ha-addon
```

## Template Notes

- Talos intentionally removes and replaces `/addons/<slug>` source files. It does not remove Supervisor-managed add-on data.
- The Dockerfile installs dependencies inside the Home Assistant add-on build.
- For private npm registries or build secrets, stop and ask the user before adding secret handling.
- For MongoDB/PostgreSQL, prefer a separate Supervisor-managed database add-on and configure the app with an option/env var. For SQLite, use `/data/<name>.sqlite`.

## Final Response Requirements

When done, report:

- files added or changed
- chosen add-on slug and add-on ID
- deploy command
- any assumptions about port, ingress, storage, or build scripts
- whether deployment was run or only packaged
