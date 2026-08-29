# Sonos architecture overview

The Grid Dashboard uses `sonos-api` as a stable compatibility and orchestration layer. During the staged migration it supports three modes:

| Mode | Reads | Writes | Purpose |
| --- | --- | --- | --- |
| `node` | node-sonos-http-api | node-sonos-http-api | Safe default and rollback |
| `shadow` | Node response is served; Home Assistant is compared asynchronously | node-sonos-http-api only | Read-parity observation without duplicate commands |
| `home_assistant` | Home Assistant Sonos entities | Home Assistant media-player services | Native target architecture |

## Target request path

```text
Grid Dashboard browser
        |
        v
Grid Dashboard server (port 3000 / ingress)
        |
        v
sonos-api (port 5006)
        |
        v
Home Assistant Core REST + WebSocket APIs
        |
        v
Home Assistant Sonos integration
        |
        v
Sonos speakers
```

The browser never receives a Home Assistant bearer token or signed artwork URL. `sonos-api` loads an initial allowlisted entity snapshot, follows `state_changed` events, canonicalizes coordinator-first groups, and proxies only approved raster artwork. The Grid server forwards the compatibility response and freshness headers.

Source names are not interchangeable across backends. SiriusXM/radio, Apple
Music, TV/SPDIF, line-in, and other favorites have different Home Assistant
inputs and metadata/URI shapes; the compatibility rules and test obligations
are frozen in [the source compatibility contract](source-compatibility.md).

Topology writes are serialized and complete only after authoritative Home Assistant state matches the request or a bounded deadline is reached. Playback and volume calls remain outside that topology queue. Unknown topology is a `503`, never an invented empty or singleton group.

## Room and policy ownership

The room-to-entity map, configured favorites, and TV presets are repository-owned allowlists under `sonos-api/src/server/`. `media_player.maker_room` and dynamically discovered entities are intentionally excluded.

The retained root policies are `/up`, `/down`, and `/same/:room`. The unused legacy root routes `/pause`, `/play`, `/tv`, `/07`, and `/quiet` return the frozen `410` deprecated-route response only in `home_assistant` mode. They remain exact pass-throughs in `node` and `shadow` so configuration rollback retains baseline behavior until retirement. Room-scoped playback, favorite, volume, and preset routes remain available below `/sonos/` in every mode.

## Staged dependency and rollback

`node-sonos-http-api` remains installed and is listed as a temporary add-on dependency while `node` or `shadow` mode can be selected. It continues to expose port 5005 for baseline and rollback validation. Do not stop, uninstall, or remove it from the repository until the shadow, pilot, whole-house, stopped-node, backup, and explicit-approval gates in [the migration plan](../plan-replace-sonos-node-api.md) have passed.

Every live test must restore the frozen household state before its stage can pass: one Bathroom-coordinated group containing all eight configured rooms, volume 20 and mute false on every member, playing `CH 735 - Steve Aoki's Remix Radio`. Home Assistant, direct node while retained, Sonos API, Grid Dashboard, and the Sonos app must agree, with no pending operation. See the validation record for the complete checkpoint.

## Development and validation

Use the repository workflows:

```bash
just setup
just test sonos-api
just test grid-dashboard
just test
```

For local Home Assistant mode, supply non-committed `HOME_ASSISTANT_REST_URL`, `HOME_ASSISTANT_WEBSOCKET_URL`, and `HOME_ASSISTANT_TOKEN` values. Supervisor provides `SUPERVISOR_TOKEN` automatically in the deployed add-on.

Live evidence, rollback artifacts, operational deadlines, and rollout status are recorded in [Home Assistant Sonos migration validation](ha-migration-validation.md).
