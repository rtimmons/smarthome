# Sonos routing guide

## Request chain

A Dashboard volume action follows this path:

```text
browser /sonos/Bedroom/groupVolume/+2
  -> Grid Dashboard server at local-grid-dashboard:3000
  -> sonos-api at local-sonos-api:5006
  -> selected backend
       node/shadow: local-node-sonos-http-api:5005
       home_assistant: Supervisor Core REST/WebSocket APIs
```

The Grid server also maps browser-facing `/sonos-intents/*` requests to the internal `/intents/sonos/*` compatibility routes. Artwork is handled as bounded binary data through both server layers; ordinary API responses use the text/JSON proxy.

## Backend modes

- `node` is the default for upgraded installations. Routes retain their existing node behavior.
- `shadow` still serves every response and executes every command through node. Home Assistant state is read asynchronously for structured comparison only; there is exactly one node write and zero Home Assistant writes per action.
- `home_assistant` serves canonical state and executes allowlisted `media_player` services through Home Assistant. Its health is ready only after authentication and a complete, live snapshot.

Select the mode with the `sonos-api` add-on's `backend_mode` option. `sonos_base_url` is relevant only to `node` and `shadow`.

## Compatibility routes

The active route families are:

- `GET /sonos/zones`, `/sonos/:room/state`, and `/sonos/:room/artwork`
- `GET /sonos/:room/{play,pause,playpause,next}`
- `GET /sonos/:room/favorite/:name`
- `GET /sonos/:room/join/:target` and `/sonos/:room/leave`
- `GET /sonos/:room/groupVolume/:value`, `/sonos/:room/volume/:value`, and `/same/:room`
- `GET /sonos/:room/preset/:name`
- `POST /intents/sonos/group-all` and `GET /intents/sonos/status`
- retained policies `GET /up` and `GET /down`

The legacy root routes `/pause`, `/play`, `/tv`, `/07`, and `/quiet` have no live repository caller. In `home_assistant` mode, both Sonos API and Grid Dashboard return the frozen `410` deprecated-route response with zero node or HA writes. In `node` and `shadow`, Grid and Sonos API preserve exact pass-through behavior for configuration rollback until retirement. These roots are not aliases for the room-scoped routes.

All room, favorite, and preset parameters pass through repository allowlists. There is no generic Home Assistant service proxy.

## State and failures

Home Assistant mode exposes these freshness headers through both layers:

- `X-Sonos-Response-Source`
- `X-Sonos-Response-Stale`
- `X-Sonos-Observed-At`
- `X-Sonos-Age-Ms`

A transport loss immediately marks the last confirmed state stale. At the frozen boundary it becomes unknown; topology reads and mutations then fail closed instead of fabricating membership. Operation status supplies pending/terminal presentation, but `/zones` remains the only source of membership truth.

## Checks from the Home Assistant host

Use the repository-local SSH identity required by the root agent guide:

```bash
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local
curl http://local-sonos-api:5006/health
curl http://local-sonos-api:5006/sonos/zones
curl http://local-grid-dashboard:3000/sonos/zones
```

In `node` or `shadow` mode, `curl http://local-node-sonos-http-api:5005/zones` is also a useful comparison. In `home_assistant` mode, direct node traffic is unexpected and should be treated as rollout evidence to investigate.

## Troubleshooting

- A `503` health response in Home Assistant mode means the authenticated snapshot is not live/complete or a configured room/source is unavailable. Check the sanitized health diagnostics and add-on logs.
- Deployment and backup readiness probe `/sonos/zones`, not `/health`, so an explicitly reported unavailable room does not make an otherwise operational add-on fail deployment or block Grid Dashboard. Invalid or unavailable topology still fails that probe.
- A stale response indicates a lost WebSocket liveness signal. Wait for authenticated reconnect and resnapshot; do not retry topology writes against unknown state.
- A `502` from the Grid proxy means its request to `sonos-api` failed or artwork violated the binary safety contract.
- Add-on hostnames use the `local-` prefix: `local-grid-dashboard`, `local-sonos-api`, and, while retained, `local-node-sonos-http-api`.
- Roll back with the exact Supervisor options POST and separate Sonos API restart in [the migration plan](../plan-replace-sonos-node-api.md#rollback). A passing rehearsal requires a new node-backend startup-log marker, parsed ready/node health, direct-node/API/Grid topology agreement, one room-state route, one low-risk playback action, full household-state restoration, and completion within 10 minutes. Record the required timestamps and restart evidence in [the migration validation record](ha-migration-validation.md).

## Live restoration checkpoint

Before and after any live action, capture the private current state. Unless a newer intentional household change was recorded before the test, completion requires exactly one Bathroom-coordinated group containing Bathroom, Closet, Bedroom, Move, Kitchen, Living Room, Guest Bathroom, and Office; volume 20 and mute false in every room; playback `playing`; station `735 - Steve Aoki's Remix Radio` / `CH 735 - Steve Aoki's Remix Radio`; agreement across HA, node while retained, Sonos API, Grid, and the Sonos app; and zero pending operations. Track metadata may advance naturally without failing restoration.
