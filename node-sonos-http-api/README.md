# Node Sonos HTTP API Home Assistant Add-on

This is a Home Assistant add-on that wraps the [node-sonos-http-api](https://github.com/jishi/node-sonos-http-api) project, providing a simple HTTP API for controlling Sonos speakers.

## Building

```bash
just ha-addon
```

This will create the add-on package in `build/home-assistant-addon/node_sonos_http_api/` and a tarball at `build/home-assistant-addon/node_sonos_http_api.tar.gz`.

## Deploying

```bash
just deploy
```

Or with custom Home Assistant host:

```bash
HA_HOST=homeassistant.local just deploy
```

## Configuration

The add-on exposes the following configuration options:

- `sonos_discovery_timeout`: Timeout in seconds for discovering Sonos speakers (default: 5)

### Presets and settings

- Put your `presets.json` in Home Assistant at `/config/node-sonos-http-api/presets.json`. The add-on will
  automatically symlink it into the app directory on start.
- You can also use individual preset files under `/config/node-sonos-http-api/presets/` (one JSON file per preset,
  named `<preset-name>.json`).
- If no file is provided, a blank `presets.json` is created at `/data/node-sonos-http-api/presets.json`
  and used so presets persist across restarts. If nothing exists, the bundled `presets.example.json` is copied
  into `/data/node-sonos-http-api/presets.json` on first start.
- `settings.json` is also picked up from `/config/node-sonos-http-api/settings.json` or `/data/node-sonos-http-api/settings.json`
  if you need to override upstream defaults. An empty file is created under `/data/node-sonos-http-api/settings.json`
  if none is provided to suppress upstream warnings.
- Default TV presets from the old Ansible setup are checked in under `node-sonos-http-api/presets/` and
  aggregated in `node-sonos-http-api/presets.example.json` for convenience—copy one of these into `/config/node-sonos-http-api/`.

### Sonos discovery health check

macOS often blocks the SSDP probes that Sonos discovery relies on whenever VPNs, Private Wi-Fi Address, or Limit IP Address Tracking are enabled. Use the bundled helper to confirm multicast reachability before starting the add-on:

```bash
node node-sonos-http-api/tools/check_sonos_multicast.js
```

`just setup` and `just dev` call this script automatically and will refuse to start the HTTP API if SSDP packets cannot leave your laptop. If it fails, disconnect VPN/ZeroTrust clients and disable **Private Wi-Fi Address** / **Limit IP Address Tracking** for your Wi-Fi network, then rerun the check.

## Architecture

This add-on:
- Runs on port 5005
- Uses host networking to discover Sonos devices on your network
- Clones a reviewed, immutable node-sonos-http-api commit from GitHub
- Is accessible to other add-ons via `http://node-sonos-http-api:5005`
- Installs a repository-owned production lockfile with `npm ci`
- Applies compatibility and reliability patches before installing dependencies
- Runs a post-install import scan so a removed or missing runtime dependency fails the image build instead of crashing after deployment

Run `just test` after dependency or patch changes. It refreshes the prepared upstream checkout with the current overlay and patches, then runs the same runtime-import scan used during image installation.

## Error Handling

This add-on applies build-time patches to the upstream node-sonos-http-api for security and to prevent crashes from transient SOAP errors:

### Patches Applied

1. **`patches/dependency-security.patch`**: Removes abandoned vulnerable clients
   - Replaces `request`/`request-promise` callers with Node's built-in `fetch`
   - Replaces the abandoned Pandora client with a local HTTPS implementation
   - Migrates Polly to AWS SDK v3 and updates JSON/audio parsers

2. **`patches/group-error-handling.patch`**: Adds retry logic to join operations
   - Retries failed join attempts up to 3 times with 1-second delays
   - Gracefully handles HTTP 500 errors from Sonos devices
   - Logs failures without crashing the service

3. **`patches/server-crash-prevention.patch`**: Adds global error handlers
   - Catches uncaught exceptions to prevent process crashes
   - Logs errors with stack traces for debugging

These patches are automatically applied during the Docker build process and help maintain service stability when Sonos devices are busy or network conditions are poor.

## API Documentation

For full API documentation, see: https://github.com/jishi/node-sonos-http-api
