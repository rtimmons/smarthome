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

- `home_assistant` is the default. The old node service is disabled pending retirement.
- `node` is retained for explicitly requested rollback and requires re-enabling the old service. Routes retain their existing node behavior.
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
- Use [backend rollback](#backend-rollback) only when deliberately requested; preserve the captured household state and record results in [migration validation](ha-migration-validation.md).

## Live restoration checkpoint

Capture the household's current group/coordinator, source, playback, volumes and
mute values privately before any live action, and restore them afterward. Verify
agreement across HA, Sonos API, Grid and the Sonos app, with zero pending operations.
Compare direct node only when deliberately enabled for rollback. The August
eight-room/volume-20 radio checkpoint in the validation record is dated evidence,
not a reason to overwrite newer intentional household state. Track metadata may
advance naturally without failing restoration.

## Backend rollback

Use this procedure only for an explicitly requested rollback or rehearsal. The
legacy service is disabled. First verify retained package/data availability,
record its existing options, and deliberately re-enable the retained node add-on;
confirm its `/zones` responds before selecting node mode. Ordinary deployments
must keep the legacy service disabled. After uninstall, reinstall the retained
prior node package/configuration before proceeding.

Run from the repository host with the dedicated Home Assistant identity and
`homeassistant.local`; follow the root guide's missing-key, authentication and
hostname stop rules. Capture the UTC start time, current private household state,
Sonos API/Grid/node versions, options, resource stats and startup-log marker before
the POST. Do not print tokens or private response bodies.

```bash
ssh -i /Users/rtimmons/Projects/smarthome/.ssh/id_ed25519_codex_smarthome \
  -o IdentitiesOnly=yes root@homeassistant.local \
  'test -n "$SUPERVISOR_TOKEN" && curl -fsS \
    -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
    -H "Content-Type: application/json" \
    -X POST \
    -d "{\"options\":{\"backend_mode\":\"node\",\"sonos_base_url\":\"http://local-node-sonos-http-api:5005\"}}" \
    http://supervisor/addons/local_sonos_api/options | jq -e ".result == \"ok\""'
```

Only after that POST passes, restart Sonos API as a separate step:

```bash
ssh -i /Users/rtimmons/Projects/smarthome/.ssh/id_ed25519_codex_smarthome \
  -o IdentitiesOnly=yes root@homeassistant.local \
  'ha apps restart local_sonos_api'
```

Then verify, in order:

1. Supervisor app info reports `state: started`, the expected installed version, and `options.backend_mode: node`.
2. The new Sonos API startup log appears after the recorded restart start time and identifies backend `node`. Record the before/after startup marker and the established unexpected-restart evidence source; a merely unchanged Supervisor `started` state is not restart proof.
3. `/health` returns `200` with `ready: true`, `backendMode: node`, and node readiness true. Record the first ready timestamp and elapsed rollback time.
4. Direct node `/zones`, Sonos API `/sonos/zones`, Grid Dashboard `/sonos/zones`, and one room-state route agree with authoritative Home Assistant/Sonos-app topology.
5. One low-risk Dashboard playback command succeeds. Prefer idempotent Bathroom play when it is already playing; if pause/play is used, restore play immediately.
6. Restore the captured pre-test household state using the [restoration checkpoint](#live-restoration-checkpoint). Confirm no open operation or HA write remains in flight and rollback finished within 10 minutes.
7. Revert Grid Dashboard only if its compatibility contract changed; otherwise keep it on the same routes. Record the trigger, failed operation, deployed versions, option POST result, planned restart evidence, health/zones/state/action results, restoration result, and RTO duration before any additional mutation.

If the retained Sonos API no longer supports node mode, restore its matching prior package/configuration and verify health before issuing actions. Do not attempt a partial reimplementation during an outage.

Immediate rollback triggers:

- Any credential or signed-artwork token exposure.
- Any UI membership that contradicts the latest authoritative topology.
- A duplicate write or late result that lets an older request overwrite a newer one.
- Missing or incorrect coordinator behavior in a TV preset.
- An add-on crash loop or loss of both direct and ingress panel control.

Threshold rollback triggers use the [recorded operational limits](ha-migration-validation.md#frozen-operational-limits-and-rollout-policy): topology timeouts, subscription loss while Home Assistant itself is healthy, unexpected restarts, pending-deadline violations, error rate, p95 control latency, and memory growth. Reaching any threshold triggers rollback rather than an improvised live fix.

Use `docker inspect addon_local_sonos_api` fields `.RestartCount` and `.State.StartedAt` as the restart/startup identity source. During an authorized observation window, sample `/sonos/zones`, health, stats, restart identity and recent logs every 5 minutes; retain sanitized topology/state summaries privately. That request triggers comparison only when explicitly running shadow mode. Keep node disabled during HA-only observation.

Rollback acceptance criteria:

- [ ] Rollback completes within the frozen RTO using the retained versioned package and configuration.
- [ ] Node mode `/health`, `/sonos/zones`, one room-state route, and one low-risk playback command pass.
- [ ] Dashboard, Home Assistant, and the Sonos app show the same topology after rollback, with no open operation or HA write still in flight.
- [ ] Deployed versions, trigger, failure evidence, rollback duration, verification results, and any restored live state are recorded in the validation record.
