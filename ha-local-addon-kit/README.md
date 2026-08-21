# Home Assistant Local Add-on Kit for Node.js Apps

This directory is intended to be symlinked into a separate Node.js app repo, then used by an agent or human to make that app deployable to a Home Assistant OS host as a local add-on.

## Install In An App Repo

From the Node.js app repo, symlink this kit:

```sh
ln -s /Users/rtimmons/Projects/smarthome/ha-local-addon-kit ./ha-local-addon-kit
```

Then ask Codex to apply it:

```sh
codex "make this app deployable to Home Assistant by following ha-local-addon-kit/AGENTS.md"
```

The agent should copy templates out of the symlinked kit into the app repo, replace placeholders, and leave the app repo with its own deploy files. The symlink is only an instruction/template source; deployment should not depend on this smarthome repo at runtime.

## Manual Install

If you want to apply the kit without an agent:

```sh
mkdir -p ha-addon scripts
cp ha-local-addon-kit/templates/ha-addon/* ha-addon/
cp ha-local-addon-kit/templates/scripts/deploy-ha-addon.sh scripts/deploy-ha-addon.sh
chmod +x ha-addon/run.sh scripts/deploy-ha-addon.sh
```

If the app repo does not already have a `Justfile`, copy the provided one:

```sh
cp ha-local-addon-kit/templates/Justfile ./Justfile
```

If the app repo already has a `Justfile`, merge these targets instead of replacing it:

```just
package-ha-addon:
	./scripts/deploy-ha-addon.sh --package-only

deploy-ha-addon:
	./scripts/deploy-ha-addon.sh

deploy-ha-addon-verbose:
	./scripts/deploy-ha-addon.sh --verbose

ha-addon-logs:
	ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local ha addons logs local_TODO_ADDON_SLUG --lines 120

ha-addon-info:
	ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local ha addons info local_TODO_ADDON_SLUG
```

Edit the copied files and replace every `TODO_*` placeholder:

- `ha-addon/config.yaml`: add-on name, slug, description, URL, port, panel title, icon, options, and schema.
- `Justfile`: `ha_addon_slug`, if using the template.
- `ha-addon/Dockerfile`: Node version, package manager, build command, or start layout if the defaults do not fit.
- `ha-addon/run.sh`: runtime environment variables or option parsing if the app needs more config.
- `scripts/deploy-ha-addon.sh`: only edit this if `TALOS` needs a different default path.

Use a lowercase snake-case slug, for example `tinyurl_service`. Home Assistant will refer to the local add-on as `local_<slug>`.

## Why This Path

Home Assistant OS is an appliance-style installation. The low-risk way to run extra software on the HA host is to package it as a Supervisor-managed local add-on, not as an unmanaged Docker container.

This kit creates an add-on wrapper in the app repo:

- `ha-addon/config.yaml` defines the Home Assistant add-on.
- `ha-addon/Dockerfile` builds the Node app.
- `ha-addon/run.sh` starts the app inside the add-on container.
- `ha-addon/package-excludes.txt` keeps deployment packages small.
- `scripts/deploy-ha-addon.sh` is a thin wrapper around Talos external add-on deployment.
- `Justfile` provides `just deploy-ha-addon`, `just package-ha-addon`, and `just ha-addon-logs`.

## Operational Model

The deploy script calls Talos from this smarthome repo:

```sh
/Users/rtimmons/Projects/smarthome/talos/build/bin/talos addon deploy-external --app-dir . --addon-dir ha-addon
```

Talos packages the app repo into a tarball shaped like this:

```text
<slug>/
  config.yaml
  Dockerfile
  run.sh
  app/
    package.json
    package-lock.json
    src/
    ...
```

Talos uploads the tarball to `root@homeassistant.local`, extracts it under `/addons/<slug>`, then runs Home Assistant CLI commands:

```sh
ha addons reload
ha addons rebuild local_<slug>
ha addons start local_<slug>
```

Persistent data should live under `/data` inside the add-on. Home Assistant manages that add-on data separately from the deployed source files.

## Expected App Shape

The app repo should have:

- `package.json`
- `package-lock.json`, preferred
- `npm start` that binds to `0.0.0.0`
- app port controlled by `PORT`
- optional `npm run build`
- optional `npm test`

For SQLite or filesystem storage, use `DATA_DIR=/data` or a config option that points storage to `/data`.

## Usage

After the agent copies and edits the templates:

```sh
just package-ha-addon
just deploy-ha-addon
```

If this repo has no `just`, run the script directly:

```sh
./scripts/deploy-ha-addon.sh
```

The default target is:

```text
root@homeassistant.local:22
```

Override with environment variables:

```sh
HA_HOST=homeassistant.local HA_USER=root HA_PORT=22 ./scripts/deploy-ha-addon.sh
```

If Talos lives somewhere else, override `TALOS`:

```sh
TALOS=/path/to/smarthome/talos/build/bin/talos ./scripts/deploy-ha-addon.sh
```

Useful commands after install:

```sh
just ha-addon-info
just ha-addon-logs
```

Or directly:

```sh
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local ha addons info local_<slug>
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local ha addons logs local_<slug> --lines 120
```

To package without touching the Home Assistant host:

```sh
just package-ha-addon
```

or:

```sh
./scripts/deploy-ha-addon.sh --package-only
```

## Risk Boundaries

Do:

- keep this as a Home Assistant local add-on
- keep add-on permissions minimal
- store mutable data in `/data`
- use ingress for HA sidebar access when appropriate
- expose a host port only when direct LAN access is needed

Do not:

- run unmanaged Docker containers on HAOS
- mount `/config`, Docker socket, or host paths unless there is a specific need
- use `full_access`, `privileged`, `host_network`, USB, GPIO, or audio by default
- store production data inside the app source directory
