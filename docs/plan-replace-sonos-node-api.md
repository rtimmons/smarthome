# Replace node-sonos-http-api with Home Assistant Sonos control

> **Status:** Proposed — investigation and live proof complete; migration not started
>
> **Investigation baseline:** 2026-08-28, repository `a4b0a97`, Home Assistant Core 2026.8.3
>
> **Scope:** `sonos-api`, Grid Dashboard Sonos behavior, add-on packaging, live migration, and retirement of `node-sonos-http-api`
>
> **Primary rule:** Home Assistant state is authoritative. A submitted action may be shown as pending, but it must never replace known group membership with an inferred or intended state.

## Objective and decision

Replace the custom `node-sonos-http-api` speaker-discovery and control process with the Sonos integration already running in Home Assistant. Retain `sonos-api` as a small, server-side compatibility and orchestration layer so the Grid Dashboard keeps its stable, legacy-browser-compatible HTTP contract while implementation details move behind it.

The target is:

```text
Grid Dashboard browser
        |
        v
Grid Dashboard server
        |
        v
sonos-api compatibility/orchestration layer
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

The target is not a direct browser-to-Home-Assistant connection. `SUPERVISOR_TOKEN` remains server-side, the iOS 12 panels keep their current transport, and room-specific policy stays testable outside the browser.

Completion means that:

- All eight configured dashboard rooms use Home Assistant entities for topology, playback state, metadata, artwork, volume, and commands.
- Manual join, manual leave, leaving the active/coordinator room, leaving a standalone room, moving between groups, and join-all converge reliably and display authoritative membership.
- The current playback, favorite, TV preset, group-volume, volume-normalization, `/up`, and `/down` behavior has either demonstrated parity or an explicitly approved replacement.
- Temporary Home Assistant disconnection produces a bounded stale indication and then an unknown state; it never presents missing data as a successful leave or join.
- `sonos-api` has no direct Sonos discovery or UPnP code and no dependency on `node-sonos-http-api`.
- The live `node-sonos-http-api` add-on is stopped and removed only after a successful observation period and a tested configuration rollback.
- The repository no longer builds, tests, deploys, or documents `node-sonos-http-api` as an active add-on.

## Why this migration is worthwhile

The live comparison established that Home Assistant and `/zones` reported the same eight-room group. Home Assistant also exposed playback metadata, volume, favorites, availability, and `group_members` for every dashboard speaker. A native live test successfully unjoined Office and rejoined it to the restored eight-room group.

Home Assistant Core 2026.8.3 provides behavior that overlaps the custom intent coordinator:

- Multi-speaker joins are serialized under a topology lock and verified after each speaker to avoid topology races.
- Unjoins are coalesced, non-coordinators are detached before coordinators, and topology is verified before the service completes.
- Join and unjoin timeouts are returned as errors rather than hidden.
- Sonos topology and media changes are local-push events when the speakers can reach Home Assistant.

See the current [Home Assistant Sonos integration](https://www.home-assistant.io/integrations/sonos/), [standard media-player actions](https://www.home-assistant.io/integrations/media_player/), and the 2026.8.3 [group implementation](https://github.com/home-assistant/core/blob/2026.8.3/homeassistant/components/sonos/speaker.py#L1063-L1118).

The current node path has the opposite failure characteristic: the local group patch retries a Sonos HTTP 500 three times and then resolves successfully even when the join permanently failed. The higher-level intent loop consequently has to infer success by repeatedly polling topology. Removing that split responsibility is the main reliability benefit.

## Current production contract

### Room map

The migration must use a single allowlisted room map. Do not derive entity IDs from labels at request time and do not expose a generic Home Assistant service proxy.

| Dashboard room | Home Assistant entity |
| --- | --- |
| Bathroom | `media_player.bathroom` |
| Closet | `media_player.closet` |
| Bedroom | `media_player.bedroom` |
| Move | `media_player.move` |
| Kitchen | `media_player.kitchen` |
| Living Room | `media_player.living_room` |
| Guest Bathroom | `media_player.guest_bathroom` |
| Office | `media_player.office` |

`media_player.maker_room` exists but was unavailable during the investigation and is not a Grid Dashboard room. It must not be pulled into join-all by discovery.

Before implementation, verify this map against the live entity registry. A rename is a contract change and must update one central map plus its tests.

### Routes that must remain compatible during migration

The Grid Dashboard currently calls the following routes through its own server. The first Home Assistant release must retain their paths and response shapes closely enough that backend and frontend work can be deployed independently.

| Existing route | Required Home Assistant-backed behavior |
| --- | --- |
| `GET /sonos/zones` | Return canonical groups derived from `group_members`. Treat membership as a set; put the coordinator first and sort remaining members for a stable response. |
| `GET /sonos/:room/state` | Return the existing dashboard state shape projected from the room entity and its group coordinator. |
| `GET /sonos/:room/play` | Call `media_player.media_play`. |
| `GET /sonos/:room/pause` | Call `media_player.media_pause`. |
| `GET /sonos/:room/playpause` | Call `media_player.media_play_pause`. |
| `GET /sonos/:room/next` | Call `media_player.media_next_track`. |
| `GET /sonos/:room/favorite/:name` | Validate `name` against the entity's `source_list`, then call `media_player.select_source`. |
| `GET /sonos/:room/join/:target` | Make `room` join the current group containing `target`. Target the group's current coordinator, not merely the requested label. |
| `GET /sonos/:room/leave` | Call `media_player.unjoin` for `room`; a standalone room is an idempotent success. |
| `GET /sonos/:room/groupVolume/:value` | Preserve characterized group-volume behavior using per-member Home Assistant volume calls. |
| `GET /same/:room` | Set every member of the room's current group to that room's volume. |
| `GET /sonos/:room/preset/:name` | Apply an allowlisted, repository-owned preset using Home Assistant services. |
| `POST /sonos-intents/group-all` | Retain the compatibility endpoint, but enqueue one serialized Home Assistant join operation rather than an open-ended per-room retry loop. |
| `GET /sonos-intents/status` | Return the operation lifecycle for compatibility. Known membership still comes only from `/zones`. |
| `GET /up`, `/down`, `/pause`, `/play`, `/tv`, `/07`, `/quiet` | Characterize usage and behavior before implementation. Preserve used routes; explicitly deprecate and log unused routes before removal. |

The compatibility layer may introduce a new compact state endpoint, but the legacy routes cannot be removed until the deployed dashboard no longer calls them and the observation logs show no other callers.

### State projection rules

The compatibility projection must be deterministic and independently unit tested.

| Existing field | Home Assistant source or rule |
| --- | --- |
| `volume` | `round(volume_level * 100)` |
| `mute` | `is_volume_muted` |
| `playbackState` | `playing -> PLAYING`, `paused -> PAUSED_PLAYBACK`, other available non-playing states -> `STOPPED` |
| `currentTrack.title` | `media_title` |
| `currentTrack.artist` | `media_artist`, falling back to `media_channel` where appropriate |
| `currentTrack.album` | `media_album_name` |
| `currentTrack.stationName` | `media_channel` |
| `currentTrack.uri` | `media_content_id` |
| `elapsedTime` | `media_position`, advanced from `media_position_updated_at` only while playing |
| `currentTrack.absoluteAlbumArtUri` | A relative, ingress-safe authenticated proxy route; never expose `SUPERVISOR_TOKEN` |
| `members` | Entity IDs in `group_members`, mapped back through the allowlist |
| coordinator | The first `group_members` entry in the current HA Sonos implementation; validate it belongs to the same set |

Live testing showed that the first entry identified the coordinator while the order of the remaining members varied between entity updates. Comparisons and UI membership logic must therefore ignore non-coordinator ordering.

Home Assistant's `entity_picture` cannot simply be handed to every panel: it is a Home Assistant-relative authenticated URL. Add an artwork proxy that fetches the current picture through the Core API and streams only image content. The state response should use an ingress-relative URL such as `./sonos/<encoded-room>/artwork` so both direct port access and Home Assistant ingress work.

Fields retained only for historical node compatibility, such as an empty `nextTrack` or unused equalizer data, must have documented defaults. Do not issue extra Home Assistant service calls or entity reads for fields that no repository consumer uses.

### Freshness and availability

- The backend obtains an initial state snapshot and subscribes to Home Assistant `state_changed` events over `ws://supervisor/core/websocket`.
- The server authenticates with `SUPERVISOR_TOKEN`; the token never appears in responses, logs, artwork URLs, or browser code. Home Assistant documents this app communication path at [App communication](https://developers.home-assistant.io/docs/apps/communication/).
- A disconnected WebSocket reconnects with bounded exponential backoff and performs a fresh snapshot before marking state live again.
- The last confirmed state may be served as stale for at most 30 seconds, retaining the known checked/unchecked membership plus the existing stale indication.
- After 30 seconds without a confirmed HA observation, topology is unknown. Do not convert unknown entities into singleton zones or unchecked rooms.
- Topology mutations are rejected with `503` while the target or anchor state is unavailable or beyond the stale command threshold.
- An unavailable non-target in join-all is reported explicitly. Available rooms may still be joined once; joined rooms must immediately display their observed membership, while unavailable rooms show a concise failure rather than indefinite pending gray.

### Command and operation lifecycle

Topology commands need a small serializer, not a second Sonos topology engine:

1. Validate the room allowlist and fresh state.
2. Assign an operation ID and mark only the affected control pending.
3. Serialize topology mutations for the household.
4. Call the appropriate Home Assistant service once. A join-all uses one `media_player.join` request whose target is the selected coordinator and whose `group_members` contains the available requested rooms.
5. Wait for the service result and authoritative state observation. Do not repeatedly resubmit a join because an HTTP request timed out.
6. Complete, partially complete, or fail the operation from observed membership.
7. Clear pending presentation without changing the last confirmed checked/unchecked membership.

If a manual mutation arrives while join-all is running, mark join-all superseded and queue only the newest desired mutation. The Home Assistant call already in flight cannot be canceled safely; after it settles, apply the newer command and let the newest observed topology win. Duplicate taps for the same room and desired state must coalesce.

Playback and volume commands do not enter the topology queue. They must still validate the room and propagate Home Assistant errors rather than returning an unconditional success.

## Scope boundaries and non-goals

In scope:

- Home Assistant Core REST/WebSocket client code inside `sonos-api`.
- Canonical Sonos state projection and current route compatibility.
- Join/leave/join-all serialization and operation status.
- Playback, favorite, volume, normalization, and TV preset parity.
- Grid Dashboard changes needed to consume authoritative state cleanly.
- Shadow comparison, live rollout, rollback, and removal of the node add-on.
- Updating Sonos architecture and operational documentation.

Not in scope:

- Replacing the Grid Dashboard with a Home Assistant dashboard.
- Sending the Supervisor token to the browser.
- Implementing arbitrary Home Assistant service calls from request paths.
- Reimplementing node features unused by this repository, such as TTS, clips, music-service search, alarms, or queue browsing.
- Changing Sonos speaker firmware, network topology, room names, or Home Assistant entity IDs as part of the migration.
- Removing `sonos-api`; that can be reconsidered only after this migration is stable.

## Safety and rollback rules

1. Read the root `AGENTS.md` and the `AGENTS.md` in every add-on being changed.
2. Use repository `just` recipes and pinned runtimes. Final validation is `just test` from the repository root.
3. No implementation sub-agent may deploy or operate live speakers unless its assigned workstream explicitly includes live validation.
4. Shadow mode never mirrors writes. Node remains the only command backend in shadow mode; Home Assistant is read and compared only.
5. Do not include `media_player.maker_room`, dynamically discovered players, or arbitrary requested entity IDs in actions.
6. Capture the installed node add-on configuration and all live preset files before replacing preset behavior. Do not commit secrets or unrelated Home Assistant storage.
7. Keep the previously working node and Sonos API packages available until the HA-backed observation window completes.
8. Do not uninstall the node add-on in the same step that first enables the HA backend.
9. A failed or timed-out action must leave the UI driven by the latest confirmed topology. Never "repair" display state by inventing membership.
10. Stop live testing if the repository-local Home Assistant SSH key is missing or rejected, following the root access rules. Do not try alternate credentials.

## Parallel implementation strategy

Parallel work starts only after a small foundation commit defines shared interfaces and fixtures. Every workstream starts from that exact integration-base commit in a clean context and its own branch/worktree. Agents must not edit files owned by another workstream. If a frozen interface is insufficient, the agent reports the required contract change instead of modifying it unilaterally.

Suggested branch names use the repository prefix:

- `codex/sonos-ha-foundation`
- `codex/sonos-ha-transport`
- `codex/sonos-ha-state`
- `codex/sonos-ha-actions`
- `codex/sonos-ha-presets`
- `codex/sonos-ha-dashboard`
- `codex/sonos-ha-integration`
- `codex/sonos-ha-retirement`

### Phase 0: Characterize and freeze the contract — serial

This phase must land before parallel implementation begins.

Actions:

- [ ] Record the exact integration-base commit and verify a clean worktree.
- [ ] Read root, `sonos-api`, `grid-dashboard`, and `node-sonos-http-api` agent instructions.
- [ ] Capture the live node preset inventory from its persistent configuration and reconcile it with the three repository preset files. Record names, players, order/coordinator, volumes, URI/source, `pauseOthers`, and any sleep/play-mode fields without copying secrets.
- [ ] Exercise or inspect each existing convenience route and classify it as dashboard-used, externally used, unused, or unknown.
- [ ] Characterize node `groupVolume` for relative and absolute changes with unequal member volumes, including clamping at 0 and 100. This result becomes the parity specification; do not guess the algorithm.
- [ ] Verify every configured favorite name in `grid-dashboard/ExpressServer/src/public/js/config.js` appears in the live Home Assistant `source_list`.
- [ ] Verify the eight-room entity map and capture representative playing, paused, stopped, unavailable, single-room, and multi-room HA state fixtures.
- [ ] Add frozen backend interfaces, room mapping, normalized error shape, and fixtures in files reserved for foundation ownership.
- [ ] Add the backend-mode contract: `node`, `shadow`, and `home_assistant`. Shadow serves and writes through node while comparing HA reads; it never duplicates a write.
- [ ] Define structured comparison output and ensure it excludes tokens and complete authenticated artwork URLs.

Recommended foundation-owned files:

- `sonos-api/src/server/sonos-contract.ts`
- `sonos-api/src/server/sonos-room-map.ts`
- `sonos-api/src/server/__fixtures__/home-assistant-sonos.ts`
- `sonos-api/src/server/__fixtures__/node-sonos.ts`
- Contract-only additions to `sonos-api/src/types/sonos/index.ts`

Foundation acceptance criteria:

- [ ] All current Grid Dashboard Sonos routes appear in a route inventory test or table.
- [ ] Room labels and entity IDs are one-to-one and duplicate-free.
- [ ] Fixture tokens and entity-picture authentication values are synthetic.
- [ ] The backend interface covers reads, playback, favorites, grouping, volume, presets, and operation status without exposing a generic service-call method to route handlers.
- [ ] `just test sonos-api` passes.
- [ ] The foundation commit hash is supplied to every parallel agent.

### Parallel wave 1A: Home Assistant transport and state store

**Owned files:** new transport/state-store modules and their tests only. Do not edit `sonos.ts`, `config.ts`, manifests, dashboard files, or frozen contracts.

Deliverables:

- [ ] Implement an injectable Core REST client using the internal Supervisor API and bearer token.
- [ ] Implement initial state loading for the allowlisted entities.
- [ ] Implement WebSocket authentication, `state_changed` subscription, reconnect/backoff, resnapshot, and shutdown cleanup.
- [ ] Track `observedAt`, connection state, and stale age without mutating entity payloads.
- [ ] Provide dependency injection for clock, HTTP, WebSocket, and timers so tests use no live Home Assistant instance.
- [ ] Ensure REST and WebSocket errors are normalized and never include credentials.

Suggested files:

- `sonos-api/src/server/home-assistant-client.ts`
- `sonos-api/src/server/home-assistant-state-store.ts`
- Matching `*.spec.ts` files

Acceptance criteria:

- [ ] Authentication success, rejection, clean shutdown, reconnect, duplicate event, out-of-order event, and resnapshot paths are tested.
- [ ] An older `last_updated` event cannot replace a newer room state.
- [ ] State is marked stale on disconnect and unknown after the configured maximum age.
- [ ] No test uses network access or real tokens.
- [ ] `just test sonos-api` passes.

### Parallel wave 1B: Home Assistant state compatibility projection

**Owned files:** new projection/artwork modules and tests only. Do not edit transport, routes, manifests, dashboard files, or frozen contracts.

Deliverables:

- [ ] Project allowlisted HA entity states into canonical groups and the existing room-state response.
- [ ] Canonicalize groups by coordinator plus sorted remaining room names.
- [ ] Reject malformed groups, unknown entity IDs, duplicate room membership, and a coordinator not contained in its group.
- [ ] Implement playback-state, metadata, elapsed-time, volume, mute, and compatibility defaults.
- [ ] Implement the artwork proxy helper with content-type and size protections; it must not become a general URL proxy.
- [ ] Produce freshness headers compatible with the existing dashboard: `X-Sonos-Response-Source`, `X-Sonos-Response-Stale`, `X-Sonos-Observed-At`, and `X-Sonos-Age-Ms`.
- [ ] Implement semantic shadow comparison that ignores non-coordinator order, elapsed-time drift within tolerance, and artwork URL differences.

Suggested files:

- `sonos-api/src/server/home-assistant-sonos-state.ts`
- `sonos-api/src/server/sonos-artwork.ts`
- `sonos-api/src/server/sonos-shadow-compare.ts`
- Matching `*.spec.ts` files

Acceptance criteria:

- [ ] Single-room and eight-room fixtures project correctly.
- [ ] Two entities reporting the same group with different non-coordinator order produce the same canonical zone.
- [ ] Unknown state is not projected as a singleton group.
- [ ] Artwork permits only the current allowlisted entity-picture path, returns only image responses, and never exposes the bearer token.
- [ ] Shadow comparison reports meaningful topology, coordinator, volume, playback, and metadata differences without noise from ordering or time drift.
- [ ] `just test sonos-api` passes.

### Parallel wave 1C: Standard playback, volume, and topology actions

**Owned files:** new action/operation modules and tests only. Do not edit transport, state projection, presets, routes, manifests, dashboard files, or frozen contracts.

Deliverables:

- [ ] Implement play, pause, play/pause, next, and favorite selection against the frozen Home Assistant client interface.
- [ ] Implement manual join and idempotent leave.
- [ ] Implement a household topology serializer with duplicate coalescing and newest-request supersession.
- [ ] Implement join-all as one Home Assistant `media_player.join` service call over all fresh, available requested rooms.
- [ ] Implement partial join-all reporting for unavailable non-target rooms and hard failure for an unavailable target.
- [ ] Implement the characterized relative/absolute group-volume behavior with clamping.
- [ ] Implement `/same/:room` from authoritative group membership and member volumes.
- [ ] Do not retry accepted topology mutations. After a timeout, observe state and report the result without resubmitting.

Suggested files:

- `sonos-api/src/server/home-assistant-sonos-actions.ts`
- `sonos-api/src/server/sonos-operation-queue.ts`
- Matching `*.spec.ts` files

Acceptance criteria:

- [ ] Manual join targets the current coordinator of the destination group.
- [ ] Leaving a standalone room makes no service call or performs an idempotent Home Assistant unjoin, and returns success without changing other rooms.
- [ ] Leaving a coordinator produces the expected two groups from observed state rather than local prediction.
- [ ] A room moving from one group to another ends only in the requested destination group.
- [ ] Join-all submits one HA join call, not one call per room from application code.
- [ ] A manual leave submitted during join-all is processed after the in-flight call and becomes the final desired state.
- [ ] Relative volume preserves the characterized offsets; absolute volume matches the characterized node behavior; all results clamp safely.
- [ ] Service errors and timeouts remain visible to the caller and operation status.
- [ ] `just test sonos-api` passes.

### Parallel wave 1D: TV presets and convenience policies

**Owned files:** new preset/policy modules, repository preset definitions in their new format, and tests only. Do not edit action implementations, routes, manifests, dashboard files, or frozen contracts.

Deliverables:

- [ ] Convert every live-used preset into an allowlisted repository definition using room labels and Home Assistant sources, never RINCON IDs.
- [ ] Preserve the intended coordinator by making the first player the Home Assistant join target.
- [ ] Apply grouping, per-room volumes, `TV` source selection, and `pauseOthers` in a documented sequence.
- [ ] Define rollback behavior for partial preset failure. At minimum, surface the failed step and current observed topology; do not claim atomicity.
- [ ] Implement the used root convenience policies (`/up`, `/down`, `/tv`, `/07`, `/quiet`, `/pause`, `/play`) or mark them deprecated from Phase 0 evidence.
- [ ] Validate preset and favorite names at startup so typos fail health checks rather than the first wall-panel tap.

Suggested files:

- `sonos-api/src/server/home-assistant-sonos-presets.ts`
- `sonos-api/src/server/sonos-convenience-actions.ts`
- `sonos-api/presets/*.json` or a typed repository-owned equivalent
- Matching `*.spec.ts` files

Acceptance criteria:

- [ ] Bedroom TV results in Bedroom as coordinator with Bathroom and Closet, all at the configured volume, using Bedroom's `TV` source.
- [ ] Living Room TV results in Living Room as coordinator with Kitchen and Guest Bathroom, all at the configured volume, using Living Room's `TV` source, with `pauseOthers` parity.
- [ ] Office TV results in a standalone Office at its configured volume using `TV`.
- [ ] No preset contains a speaker UUID, IP address, raw `x-sonos-htastream` URI, or arbitrary entity ID.
- [ ] An unavailable member produces a clear partial/failure result and never leaves indefinite pending UI.
- [ ] Every retained convenience route has a unit test; every removed route has evidence and a deprecation note.
- [ ] `just test sonos-api` passes.

### Parallel wave 1E: Grid Dashboard authoritative-state presentation

**Owned files:** `grid-dashboard/ExpressServer/src/public/js/`, related CSS/HTML only if required, and their tests. Do not edit either server's Sonos routes or add-on manifests.

Deliverables:

- [ ] Keep checked/unchecked group indicators driven only by `/zones` observations.
- [ ] Retain the last confirmed membership while an operation is pending. Pending styling may add a border, spinner, or subtle overlay but must not replace the known check/X state.
- [ ] Treat stale-within-window separately from unknown. Stale keeps the last membership and shows age; unknown shows `?` and disables duplicate topology taps until fresh state returns.
- [ ] Reconcile manual operations and join-all status against observed zones.
- [ ] Clear pending on success, partial success, failure, supersession, or timeout without changing membership locally.
- [ ] Keep Safari 12-compatible JavaScript and the existing one-screen/touch behavior.
- [ ] Continue resolving artwork and action URLs relative to the ingress base.

Acceptance criteria:

- [ ] A selected room remains visibly checked while its leave request is in flight, with a separate pending treatment.
- [ ] Known joined rooms never become gray merely because join-all is still processing another room.
- [ ] An operation failure restores normal interaction and shows a concise failure while preserving observed checks.
- [ ] Stale and unknown fixtures produce distinct presentation states.
- [ ] Repeated taps while the same room mutation is pending issue at most one request.
- [ ] Existing single-tap/double-tap arbitration tests continue to pass.
- [ ] `just test grid-dashboard` passes.

### Phase 2: Integrate the parallel work — serial owner

Start only after wave 1 branches are individually green. Merge foundation first, then transport, state, actions, presets, and dashboard. Resolve interface mismatches centrally; do not ask one parallel branch to absorb another branch's unrelated implementation.

The integration owner owns the conflict-prone files:

- `sonos-api/src/server/sonos.ts`
- `sonos-api/src/server/config.ts`
- `sonos-api/src/server/index.ts`
- `sonos-api/addon.yaml`
- `sonos-api/package*.json` if required
- Existing `intents.ts`, `status-proxy.ts`, and their tests
- Grid Dashboard server proxy files only if the frozen response contract requires it

Actions:

- [ ] Wire backend selection for `node`, `shadow`, and `home_assistant` modes.
- [ ] In shadow mode, serve node responses and execute writes only through node while asynchronously comparing HA reads.
- [ ] In Home Assistant mode, serve reads and execute writes only through the HA backend.
- [ ] Add `homeassistant_api: true` to `sonos-api`; use `http://supervisor/core/api/` and `ws://supervisor/core/websocket` by default.
- [ ] Preserve injectable local-development URLs/tokens without adding secrets to options or defaults.
- [ ] Route all accepted names through the room/preset/favorite allowlists.
- [ ] Replace the current polling/retry intent implementation with the simple operation lifecycle while retaining compatibility endpoints.
- [ ] Keep stale response headers and add structured backend/action/duration/result logging.
- [ ] Extend `/health` so Home Assistant mode is ready only after a snapshot contains all expected rooms; report unavailable rooms as diagnostics without leaking state tokens.
- [ ] Add an integration test with fake node and fake Home Assistant servers proving that shadow mode never duplicates writes.

Acceptance criteria:

- [ ] The browser-facing route suite passes unchanged or with deliberately updated fixtures.
- [ ] Switching backend mode requires configuration only, not a rebuild.
- [ ] `node` mode remains a tested rollback until retirement.
- [ ] `shadow` makes exactly one write to node and zero writes to Home Assistant for every action test.
- [ ] `home_assistant` makes zero requests to node.
- [ ] Missing `SUPERVISOR_TOKEN` fails Home Assistant mode clearly and does not fall back silently to node.
- [ ] `just test sonos-api`, `just test grid-dashboard`, and root `just test` pass.

### Phase 3: Automated end-to-end validation

Add a deterministic test harness before live backend switching.

Required scenarios:

- [ ] Initial eight singleton rooms.
- [ ] One eight-room group with each possible configured coordinator.
- [ ] Multiple simultaneous groups.
- [ ] Manual non-coordinator leave.
- [ ] Manual coordinator/active-room leave.
- [ ] Standalone leave.
- [ ] Join a singleton to a group.
- [ ] Move a room between two groups.
- [ ] Join-all from a singleton and from a non-coordinator already in another group.
- [ ] Two fast join-all requests to different targets.
- [ ] Manual leave while join-all is in flight.
- [ ] One unavailable non-target and an unavailable target.
- [ ] WebSocket disconnect, stale window, unknown transition, and reconnect/resnapshot.
- [ ] Home Assistant service error and timeout without duplicate submission.
- [ ] Unequal volume group: relative, absolute, normalization, and clamps.
- [ ] Each TV preset, configured favorite, play/pause, and next.
- [ ] Artwork success, missing art, non-image upstream response, oversized response, and HA failure.
- [ ] Direct-port and ingress-relative URL construction.

Automated phase exit criteria:

- [ ] No test depends on room iteration order other than coordinator-first canonicalization.
- [ ] No test marks an intended group as observed before a state event/snapshot contains it.
- [ ] All duplicate-write assertions pass.
- [ ] All packages and add-on container builds pass under root `just test`.
- [ ] The complete behavior matrix and remaining live-only checks are included in the integration handoff.

## Live rollout

Live validation is a dedicated workstream with explicit authority to operate speakers. Do not intermingle it with feature implementation.

### Stage 1: Baseline and shadow mode

- [ ] Record Git revision, HA version, installed add-on versions, current groups, playback source, per-room volumes, unavailable rooms, and relevant restart counts.
- [ ] Retain the current deployed packages/configuration for Grid Dashboard, Sonos API, and Node Sonos HTTP API.
- [ ] Deploy `sonos-api` in `shadow` mode while leaving the dashboard and node control path unchanged.
- [ ] Observe at least 24 hours including external Sonos-app changes, TV source changes, grouping, favorites, and idle periods.
- [ ] Compare topology as coordinator plus member set; compare volume within one percentage point; compare playback state exactly; compare metadata while ignoring elapsed-time/artwork URL differences.
- [ ] Resolve every persistent divergence. Do not waive topology or coordinator differences as harmless.
- [ ] Confirm node port 5005 has no unexplained direct callers beyond the shadow/diagnostic path.

Shadow exit criteria:

- [ ] No unexplained topology divergence during the observation window.
- [ ] State freshness is normally event-driven and reconnection was observed or deliberately tested.
- [ ] No duplicated writes reached speakers.
- [ ] Sonos API and Grid Dashboard show no new restart, memory, or latency regression.
- [ ] Rollback to the prior node configuration has been rehearsed without uninstalling anything.

### Stage 2: Home Assistant backend pilot

Switch `sonos-api` to `home_assistant` mode while keeping the node add-on installed and available for rollback. Use one pilot wall panel first.

Run this live matrix and restore the starting group/volume/playback state afterward:

- [ ] Join one singleton room to the pilot room's group.
- [ ] Leave a non-coordinator room.
- [ ] Leave the active room when it is the coordinator; verify the former members remain coherent and the active room becomes singleton.
- [ ] Leave the already-standalone active room again; verify idempotence.
- [ ] Move a room from one existing group to another.
- [ ] Double-tap join-all from a singleton target.
- [ ] Double-tap join-all from a room that begins as a non-coordinator.
- [ ] Issue a manual leave while join-all is pending; verify the manual request is the final state.
- [ ] Play/pause, pause, next, every configured favorite, volume up/down, absolute 10, and volume normalization.
- [ ] Apply Bedroom TV, Living Room TV, and Office TV presets, verifying coordinator, members, source, volumes, and `pauseOthers` behavior.
- [ ] Temporarily stop or disconnect the HA state feed in a controlled test; verify stale then unknown presentation and recovery.
- [ ] Verify album art through direct port 3000 and Home Assistant ingress.

Pilot exit criteria:

- [ ] Every operation ends with UI membership matching Home Assistant `group_members` and the Sonos app.
- [ ] No room remains pending beyond the operation deadline.
- [ ] No join/leave service is submitted more than once per accepted user operation.
- [ ] Failures are visible and do not falsify membership.
- [ ] The starting live group, source, and volumes are restored.
- [ ] The pilot panel remains stable for at least 24 hours.

### Stage 3: Whole-house observation

- [ ] Enable the HA backend for all panels.
- [ ] Keep node installed but unused for a 48-hour observation window.
- [ ] Exercise normal household use rather than only scripted tests.
- [ ] Review action failures, topology timeouts, state age, reconnects, preset failures, artwork errors, and unexpected legacy-route calls.
- [ ] Verify no direct node requests occurred during the window.

Whole-house exit criteria:

- [ ] No unresolved P0/P1 Sonos behavior regression.
- [ ] No persistent topology divergence between UI, HA, and the Sonos app.
- [ ] No indefinite pending/intent presentation.
- [ ] No unexpected node API consumers remain.
- [ ] The user explicitly accepts the HA-backed behavior before node uninstall.

## Node retirement

Retirement is a separate, reversible deployment before repository deletion.

### Runtime retirement

- [ ] Remove `depends_on: node-sonos-http-api` from `sonos-api` and remove the node base URL from active configuration.
- [ ] Deploy the independent HA-backed Sonos API and verify health.
- [ ] Stop the node add-on without uninstalling it.
- [ ] Run the high-risk subset: state, manual leave/join, join-all, group volume, one favorite, and one TV preset.
- [ ] Observe at least 24 hours with node stopped.
- [ ] Uninstall node only after the stopped observation passes and a reinstallable prior package/configuration is retained.
- [ ] Verify port 5005 is closed and Sonos operation continues.

### Repository retirement

Delete and update only after runtime retirement passes:

- [ ] Remove `node-sonos-http-api/`, including patches, dependency overlay, presets, build files, and documentation.
- [ ] Remove node add-on references from root workflows, dependency graphs, deployment documentation, version documentation, and Sonos documentation.
- [ ] Update `docs/sonos/overview.md` and `docs/sonos/routing-guide.md` to the HA-backed architecture.
- [ ] Update `docs/operations/improvements.md` to mark the replacement complete and describe the remaining thin adapter.
- [ ] Update `sonos-api/README.md`, `sonos-api/addon.yaml`, option translations, and health documentation.
- [ ] Update `grid-dashboard/addon.yaml` descriptions that still call the Sonos base URL the node API.
- [ ] Remove backend modes `node` and `shadow`, legacy node client code, old intent polling code, status proxy code made obsolete by the HA state store, and their dependencies/tests.
- [ ] Retain compatibility routes that are still used; route removal is independent of node removal.

Repository retirement acceptance criteria:

- [ ] `rg -i "node-sonos-http-api|node_sonos_http_api|local-node-sonos-http-api"` returns only historical migration documentation intentionally retained in this plan or changelog.
- [ ] Add-on discovery no longer lists the node add-on.
- [ ] `sonos-api` has `homeassistant_api: true`, no `host_network`, and no Sonos discovery dependency.
- [ ] Root `just test` passes, including all configured container builds.
- [ ] A clean install/deploy of Sonos API and Grid Dashboard works without node ever being installed.
- [ ] The working tree is clean and the migration is represented by reviewable commits.

## End-to-end acceptance criteria

The migration is complete only when all of the following are true.

### Functional

- [ ] All eight dashboard rooms show the same membership as Home Assistant and the Sonos app.
- [ ] Manual join and leave work for members, coordinators, standalone rooms, and rooms moving between groups.
- [ ] Join-all works from any configured room and tolerates unavailable non-target rooms without misleading the known state.
- [ ] Playback, configured favorites, group volume, normalization, and all three room TV presets pass live parity checks.
- [ ] Album art and metadata work through ingress and direct dashboard access.

### Reliability and presentation

- [ ] Known membership remains visible while a command is pending.
- [ ] Pending status is bounded and always resolves to success, partial, failed, timed out, cancelled, or superseded.
- [ ] No topology command is blindly retried after Home Assistant accepted it.
- [ ] Disconnect/reconnect and stale/unknown behavior pass automated and live checks.
- [ ] Duplicate taps and overlapping group operations do not make an older request the final state.

### Operations and security

- [ ] The Supervisor token is server-side only and absent from logs/responses.
- [ ] Sonos API health detects missing HA authentication, missing expected entities, and stale initial state.
- [ ] Port 5005 is closed and the node add-on is absent from the live host.
- [ ] The prior node deployment remains recoverable for the agreed rollback-retention period.
- [ ] Documentation describes the actual deployed architecture and troubleshooting path.

### Repository quality

- [ ] Each parallel workstream was merged from the frozen contract base with scoped commits and handoff notes.
- [ ] Unit, integration, dashboard, root, and container tests pass.
- [ ] No live credentials, entity-picture tokens, IP addresses, or captured private media metadata were committed as fixtures.
- [ ] No obsolete runtime dependency or documentation claims that `sonos-api` requires node.

## Rollback

Before node uninstall, rollback is configuration-only:

1. Set Sonos API backend mode to `node`.
2. Restart Sonos API and verify `/health`, `/sonos/zones`, one state route, and a low-risk playback command.
3. Revert Grid Dashboard only if its compatibility contract changed; otherwise it should continue using the same routes.
4. Record the failed HA-backed operation and current topology before additional live mutation.

After node is stopped but before uninstall, restart the retained node add-on and perform the same configuration rollback.

After uninstall, reinstall the retained prior node package/configuration, restore the prior Sonos API package/configuration, and verify health before issuing actions. Do not attempt a hurried partial reimplementation during an outage.

Rollback triggers include:

- Repeated topology timeout or incorrect final grouping.
- A duplicate write that causes a newer manual request to be overwritten.
- Missing or incorrect coordinator behavior in a TV preset.
- State older than 30 seconds during otherwise healthy Home Assistant operation.
- Artwork/authentication behavior exposing credentials or breaking both panel access paths.
- Unbounded pending UI, recurring add-on restarts, or a material control-latency regression.

## Clean-context sub-agent handoff template

Every implementation assignment should include the following information so the agent does not need prior conversation history:

```text
Start from integration-base commit <exact SHA> in a clean branch/worktree.
Read /AGENTS.md and <owned add-on>/AGENTS.md completely.
Implement only workstream <ID and title> from docs/plan-replace-sonos-node-api.md.
Owned files: <exact list>. Do not edit frozen contracts or another workstream's files.
Do not deploy or operate the live Sonos system unless this assignment explicitly says live validation.
Use repository just recipes and run <scoped test command>.
Commit the scoped result with a descriptive message.
In the handoff report include: commit SHA, files changed, tests run/results, assumptions,
contract gaps, and any live validation still required.
```

The integration owner must receive every workstream's commit SHA and handoff report. A branch is not ready to merge merely because its local unit tests pass; it must also respect the frozen contract, owned-file boundary, security rules, and acceptance criteria above.
