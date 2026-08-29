# Replace node-sonos-http-api with Home Assistant Sonos control

> **Status:** Source version 1.1.1 is prepared for the immutable candidate. The deployed 1.1.0 dirty-worktree build and all tests run before the final 1.1.1 commit are diagnostic or superseded evidence only. The corrected package must be committed, tested, deployed, and re-baselined before a new 24-hour shadow clock can start; every later live gate remains pending.
>
> **Investigation baseline:** 2026-08-28, repository `36882c3`, Home Assistant Core 2026.8.3
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

The Grid Dashboard currently calls the following routes through its own server. The first Home Assistant release must match the exact Phase 0 method, path, status, media type, header, success-schema, and error-schema contracts so backend and frontend work can be deployed independently; any exception requires explicit approval in the validation record.

| Existing route | Required Home Assistant-backed behavior |
| --- | --- |
| `GET /sonos/zones` | Return canonical groups derived from `group_members`. Treat membership as a set; put the coordinator first and sort remaining members for a stable response. |
| `GET /sonos/:room/state` | Return the existing dashboard state shape projected from the room entity and its group coordinator. |
| `GET /sonos/:room/artwork` | Stream the current room artwork through both server layers without changing image bytes; apply the artwork allowlist, size, MIME, redirect, and authentication rules below. |
| `GET /sonos/:room/play` | Call `media_player.media_play`. |
| `GET /sonos/:room/pause` | Call `media_player.media_pause`. |
| `GET /sonos/:room/playpause` | Call `media_player.media_play_pause`. |
| `GET /sonos/:room/next` | Call `media_player.media_next_track`. |
| `GET /sonos/:room/favorite/:name` | Validate `name` against the entity's `source_list`, then call `media_player.select_source`. |
| `GET /sonos/:room/join/:target` | Make `room` join the current group containing `target`. Target the group's current coordinator, not merely the requested label. |
| `GET /sonos/:room/leave` | Call `media_player.unjoin` for `room`; a standalone room is an idempotent success. |
| `GET /sonos/:room/groupVolume/:value` | Preserve characterized group-volume behavior using per-member Home Assistant volume calls. |
| `GET /sonos/:room/volume/:value` | Set the allowlisted room's volume using `media_player.volume_set`, preserving the frozen validation and error contract. |
| `GET /same/:room` | Set every member of the room's current group to that room's volume. |
| `GET /sonos/:room/preset/:name` | Apply an allowlisted, repository-owned preset using Home Assistant services. |
| `POST /sonos-intents/group-all` | Retain the compatibility endpoint, but enqueue one serialized Home Assistant join operation rather than an open-ended per-room retry loop. |
| `GET /sonos-intents/status` | Return the operation lifecycle for compatibility. Known membership still comes only from `/zones`. |
| `GET /up`, `/down` | Preserve the characterized convenience policies in every migration mode. |
| `GET /pause`, `/play`, `/tv`, `/07`, `/quiet` | In `home_assistant` mode, return the frozen `410` deprecated-route response through both HTTP layers with zero writes. In `node` and `shadow`, preserve exact pass-through behavior for configuration rollback until retirement. |

The compatibility layer may introduce a new compact state endpoint, but the legacy routes cannot be removed until the deployed dashboard no longer calls them and the observation logs show no other callers.

### Source-family compatibility (frozen)

Home Assistant's `source`, `source_list`, and `media_content_*` fields are not a
provider-neutral replacement for node API inputs. SiriusXM/radio favorites,
Apple Music, TV/SPDIF, line-in, and other favorites each have distinct action
and URI semantics. The detailed matrix is maintained in
[Sonos source compatibility](sonos/source-compatibility.md) and is part of the
acceptance contract:

- Normalize state transport, metadata, artwork, volume, and mute into the
  legacy response, while retaining coordinator-owned metadata and
  requested-member volume/mute.
- Match favorites by exact observed title; use physical `TV`/`Line-in` source
  names only when advertised by the target model; never persist raw RINCON or
  `x-sonos-htastream` values in repository presets.
- Treat Apple Music as `play_media` (share link or stable favorite item ID),
  not as an assumed `source_list` entry or `select_source` provider.
- Preserve URI families and source-specific metadata, but ignore dynamic
  stream UUIDs and independent elapsed clocks in parity comparisons.

Every root route classified as deprecated must return `410` with `code: "deprecated_route"` through both the Grid Dashboard and Sonos API boundaries and make zero node or Home Assistant writes in HA mode. In node/shadow rollback modes the same Grid routes remain exact pass-throughs so current behavior is recoverable until retirement.

### State projection rules

The compatibility projection must be deterministic and independently unit tested.

| Existing field | Home Assistant source or rule |
| --- | --- |
| `volume` | `round(volume_level * 100)` |
| `mute` | `is_volume_muted` |
| `playbackState` | `playing -> PLAYING`; paused on-demand media -> `PAUSED_PLAYBACK`; paused live radio -> `STOPPED` because that is the live-observed node result; other available states -> `STOPPED`. |
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

Home Assistant's `entity_picture` cannot simply be handed to every panel: it is a Home Assistant-relative authenticated URL. Add an artwork proxy that fetches the current picture through the Core API and streams only approved raster image content. The state response should use an ingress-relative URL such as `./sonos/<encoded-room>/artwork?rev=<safe-revision>` so both direct port access and Home Assistant ingress work and a track/art change is not hidden by browser caching. The revision must be derived from accepted state/art version data, never from Home Assistant's signed query. Unchanged art keeps a stable revision; changed art produces a new browser URL/request even if the internal proxy route ignores that cache key.

Fields retained only for historical node compatibility, such as an empty `nextTrack` or unused equalizer data, must have documented defaults. Do not issue extra Home Assistant service calls or entity reads for fields that no repository consumer uses.

Phase 0 must freeze complete golden response shapes, not only the fields listed above. The `/zones` contract includes zone UUID, coordinator, members, member UUID/coordinator, `groupState`, and each nested member state. The room-state contract also accounts for `equalizer`, `currentTrack.albumArtUri`, `currentTrack.absoluteAlbumArtUri`, `currentTrack.duration`, `currentTrack.trackUri`, `currentTrack.type`, `nextTrack`, `trackNo`, `elapsedTimeFormatted`, `playMode`, and `sub`. Each field must be classified as projected, derived, constant compatibility default, or deliberately removed with consumer evidence.

The same contract must identify entity ownership for every projected field. In particular, freeze which values come from the requested member (including volume/mute) and which, if any, come from the observed coordinator (including transport, metadata, and artwork). Also characterize whether playback and favorite actions target the requested member or its observed coordinator; do not infer this from labels or assume parity without a test.

Artwork is binary end to end. The Grid Dashboard proxy cannot pass it through a text-response helper. Both server layers must preserve allowed image bytes and content type exactly, reject SVG and other active content, reject redirects and unapproved URL forms, enforce declared and streamed byte limits, and set `X-Content-Type-Options: nosniff`. Neither layer may expose a signed `entity_picture` query, an absolute Home Assistant URL, or a bearer token in a body, header forwarded to the browser, URL, log, or error.

For a follower room, track metadata, artwork revision identity, authenticated entity-picture path, and returned bytes all belong to the observed coordinator; the public compatibility URL remains follower-relative. A follower/coordinator mismatch or malformed ownership fails with the frozen error and performs no artwork fetch.

### Freshness and availability

- The backend obtains an initial state snapshot and subscribes to Home Assistant `state_changed` events over `ws://supervisor/core/websocket`.
- The server authenticates with `SUPERVISOR_TOKEN`; the token never appears in responses, logs, artwork URLs, or browser code. Home Assistant documents this app communication path at [App communication](https://developers.home-assistant.io/docs/apps/communication/).
- Freshness is based on the authenticated subscription's liveness, not the time of the last speaker change. A healthy, quiet WebSocket keeps the last snapshot live indefinitely; `observedAt` may be old without making unchanged state stale.
- Use a frozen application-level ping/watchdog deadline to detect a half-open socket. A close, authentication/subscription failure, or missed liveness deadline marks the state stale immediately and starts the 30-second stale window.
- A disconnected WebSocket reconnects with bounded exponential backoff and performs a gap-free fresh snapshot before marking state live again. It remains stale during reconnect and resnapshot even if the socket has reopened.
- The last confirmed state may be served as stale for at most 30 seconds after transport liveness is lost, retaining the known checked/unchecked membership plus a stale indication and age since connection loss.
- At 30 seconds after transport liveness is lost, topology is unknown. Do not convert unknown entities into an empty response, singleton zones, or unchecked rooms.
- Every Home Assistant-backed write is rejected with the normalized `503` response and zero Home Assistant service calls whenever the subscription is not `live`, including playback, favorites, joins, leaves, join-all, room/group volume, normalization, presets, `/up`, and `/down`. There is no write grace period at disconnect age zero. Read-only zones, room-state, and artwork responses may use the last confirmed snapshot only during the 30-second stale window and must carry the frozen freshness headers; unknown state fails closed.
- Topology mutations are also rejected with `503` whenever the target or anchor entity is unavailable. A healthy quiet entity does not expire solely because its `last_updated` value is old.
- An unavailable non-target in join-all is reported explicitly. Available rooms may still be joined once; joined rooms must immediately display their observed membership, while unavailable rooms show a concise failure rather than indefinite pending gray.

### Command and operation lifecycle

Topology commands need a small serializer, not a second Sonos topology engine:

1. Validate the room allowlist and fresh state.
2. Assign an operation ID and mark only the affected control pending.
3. Serialize topology mutations for the household.
4. Call the appropriate Home Assistant service only as required by the observed topology. A join-all normally uses one `media_player.join` request whose target is the selected coordinator and whose `group_members` contains the available requested rooms, or zero calls when observed topology already satisfies the request. The only two-step exception is when the requested target is currently a follower: first submit one `media_player.unjoin` for that target, wait for authoritative detachment, then submit one `media_player.join` with that target as coordinator. No step is retried.
5. Wait for the service result and authoritative state observation. Do not repeatedly resubmit a join because an HTTP request timed out.
6. Complete, partially complete, or fail the operation from observed membership.
7. Clear pending presentation without changing the last confirmed checked/unchecked membership.

If a manual mutation arrives while join-all is running, mark join-all superseded and queue only the newest desired mutation. The Home Assistant call already in flight cannot be canceled safely; after it settles, apply the newer command and let the newest observed topology win. Duplicate taps for the same room and desired state must coalesce.

Playback and volume commands do not enter the topology queue. They must still require a `live` state snapshot, validate the room, and propagate Home Assistant errors rather than returning an unconditional success. Playback, favorite, and direct room-volume actions target the requested allowlisted member; joins resolve the requested destination to its observed coordinator, while state metadata and artwork use the observed coordinator and retain requested-member volume/mute.

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
11. Run `just addon-state-backup` only with the tested transport that resolves the repository-local identity (including from a linked worktree), passes `IdentitiesOnly=yes` to SSH/SCP, preserves `homeassistant.local`, and stops on authentication or mDNS failure without alternate credentials.

## Acceptance evidence and regression-test rules

Acceptance is based on observable outcomes, not implementation completion. Each phase exit criterion must have one of these forms of evidence in the integration handoff:

- An automated test name and the command that ran it at the candidate commit.
- A sanitized before/after fixture comparison with the exact differing fields explained.
- A live validation record containing the date, versions, starting state, action, observed final state, and restoration result.

Track this evidence in `docs/sonos/ha-migration-validation.md`, committed alongside the implementation. Parallel workstreams return evidence in their handoffs without editing this serially owned file; the foundation owner creates it, and the integration/live owner updates it between phase gates. An unchecked criterion blocks the next phase. Any exception requires explicit user approval and must record the unmet criterion, impact, owner, expiry, and tested rollback; an exception cannot waive credential exposure, duplicate writes, invented topology, or a failing root test.

Regression tests follow these rules:

- Phase 0 records a green baseline for `just test sonos-api`, `just test grid-dashboard`, and root `just test` before behavior changes.
- The `sonos-api` test command must discover every `src/**/*.spec.ts` suite instead of enumerating today's three files. It must fail when no suites are found, fail on any suite error, and report the executed suite paths so later workstreams cannot add unexecuted tests accidentally.
- Tests use sanitized, immutable node and Home Assistant fixtures. A test may derive a new object from a fixture but must not mutate the shared fixture or depend on test order.
- Time, HTTP, WebSocket, timers, and randomness are injected. Automated tests use no live network, credentials, sleeps, or wall clock.
- Every legacy route has a route-level contract test at both `sonos-api` and the Grid Dashboard proxy boundary. Tests assert method, encoded path, status, content type, required freshness headers, response shape, and normalized error shape; they do not couple to irrelevant JSON key order.
- Golden compatibility cases are captured against the node backend before replacement. The same cases run against Home Assistant mode, with each intentionally changed field documented and approved.
- Boundary values are tested immediately before and at each frozen timeout or size limit, including the 30-second stale-to-unknown transition. There is no untested gap between stale, unknown, timed out, and terminal states.
- A live test supplements but never replaces an automatable unit, route, integration, security, or presentation regression.

Phase 0 must freeze the currently unspecified operational limits before parallel work begins: WebSocket liveness deadline, topology operation deadline, matching Dashboard pending deadline, terminal-status retention, REST/service timeout, WebSocket reconnect schedule, shadow convergence grace, artwork byte limit, shadow comparison field exclusions, rollback RTO, rollback-artifact retention period, P0/P1 severity definitions, and the shadow/pilot latency and memory budgets. Elapsed time is excluded from every shadow equality comparison because the backends advance it from independent clocks; projection correctness remains testable independently. Later acceptance criteria use those recorded values rather than phrases such as "reasonable" or "material regression."

## Parallel implementation strategy

Parallel work starts only after shared interfaces and fixtures are frozen. Each workstream must have explicit file ownership and a recorded handoff; it may use a separate branch/worktree or integrate into one dedicated candidate worktree when the collaboration runtime shares a filesystem. If a frozen interface is insufficient, the agent reports the required contract change instead of modifying it unilaterally. The integration owner may produce scoped commits or one documented integration commit, provided the validation record ties every handoff and regression command to the immutable candidate SHA.

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
- [x] Run and record the pre-migration baseline for `just test sonos-api`, `just test grid-dashboard`, and root `just test`; isolate any pre-existing failure, prove it is unrelated, and require the candidate to repair it or record an explicit exception.
- [x] Replace the enumerated `sonos-api` test script with a discovery-based runner for all `src/**/*.spec.ts` suites, and prove a newly added route-contract suite is executed by `just test sonos-api`.
- [ ] Capture the live node preset inventory from its persistent configuration and reconcile it with the three repository preset files. Record names, players, order/coordinator, volumes, URI/source, `pauseOthers`, and any sleep/play-mode fields without copying secrets.
- [ ] Exercise or inspect each existing convenience route and classify it as dashboard-used, externally used, unused, or unknown.
- [x] Freeze table-driven contracts for both browser-facing `/sonos-intents/*` routes and internal Sonos API `/intents/sonos/*` routes, plus the complete `/zones`, room-state, and artwork responses.
- [ ] Characterize node `groupVolume` for relative and absolute changes with unequal member volumes, including clamping at 0 and 100. This result becomes the parity specification; do not guess the algorithm.
- [ ] Verify every configured favorite name in `grid-dashboard/ExpressServer/src/public/js/config.js` appears in the live Home Assistant `source_list`.
- [x] Freeze the source-family matrix for SiriusXM/radio, Apple Music, TV/SPDIF, line-in, and other favorites, including source-specific input, URI, metadata, and legacy-state normalization rules in [Sonos source compatibility](sonos/source-compatibility.md).
- [x] Add source-family projection and exact source-selection regressions for radio, Apple Music service URIs, TV/SPDIF, line-in, and grouped coordinator/member ownership.
- [ ] Verify the eight-room entity map and capture representative playing, paused, stopped, unavailable, single-room, and multi-room HA state fixtures.
- [x] Add frozen backend interfaces, room mapping, normalized error shape, and fixtures in files reserved for foundation ownership.
- [x] Add the backend-mode contract: `node`, `shadow`, and `home_assistant`. Shadow serves and writes through node while comparing HA reads; it never duplicates a write.
- [x] Define structured comparison output and ensure it excludes tokens and complete authenticated artwork URLs.
- [x] Freeze the WebSocket liveness, operation, Dashboard pending, REST/service, and rollback timeouts; reconnect schedule, artwork limit, comparison tolerances, terminal retention, and measurable rollout resource/latency budgets.
- [x] Reconcile the current 15-second Dashboard mutation timeout with the current 45-second backend intent deadline. The frozen UI rule must not re-enable a topology control while its backend operation is active, and fake-clock tests must cover the chosen deadline and status-based release.
- [x] Freeze the operation schema and allowed state transitions for running, completed, partially completed, failed, timed out, cancelled, and superseded results, including whether each route responds synchronously or with an operation.
- [x] Freeze field ownership between requested member and coordinator, plus target semantics for every playback/favorite/group action.
- [x] Freeze how each manual join/leave response exposes an operation ID/status and how the Dashboard correlates immediate failures and later terminal status; separately define which playback/volume routes remain allowed when topology transport is stale or unknown.
- [x] Freeze the exact unknown-topology HTTP contract for zones, room state, and mutations; unknown must never appear as `[]`, invented singleton zones, unchecked rooms, or a successful mutation.
- [x] Create the migration validation record and a traceability table mapping every retained route and end-to-end behavior to its automated suite and any required live check.

Recommended foundation-owned files:

- `sonos-api/src/server/sonos-contract.ts`
- `sonos-api/src/server/sonos-room-map.ts`
- `sonos-api/src/server/__fixtures__/home-assistant-sonos.ts`
- `sonos-api/src/server/__fixtures__/node-sonos.ts`
- Contract-only additions to `sonos-api/src/types/sonos/index.ts`
- The `sonos-api` test-runner entry point and test-script-only changes to `sonos-api/package.json`
- `docs/sonos/ha-migration-validation.md` (serial owners only; parallel agents return evidence in handoffs)

Foundation acceptance criteria:

- [x] The route inventory covers both HTTP layers and records, for every retained route, method, path/parameters, success status/media type/schema/defaults, freshness headers, normalized error status/schema, caller, and disposition.
- [ ] The route inventory fails if a retained route is missing its method, response contract, negative cases, or Grid Dashboard proxy test.
- [ ] No route, favorite, preset, or externally used behavior remains classified as unknown; every parity change has explicit user approval.
- [ ] Room labels and entity IDs are one-to-one and duplicate-free.
- [x] Fixture tokens and entity-picture authentication values are synthetic.
- [x] Golden fixtures cover the complete legacy zone/member/state shape, and every field is classified as projected, derived, compatibility default, or approved removal.
- [x] The backend interface covers reads, playback, favorites, grouping, volume, presets, and operation status without exposing a generic service-call method to route handlers.
- [x] `just test sonos-api` reports and executes every discovered suite, including the new route-contract suite.
- [ ] All operational limits and rollout budgets are numeric, named, and represented by boundary tests or a named live measurement.
- [ ] The checked-in characterization covers the room map, complete route classifications, presets, favorites, group-volume algorithm, operation/unknown schemas, representative fixtures, and every approved parity exception.
- [x] The checked-in characterization explicitly records that Apple Music node-only queue/search endpoints are not interchangeable with Home Assistant `select_source`; retained compatibility routes use exact favorite titles/IDs or physical `TV`/`Line-in` names only.
- [ ] `just test sonos-api` passes.
- [ ] The foundation commit hash is supplied to every parallel agent.

### Parallel wave 1A: Home Assistant transport and state store

**Owned files:** new transport/state-store modules and their tests only. Do not edit `sonos.ts`, `config.ts`, manifests, dashboard files, or frozen contracts.

Deliverables:

- [x] Implement an injectable Core REST client using the internal Supervisor API and bearer token.
- [x] Implement initial state loading for the allowlisted entities.
- [x] Implement WebSocket authentication, `state_changed` subscription, reconnect/backoff, resnapshot, and shutdown cleanup.
- [x] Make snapshot/subscription startup and reconnect gap-free by buffering or reconciling events that arrive while a snapshot is in flight.
- [x] Track `observedAt`, connection state, and stale age without mutating entity payloads.
- [x] Provide dependency injection for clock, HTTP, WebSocket, and timers so tests use no live Home Assistant instance.
- [x] Ensure REST and WebSocket errors are normalized and never include credentials.

Suggested files:

- `sonos-api/src/server/home-assistant-client.ts`
- `sonos-api/src/server/home-assistant-state-store.ts`
- Matching `*.spec.ts` files

Acceptance criteria:

- [x] Authentication success, rejection, clean shutdown, reconnect, duplicate event, out-of-order event, and resnapshot paths are tested.
- [x] An event arriving during initial snapshot or reconnect cannot be lost or overwritten by an older snapshot.
- [x] Malformed messages, unrelated entity events, authentication timeout, subscription rejection, and disconnect during resnapshot are tested.
- [x] Reconnect leaves exactly one active subscription; shutdown cancels reconnect timers and in-flight snapshot/authentication work.
- [x] An older `last_updated` event cannot replace a newer room state.
- [x] A quiet healthy subscription remains live beyond 30 seconds; after transport loss, state is stale through 29,999 ms and unknown at 30,000 ms; reconnect remains stale until the replacement snapshot completes.
- [x] Recognizable synthetic credentials injected into REST, WebSocket, timeout, and malformed-response failures are absent from returned errors and captured logs.
- [x] No test uses network access or real tokens.
- [ ] `just test sonos-api` passes.

### Parallel wave 1B: Home Assistant state compatibility projection

**Owned files:** new projection/artwork modules and tests only. Do not edit transport, routes, manifests, dashboard files, or frozen contracts.

Deliverables:

- [x] Project allowlisted HA entity states into canonical groups and the existing room-state response.
- [x] Canonicalize groups by coordinator plus sorted remaining room names.
- [x] Reject malformed groups, unknown entity IDs, duplicate room membership, and a coordinator not contained in its group.
- [x] Implement playback-state, metadata, elapsed-time, volume, mute, and compatibility defaults.
- [x] Implement the artwork proxy helper with content-type and size protections; it must not become a general URL proxy.
- [x] Produce freshness headers compatible with the existing dashboard: `X-Sonos-Response-Source`, `X-Sonos-Response-Stale`, `X-Sonos-Observed-At`, and `X-Sonos-Age-Ms`.
- [x] Implement semantic shadow comparison that ignores non-coordinator order, elapsed time for all media, and artwork URL differences.

Suggested files:

- `sonos-api/src/server/home-assistant-sonos-state.ts`
- `sonos-api/src/server/sonos-artwork.ts`
- `sonos-api/src/server/sonos-shadow-compare.ts`
- Matching `*.spec.ts` files

Acceptance criteria:

- [x] Single-room and eight-room fixtures project correctly.
- [x] Playing, paused, stopped, buffering/idle, unavailable, missing-attribute, and malformed-state fixtures produce the frozen compatibility response or normalized error.
- [x] Follower-room state uses coordinator metadata where the legacy contract requires it while preserving the follower's own volume and mute values.
- [x] Single-, multi-, and eight-room groups plus every configured coordinator deep-equal the frozen complete response fixtures.
- [x] Two entities reporting the same group with different non-coordinator order produce the same canonical zone.
- [x] Missing, unknown, duplicate, or malformed membership follows the frozen unknown/error contract and never yields an empty, partial, or singleton invented topology.
- [x] Artwork permits only the current allowlisted entity-picture path and frozen safe raster MIME allowlist, rejects SVG, absolute/protocol-relative/traversal URLs, and redirects, enforces the byte limit for both declared and streamed sizes, sets `X-Content-Type-Options: nosniff`, and never exposes the bearer or signed-picture token.
- [x] Two successive art revisions produce distinct token-free browser URLs and updated exact bytes through both proxy layers, while unchanged art keeps a stable revision.
- [x] Live, stale, and unknown responses assert the exact frozen freshness header names and values.
- [x] Shadow comparison reports meaningful topology, coordinator, volume, playback, and metadata differences without noise from ordering, elapsed time, or artwork URLs.
- [ ] `just test sonos-api` passes.

### Parallel wave 1C: Standard playback, volume, and topology actions

**Owned files:** new action/operation modules and tests only. Do not edit transport, state projection, presets, routes, manifests, dashboard files, or frozen contracts.

Deliverables:

- [x] Implement play, pause, play/pause, next, and favorite selection against the frozen Home Assistant client interface.
- [x] Implement manual join and idempotent leave.
- [x] Implement a household topology serializer with duplicate coalescing and newest-request supersession.
- [x] Implement join-all as one Home Assistant `media_player.join` service call over all fresh, available requested rooms, except for the frozen follower-target case, which uses exactly one prerequisite `media_player.unjoin` and then exactly one `media_player.join` after observed detachment.
- [x] Make already-satisfied manual join and join-all idempotent with zero Home Assistant writes.
- [x] Implement partial join-all reporting for unavailable non-target rooms and hard failure for an unavailable target.
- [x] Implement the characterized relative/absolute group-volume behavior with clamping.
- [x] Implement `/same/:room` from authoritative group membership and member volumes.
- [x] Validate every affected member before multi-call group-volume or `/same` submission; report failed members and current observed volumes on partial failure without claiming atomic rollback or full success.
- [x] Do not retry accepted topology mutations. After a timeout, observe state and report the result without resubmitting.
- [x] Keep operation IDs and status transitions monotonic and deterministic through completion, partial completion, failure, timeout, cancellation, supersession, and terminal retention expiry.

Suggested files:

- `sonos-api/src/server/home-assistant-sonos-actions.ts`
- `sonos-api/src/server/sonos-operation-queue.ts`
- Matching `*.spec.ts` files

Acceptance criteria:

- [x] Manual join targets the current coordinator of the destination group.
- [x] Every action sends the exact frozen Home Assistant domain, service, target, and service-data payload; invalid or unavailable rooms fail before any service call.
- [x] Invalid room, target, favorite, preset, and volume inputs return the frozen `4xx` response with zero HA calls; disconnected or unavailable topology inputs return the frozen `503` response with zero HA calls.
- [x] Leaving a standalone room makes no service call or performs an idempotent Home Assistant unjoin, and returns success without changing other rooms.
- [x] Leaving a coordinator produces the expected two groups from observed state rather than local prediction.
- [x] A room moving from one group to another ends only in the requested destination group.
- [x] Join-all submits at most one HA join call, not one call per room from application code, and submits zero when authoritative topology already satisfies the request; when the requested target starts as a follower, it submits exactly one unjoin before that one join and tests assert both ordered calls.
- [x] A manual leave submitted during join-all is processed after the in-flight call and becomes the final desired state.
- [x] State events arriving before the service response, after the service response, after timeout, and from a superseded operation cannot complete the wrong operation or cause another service call.
- [x] An operation reports success only after matching membership is observed; a missing or mismatched observation reaches a terminal status by the frozen deadline without resubmission.
- [x] Success, service error, request timeout, and late observation each produce exactly one HA topology call per accepted operation.
- [x] Relative volume preserves the characterized offsets; absolute volume matches the characterized node behavior; all results clamp safely.
- [x] Group-volume and `/same` tests assert exact member write counts; partial failure reports failed members and current observed volumes without falsely claiming all members changed, and unchanged `/same` members receive no call.
- [x] Service errors and timeouts remain visible to the caller and operation status.
- [ ] `just test sonos-api` passes.

### Parallel wave 1D: TV presets and convenience policies

**Owned files:** new preset/policy modules, repository preset definitions in their new format, and tests only. Do not edit action implementations, routes, manifests, dashboard files, or frozen contracts.

Deliverables:

- [ ] Convert every live-used preset into an allowlisted repository definition using room labels and Home Assistant sources, never RINCON IDs.
- [ ] Preserve the intended coordinator by making the first player the Home Assistant join target.
- [ ] Apply grouping, per-room volumes, `TV` source selection, and `pauseOthers` in a documented sequence.
- [ ] Define rollback behavior for partial preset failure. At minimum, surface the failed step and current observed topology; do not claim atomicity.
- [ ] Implement the used root convenience policies `/up` and `/down`; enforce the frozen mode-dependent contract for `/tv`, `/07`, `/quiet`, `/pause`, and `/play` (`410`/zero writes in HA mode, exact pass-through in node/shadow until retirement).
- [ ] Validate repository preset/favorite structure at startup in every mode. Treat live Home Assistant `source_list` mismatches as diagnostics in shadow mode and readiness failures in Home Assistant mode; node rollback mode must not become unhealthy merely because HA source data is absent.
- [x] Document and test that TV/SPDIF presets select exact `TV`, never a raw `x-sonos-htastream` URI; physical `Line-in` is a separate source and is not inferred from a TV preset.

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
- [ ] Failure at each preset step reports that step and the observed topology; tests do not assert nonexistent atomic rollback.
- [ ] Structurally invalid preset/favorite definitions make health non-ready in every mode before any service call; live HA source mismatches follow the frozen mode-aware node/shadow/HA policy, and `pauseOthers` tests name the exact rooms paused and left untouched.
- [ ] Every retained convenience route has a unit test; every removed route has evidence and a deprecation note.
- [ ] `just test sonos-api` passes.

### Parallel wave 1E: Grid Dashboard authoritative-state presentation

**Owned files:** `grid-dashboard/ExpressServer/src/public/js/`, related CSS/HTML only if required, and their tests. Do not edit either server's Sonos routes or add-on manifests.

Deliverables:

- [ ] Keep checked/unchecked group indicators driven only by `/zones` observations.
- [ ] Retain the last confirmed membership while an operation is pending. Pending styling may add a border, spinner, or subtle overlay but must not replace the known check/X state.
- [ ] Treat stale-within-window separately from unknown. Stale keeps the last membership and shows age; unknown shows `?`; neither state permits topology taps until fresh state returns.
- [ ] Disable every topology mutation while state is stale or unknown. Apply the separately frozen degraded-mode policy to playback and volume routes.
- [ ] When room state becomes unknown, clear or visibly mark old metadata and artwork as unknown so they cannot appear current; recover them only from a fresh response.
- [ ] Reconcile manual operations and join-all status against observed zones.
- [ ] Clear pending on success, partial success, failure, supersession, or timeout without changing membership locally.
- [ ] Correlate manual mutation responses and operation status by operation ID so an immediate failure clears pending promptly and an unrelated or late result cannot clear another control.
- [ ] Keep Safari 12-compatible JavaScript and the existing one-screen/touch behavior.
- [ ] Continue resolving artwork and action URLs relative to the ingress base.

Acceptance criteria:

- [ ] A selected room remains visibly checked while its leave request is in flight, with a separate pending treatment.
- [ ] Known joined rooms never become gray merely because join-all is still processing another room.
- [ ] An operation failure restores normal interaction and shows a concise failure while preserving observed checks.
- [ ] Stale and unknown fixtures produce distinct presentation states.
- [ ] Fake-clock tests cover pending through every terminal status and the frozen pending deadline; stale retains the last checks, while unknown disables every topology mutation.
- [ ] Repeated taps while the same room mutation is pending issue at most one request.
- [ ] A late status response from a superseded operation cannot clear or overwrite the newer operation's presentation.
- [ ] The stale-to-unknown transition does not leave old track metadata or artwork presented as current, and a later fresh state restores them.
- [ ] Existing single-tap/double-tap arbitration tests continue to pass.
- [ ] A named automated compatibility check rejects syntax unsupported by Safari 12 in directly served Dashboard JavaScript, and the live pilot repeats the check on an actual panel.
- [ ] `just test grid-dashboard` passes.

### Phase 2: Integrate the parallel work — serial owner

Start only after wave 1 branches are individually green. Merge foundation first, then transport, state, actions, presets, and dashboard. Resolve interface mismatches centrally; do not ask one parallel branch to absorb another branch's unrelated implementation.

The integration owner owns the conflict-prone files:

- `sonos-api/src/server/sonos.ts`
- `sonos-api/src/server/config.ts`
- `sonos-api/src/server/index.ts`
- `sonos-api/src/server/graceful-shutdown.ts` and its spec, or the replacement lifecycle module
- `sonos-api/addon.yaml`
- `sonos-api/run.sh`
- `sonos-api/package*.json` if required
- Existing `intents.ts`, `status-proxy.ts`, and their tests
- `grid-dashboard/ExpressServer/src/server/sonos.ts`, `http.ts`, `config.ts`, and their tests for route compatibility, binary artwork streaming, and the standalone local Sonos API default

Actions:

- [ ] Wire backend selection for `node`, `shadow`, and `home_assistant` modes.
- [ ] Keep `node` as the safe default when an upgraded installation has no `backend_mode`; require an explicit option change to enter `shadow` or `home_assistant`. After final retirement, remove the other modes and make Home Assistant the sole/default backend.
- [ ] In shadow mode, serve node responses and execute writes only through node while asynchronously comparing HA reads.
- [ ] In Home Assistant mode, serve reads and execute writes only through the HA backend.
- [ ] Add `homeassistant_api: true` to `sonos-api`; use `http://supervisor/core/api/` and `ws://supervisor/core/websocket` by default.
- [ ] Set `homeassistant_min` to the live-verified 2026.8.3 behavior baseline, or provide compatibility evidence for every older supported Core version before retaining a lower minimum.
- [ ] Preserve injectable local-development URLs/tokens without adding secrets to options or defaults.
- [ ] Document and test local development outside Supervisor with non-committed Core REST URL, WebSocket URL, and token environment values; these are development inputs, not add-on options or checked-in defaults.
- [ ] Update and test the packaged `run.sh`, add-on schema/translations, and Talos launcher path so `/data/options.json` supplies `backend_mode`; prove old options containing only `sonos_base_url` still start in node mode.
- [ ] Route all accepted names through the room/preset/favorite allowlists.
- [ ] Replace the current polling/retry intent implementation with the simple operation lifecycle while retaining compatibility endpoints.
- [ ] Keep stale response headers and add structured backend/action/duration/result logging.
- [ ] Extend `/health` so Home Assistant mode is ready only after a snapshot contains all expected rooms; report unavailable rooms as diagnostics without leaking state tokens.
- [ ] Add an integration test with fake node and fake Home Assistant servers proving that shadow mode never duplicates writes.
- [ ] Wire asynchronous lifecycle cleanup so shutdown stops the HA socket, reconnect timers, snapshot/authentication work, and operation timers before exit while preserving the existing forced-shutdown bound.
- [ ] Add route-level Grid Dashboard Sonos proxy tests for success, structured upstream failure, connection failure, request-body forwarding, URL encoding, status, content type, freshness headers, and byte-for-byte binary artwork forwarding.
- [ ] Change and test the standalone Grid Dashboard development default from node port 5005 to Sonos API port 5006; root `just dev` and direct `cd ExpressServer && npm run dev` must target the same layer.

Acceptance criteria:

- [ ] Every retained route in node and Home Assistant modes matches the frozen Phase 0 status, media type, headers, success/error schema, and invalid-input contract; every exception names its explicit approval.
- [ ] Switching backend mode requires configuration only, not a rebuild.
- [ ] The built add-on reads `backend_mode` from `/data/options.json`; an old options file defaults to node, and Home Assistant mode receives the Supervisor token without storing it in options.
- [ ] `node` mode remains a tested rollback until retirement.
- [ ] `shadow` makes exactly one write to node and zero writes to Home Assistant for every action test.
- [ ] `home_assistant` makes zero requests to node.
- [ ] Missing `SUPERVISOR_TOKEN` fails Home Assistant mode clearly and does not fall back silently to node.
- [ ] Health tests cover missing token, authentication rejection, missing configured room, unavailable-room diagnostics, stale/unknown connection, and reconnect recovery.
- [ ] Shadow read/comparison failures do not alter the node response; every retained write route makes exactly one node write and zero HA writes in shadow, while HA mode performs zero node reads or writes.
- [ ] Token redaction and graceful shutdown with an in-flight operation pass at the integrated router/server boundary.
- [ ] Route-contract tests exercise every retained route through the real Express routers in both Sonos API and Grid Dashboard, including spaces, apostrophes, literal `+2`, other encoded room/favorite/preset names, unsupported methods, and invalid names.
- [ ] The Grid Dashboard proxy preserves the upstream status, body, content type, and freshness headers and converts connection failures to the frozen `502` shape.
- [ ] `just test sonos-api`, `just test grid-dashboard`, and root `just test` pass.

### Required regression-test matrix

The integration owner maintains this matrix in the migration validation record. Every row needs an automated test at the candidate commit; rows marked live also need rollout evidence.

| Contract at risk | Required automated regression | Additional live proof |
| --- | --- | --- |
| Legacy HTTP compatibility | Table-driven request through both Express routers for every retained method/path; assert encoded upstream path, status, content type, required headers, success body, and normalized failure body. | Observation logs show no unclassified legacy caller before route removal. |
| Room and input allowlists | Every valid room plus unknown, empty, case-changed, encoded, traversal-like, duplicate, and `maker_room` inputs; assert rejection occurs before an HA call. | Live registry matches the frozen eight-room map. |
| State projection | Golden node/HA pairs for playing, paused, stopped, unavailable, missing metadata, single group, multiple groups, all coordinators, and unstable non-coordinator order. | UI, HA, and Sonos app agree during pilot. |
| Home Assistant transport | Auth success/failure/timeout, subscription rejection, snapshot-event race, duplicate/out-of-order events, disconnect at each startup phase, reconnect backoff, resnapshot, and shutdown with fake time/network. | Controlled reconnect succeeds without a false singleton or unchecked room. |
| Fresh/stale/unknown | A quiet healthy connection beyond 30 seconds, ping/watchdog failure, and fake-clock assertions at 29,999/30,000 ms after transport loss; command rejection while disconnected or unavailable. | Panel visibly transitions stale to unknown and recovers. |
| Service mapping | Exact domain, service, target, and payload for playback, favorite, join, unjoin, volume, normalization, and each preset; zero calls on validation failure. | One low-risk example of each action family succeeds. |
| Topology serialization | Service/state response in either order, duplicate tap coalescing, join-all then manual mutation, two competing join-all requests, follower-target join-all as exactly one ordered unjoin plus one join, timeout with late success, late superseded events, partial availability, and terminal retention expiry; assert exact write counts. | High-risk pilot matrix restores its starting topology. |
| Volume and presets | Characterized relative/absolute/clamp cases, unequal volumes, `/same`, every retained convenience route, every preset step failure, and startup validation of preset/favorite names. | Volumes, coordinator, source, and `pauseOthers` match the captured baseline. |
| Artwork and credentials | Allowed raster image, absent image, SVG/non-image, declared/streamed oversize, redirect, absolute/protocol-relative/traversal URL, timeout, and error log; verify `nosniff` and scan every response/log fixture for synthetic bearer and signed-picture tokens. | Artwork works through direct port and ingress; captured requests expose no token. |
| Backend isolation | The same action matrix in `node`, `shadow`, and `home_assistant`; assert node/HA read and write counts, especially zero HA writes in shadow and zero node requests in HA mode. | Node receives no direct request during the whole-house HA window. |
| Dashboard presentation | Known, pending, stale, unknown, partial, failed, timed out, cancelled, and superseded fixtures; repeated taps and late responses; direct/ingress-relative links. | An actual iOS 12 panel loads without syntax errors and completes the pilot matrix. |
| Packaging and retirement | Add-on manifest/config assertions, clean container builds, add-on discovery, forbidden-reference scan, and clean-install test without node. | Port 5005 is closed and HA-backed controls remain healthy. |

### Phase 3: Automated end-to-end validation

Add a deterministic test harness before live backend switching.

Required scenarios:

- [ ] Initial eight singleton rooms.
- [ ] One eight-room group with each possible configured coordinator.
- [ ] Multiple simultaneous groups.
- [ ] Manual non-coordinator leave.
- [ ] Manual coordinator/active-room leave.
- [ ] Standalone leave.
- [ ] Join a room already in the destination group and self-join, using the frozen idempotent-or-rejected result with zero service writes.
- [ ] Join a singleton to a group.
- [ ] Move a room between two groups.
- [ ] Manual join with stale or unavailable source and stale or unavailable anchor; return the frozen `503` response with zero service writes.
- [ ] Join-all from a singleton and from a non-coordinator already in another group.
- [ ] Two fast join-all requests to different targets.
- [ ] Manual leave while join-all is in flight.
- [ ] One unavailable non-target and an unavailable target.
- [ ] WebSocket disconnect, stale window, unknown transition, and reconnect/resnapshot.
- [ ] Home Assistant service error and timeout without duplicate submission, including timeout followed by observed success and success followed by no confirming observation.
- [ ] Unequal volume group: relative, absolute, normalization, unchanged-member skipping, partial per-member failure, and clamps; parse `+2`, `-2`, `0`, `100`, out-of-range, decimal, and nonnumeric values according to the frozen contract.
- [ ] Each TV preset, configured favorite, play/pause, and next.
- [ ] Artwork success, missing art, non-image upstream response, oversized response, and HA failure.
- [ ] Direct-port and ingress-relative URL construction.
- [ ] Browser-facing `/sonos-intents/*` and internal `/intents/sonos/*` route compatibility, including terminal-status retention and expiry.
- [ ] Stale to unknown to fresh Dashboard presentation as one sequence, proving stale retains the last check/X and only unknown shows `?` and disables topology input.
- [x] Repository-static validators reject malformed room/preset/favorite definitions; runtime startup and health tests cover missing token, rejected authentication, partial initial snapshot, missing configured favorite/preset sources, and readiness recovery after Home Assistant source data is corrected.

Automated phase exit criteria:

- [ ] No test depends on room iteration order other than coordinator-first canonicalization.
- [ ] No test marks an intended group as observed before a state event/snapshot contains it.
- [ ] All duplicate-write assertions pass.
- [ ] Pre-existing intent, stale-cache/status-proxy, graceful-shutdown, Dashboard tap-arbitration, and ingress-relative URL regressions remain green until their owning code is deliberately retired or replaced by an approved equivalent.
- [ ] All packages and add-on container builds pass under root `just test`.
- [ ] The complete behavior matrix and remaining live-only checks are included in the integration handoff.

## Live rollout

Live validation is a dedicated workstream with explicit authority to operate speakers. Do not intermingle it with feature implementation. Before rollout, the validation record must define P0/P1 severity, the frozen shadow convergence grace, numeric latency/RSS budgets, unexpected-restart threshold, and the rollback triggers/RTO; no rollout gate may rely on undefined terms such as "persistent," "indefinite," or "material."

### Live-state restoration contract

Capture a private, just-in-time state immediately before each live mutation. If that capture differs from the frozen household state below because someone intentionally changed Sonos after the migration began, stop and record the newer state as the restoration target rather than overwriting it. Otherwise, a live test is not restored and its stage cannot pass until all of these conditions hold simultaneously:

- [ ] There is exactly one group, coordinated by Bathroom, whose member set is exactly Bathroom, Closet, Bedroom, Move, Kitchen, Living Room, Guest Bathroom, and Office. Non-coordinator response ordering is irrelevant.
- [ ] Every member volume is exactly 20 and every member has mute false.
- [ ] The Bathroom-coordinated group is playing, with no room left paused, stopped, buffering, or pending because of the test.
- [ ] The source is the Home Assistant favorite `735 - Steve Aoki's Remix Radio`, represented on the live stream as `CH 735 - Steve Aoki's Remix Radio`. Track title, artist, and album may change naturally, but the station may not.
- [ ] Home Assistant `group_members`, direct node `/zones` while node is retained, Sonos API `/sonos/zones` and room state, Grid Dashboard `/sonos/zones`, and the Sonos app agree on the restored topology and playback. Every pending operation is terminal.
- [ ] The validation record contains the pre-test capture time, restoration time, observed coordinator/member set, eight volume/mute pairs, playback state, station, verification surfaces, and any deviation from the frozen state.

### Stage 1: Baseline and shadow mode

- [ ] Record Git revision, HA version, installed add-on versions, current groups, playback source, per-room volumes, unavailable rooms, and relevant restart counts.
- [ ] Retain the current deployed packages/configuration for Grid Dashboard, Sonos API, and Node Sonos HTTP API.
- [ ] Deploy `sonos-api` in `shadow` mode while leaving the dashboard and node control path unchanged.
- [ ] Observe at least 24 hours including external Sonos-app changes, TV source changes, grouping, favorites, and idle periods.
- [ ] Compare topology as coordinator plus member set; compare volume within one percentage point; compare playback state exactly; compare metadata while ignoring elapsed-time/artwork URL differences and normalizing the node live-radio `TYPE`/`TITLE`/`ARTIST`/`ALBUM` title envelope into the equivalent Home Assistant fields.
- [ ] Classify every comparison. A transient mismatch must self-clear within the frozen shadow convergence grace; anything longer is persistent. Do not waive topology or coordinator differences as harmless.
- [ ] Confirm node port 5005 has no unexplained direct callers beyond the shadow/diagnostic path.

Shadow exit criteria:

- [ ] Zero persistent topology, coordinator, or playback mismatches; every transient mismatch self-clears within the frozen grace and is classified in the evidence log; every converged volume difference is at most one percentage point.
- [ ] State updates are event-driven, the liveness watchdog stays healthy during idle periods, and reconnection was observed or deliberately tested.
- [ ] Correlated action logs show exactly one node write and zero Home Assistant writes for every shadow action.
- [ ] There are zero unexpected add-on restarts, and measured p95 latency and peak RSS remain inside the numeric budgets frozen with the baseline.
- [ ] Rollback to the prior node configuration has been rehearsed without uninstalling anything.
- [ ] The full live-state restoration contract passes after the shadow action/reconnect exercises.

### Stage 2: Home Assistant backend pilot

Switch the single shared `sonos-api` instance to `home_assistant` mode during a controlled maintenance window while keeping the node add-on installed and available for rollback. This is a global backend switch for every panel; use one designated wall panel for the scripted matrix while other panels are idle, rather than implying per-panel backend routing.

Run this live matrix and restore the starting group/volume/playback state afterward:

- [ ] For each operation, record operation ID, accepted service-call count, start/end/duration, starting and final HA topology, UI result, Sonos-app result, and restoration result.
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
- [ ] The full live-state restoration contract passes: exact Bathroom-led member set, all eight volumes at 20, all eight mute values false, playing, and the Steve Aoki Remix Radio station through every verification surface.
- [ ] The pilot panel remains stable for at least 24 hours.

### Stage 3: Whole-house observation

- [ ] Keep the already-global HA backend enabled and return all panels to normal household use.
- [ ] Keep node installed but unused for a 48-hour observation window.
- [ ] Exercise normal household use rather than only scripted tests.
- [ ] Review action failures, topology timeouts, state age, reconnects, preset failures, artwork errors, and unexpected legacy-route calls.
- [ ] Verify no direct node requests occurred during the window.

Whole-house exit criteria:

- [ ] No unresolved P0/P1 Sonos behavior regression; every lower-severity regression is closed or explicitly accepted with severity, owner, impact, and expiry.
- [ ] No persistent topology divergence between UI, HA, and the Sonos app under the frozen grace.
- [ ] Zero operations remain pending at window end, and no operation exceeded the frozen deadline without a terminal result.
- [ ] Zero unexpected add-on restarts and zero node reads or writes occurred during the window.
- [ ] No unexpected node API consumers remain.
- [ ] The user explicitly accepts the HA-backed behavior before node uninstall.

## Node retirement

Retirement is a separate, reversible deployment before repository deletion.

### Runtime retirement

- [ ] Before any live backup, update and test `talos/src/talos/addon_backup.py` so SSH and SCP select `.ssh/id_ed25519_codex_smarthome`, set `IdentitiesOnly=yes`, retain `homeassistant.local`, and follow the root missing-key/authentication/hostname failure behavior without alternate credentials.
- [ ] Run `just addon-state-backup` and verify its manifest contains the installed node add-on and its `/data` preset/settings files. Export a separate `/config/node-sonos-http-api/` copy only if the live preflight finds that directory; the captured 2026-08-28 installation had no such `/config` state. Keep every private export out of Git.
- [ ] Remove `depends_on: node-sonos-http-api` from `sonos-api`, but retain dormant node-mode schema and the node base URL until node uninstall so configuration-only rollback still works.
- [ ] Deploy the independent HA-backed Sonos API and verify health.
- [ ] Stop the node add-on without uninstalling it.
- [ ] Run the high-risk subset: state, manual leave/join, join-all, group volume, one favorite, and one TV preset; record expected/observed topology and restore the starting state.
- [ ] Observe at least 24 hours starting only after node is confirmed stopped.
- [ ] Retain durable copies of both prior node and Sonos API installable tarballs outside ignored build output, with exact versions, checksums, reinstall commands, sanitized configuration-backup location, retention-until date, and a safe-environment installation rehearsal that meets the frozen RTO.
- [ ] Uninstall node only after the stopped observation and runtime-retirement exit criteria pass.
- [ ] Verify port 5005 is closed and Sonos operation continues.

Runtime-retirement exit criteria:

- [ ] Correlated logs for the stopped 24-hour window show zero port-5005 requests, zero unexpected restarts, no stale period exceeding the frozen limit while HA is healthy, and zero open operations at window end.
- [ ] The recorded high-risk matrix matches authoritative HA/UI/Sonos-app topology and confirms restoration of the starting state.
- [ ] The high-risk subset ends with the full live-state restoration contract satisfied, including the exact eight volume/mute pairs, playing state, and Steve Aoki station.
- [ ] The retained node and Sonos API tarballs, Supervisor backup, any conditionally required separate config export, versions/checksums, exact reinstall commands, durable location, and retention-until date are recorded; safe installation and rollback rehearsals met the frozen RTO.
- [ ] The user explicitly approves node uninstall after reviewing the evidence.

### Repository retirement

Delete and update only after runtime retirement passes:

- [ ] Remove `node-sonos-http-api/`, including patches, dependency overlay, presets, build files, and documentation.
- [ ] Remove node-specific Talos behavior from `talos/src/talos/dev.py`, `talos/src/talos/addon_backup.py`, `talos/src/talos/templates/run.sh.j2`, and the add-on builder/runner/manifest/backup/Justfile tests.
- [ ] Remove node add-on references from root `README.md` and `AGENTS.md`; Sonos, setup, development, hook, ingress, operations, version, and Talos documentation; dependency graphs; and deployment workflows.
- [ ] Update `docs/operations/addon-state-backups.md` and its tests for the post-retirement add-on count and restore order.
- [ ] Remove or regenerate the tracked `printer/report.txt` snapshot so it does not preserve stale node add-on inventory.
- [ ] Update `docs/sonos/overview.md` and `docs/sonos/routing-guide.md` to the HA-backed architecture.
- [ ] Reconcile `docs/plan-dashboard-upgrade.md` so it does not preserve superseded node-intent, stale-state, or pending-state guidance.
- [ ] Update `docs/operations/improvements.md` to mark the replacement complete and describe the remaining thin adapter.
- [ ] Update `sonos-api/AGENTS.md`, `Justfile`, `README.md`, `run.sh`, `addon.yaml`, package metadata, option translations, and health documentation.
- [ ] Update `grid-dashboard/addon.yaml` descriptions that still call the Sonos base URL the node API.
- [ ] Remove backend modes `node` and `shadow`, legacy node client code, old intent polling code, status proxy code made obsolete by the HA state store, and their dependencies/tests.
- [ ] Retain compatibility routes that are still used; route removal is independent of node removal.

Repository retirement acceptance criteria:

- [ ] `rg -i "node-sonos-http-api|node_sonos_http_api|local-node-sonos-http-api"` matches only an explicit reviewed allowlist of historical migration/changelog entries; stale generated reports and active code/config/docs have zero matches.
- [ ] Add-on discovery no longer lists the node add-on.
- [ ] `sonos-api` has `homeassistant_api: true`, no `host_network`, and no Sonos discovery dependency.
- [ ] Manifest, packaged-launcher, dependency, and container inspection confirms there is no node hostname/base URL, UPnP/SSDP library, multicast hook, upstream clone, or hidden direct-Sonos runtime path.
- [ ] Root `just test` passes, including all configured container builds.
- [ ] A clean install/deploy of Sonos API and Grid Dashboard works without node ever being installed.
- [ ] Root `just dev` and direct Dashboard development start without node, honor the documented non-committed Home Assistant development connection values, and no longer order or launch a node dependency.
- [ ] The working tree is clean and the migration is represented by reviewable commits.

## End-to-end acceptance criteria

The migration is complete only when all of the following are true.

### Functional

- [ ] All eight dashboard rooms show the same membership as Home Assistant and the Sonos app.
- [ ] Manual join and leave work for members, coordinators, standalone rooms, and rooms moving between groups.
- [ ] Join-all works from any configured room; unavailable target and non-target cases produce the frozen failure/partial result without misleading the known state.
- [ ] Play, pause, play/pause, next, configured favorites, group volume, normalization, every retained convenience route, and all three room TV presets pass live parity checks.
- [ ] Complete metadata/state compatibility and binary album art work through ingress and direct dashboard access.

### Reliability and presentation

- [ ] Known membership remains visible while a command is pending.
- [ ] Pending status is bounded and always resolves to success, partial, failed, timed out, cancelled, or superseded.
- [ ] No topology command is blindly retried after Home Assistant accepted it.
- [ ] Disconnect/reconnect and stale/unknown behavior pass automated and live checks.
- [ ] Health becomes non-ready for every frozen startup/connection failure and returns ready only after authenticated resnapshot recovery.
- [ ] Stale/unknown membership and media presentation never displays old data as current or permits a topology mutation.
- [ ] Duplicate taps and overlapping group operations do not make an older request the final state.

### Operations and security

- [ ] The Supervisor token and signed artwork token are server-side only and absent from logs/responses; artwork allowlist, MIME, redirect, `nosniff`, and size-limit checks pass.
- [ ] Invalid room, favorite, preset, volume, and path inputs make zero HA calls, and no generic HA service proxy is reachable.
- [ ] Sonos API health detects missing HA authentication, missing expected entities, and stale initial state.
- [ ] Port 5005 is closed and the node add-on is absent from the live host.
- [ ] Zero node traffic is observed during the final HA-backed window before uninstall.
- [ ] The prior node deployment remains recoverable until the concrete retention-until date recorded in the validation record.
- [ ] Documentation describes the actual deployed architecture and troubleshooting path.
- [ ] The last agent-initiated live mutation ends with the full live-state restoration contract satisfied and recorded.

### Repository quality

- [ ] Each parallel workstream has explicit ownership and handoff notes, and the immutable candidate commit records either scoped workstream commits or a documented single integration commit.
- [ ] Unit, integration, dashboard, root, and container tests pass.
- [ ] No live credentials, entity-picture tokens, IP addresses, or captured private media metadata were committed as fixtures.
- [ ] No obsolete runtime dependency or documentation claims that `sonos-api` requires node.

## Final merge-to-main gate

Do not merge the candidate into `main` merely because implementation tests pass. Merge is authorized only after every automated criterion and the uninterrupted 24-hour shadow, 24-hour Home Assistant pilot, 48-hour whole-house, and 24-hour stopped-node gates pass; the full live-state restoration contract passes after the last mutation; the user has explicitly accepted HA-backed behavior and separately approved node uninstall; repository retirement and its clean-install checks pass; and the validation record names the final candidate SHA, package digests, test commands, deployed versions, and observation timestamps.

The merge must preserve unrelated work already present in the primary `main` checkout:

- [ ] Record `git status --short` and a patch/hash inventory of every pre-existing modified, staged, and untracked main-worktree path before merging.
- [ ] Confirm the candidate commit range and the pre-existing main dirty-path set do not overlap. If they overlap or Git cannot merge without touching a dirty path, stop for user direction; do not stash, reset, restore, clean, or overwrite the user's work.
- [ ] Merge only committed candidate changes. The candidate worktree must be clean apart from documented ignored validation artifacts, and no private live capture may be staged.
- [ ] After the merge, confirm `main` contains the reviewed candidate commits, the pre-existing dirty-path patch/hash inventory is unchanged, and no unexpected file entered the commit history.
- [ ] Rerun the final proportionate repository checks on the merged tree without modifying the preserved user work, record the merge commit or fast-forward SHA, and update the validation record. A failed post-merge check blocks completion and must not be hidden by rewriting either worktree.

## Rollback

Before node uninstall, rollback is configuration-only. Run the following from the repository host using only the required repository-local identity and `homeassistant.local`; do not substitute an IP address or another credential. Capture the UTC start time, current topology, Sonos API/Grid/node versions, current options, resource stats, and the current Sonos API startup-log marker before the POST.

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
6. The full live-state restoration contract passes, there is no open operation or HA write in flight, and rollback finished within 10 minutes.
7. Revert Grid Dashboard only if its compatibility contract changed; otherwise keep it on the same routes. Record the trigger, failed operation, deployed versions, option POST result, planned restart evidence, health/zones/state/action results, restoration result, and RTO duration before any additional mutation.

After node is stopped but before uninstall, restart the retained node add-on and perform the same configuration rollback.

After uninstall, reinstall the retained prior node package/configuration, restore the prior Sonos API package/configuration, and verify health before issuing actions. Do not attempt a hurried partial reimplementation during an outage.

Immediate rollback triggers:

- Any credential or signed-artwork token exposure.
- Any UI membership that contradicts the latest authoritative topology.
- A duplicate write or late result that lets an older request overwrite a newer one.
- Missing or incorrect coordinator behavior in a TV preset.
- An add-on crash loop or loss of both direct and ingress panel control.

Threshold rollback triggers use the numeric counts/windows frozen in Phase 0: topology timeouts, subscription loss while Home Assistant itself is healthy, unexpected restarts, pending-deadline violations, error rate, p95 control latency, and memory growth. Reaching any threshold triggers rollback rather than an improvised live fix.

Use `docker inspect addon_local_sonos_api` fields `.RestartCount` and `.State.StartedAt` as the frozen restart/startup identity source. During every observation window, trigger the request-driven shadow comparison with `/sonos/zones` every 5 minutes and retain sanitized health, stats, restart identity, recent logs, and topology/state summaries in the private validation directory.

Rollback acceptance criteria:

- [ ] Rollback completes within the frozen RTO using the retained versioned package and configuration.
- [ ] Node mode `/health`, `/sonos/zones`, one room-state route, and one low-risk playback command pass.
- [ ] Dashboard, Home Assistant, and the Sonos app show the same topology after rollback, with no open operation or HA write still in flight.
- [ ] Deployed versions, trigger, failure evidence, rollback duration, verification results, and any restored live state are recorded in the validation record.

## Clean-context sub-agent handoff template

Every implementation assignment should include the following information so the agent does not need prior conversation history:

```text
Start from integration-base commit <exact SHA> in a clean branch/worktree.
Read the repository-root AGENTS.md and <owned add-on>/AGENTS.md completely.
Implement only workstream <ID and title> from docs/plan-replace-sonos-node-api.md.
Owned files: <exact list>. Do not edit frozen contracts or another workstream's files.
Do not deploy or operate the live Sonos system unless this assignment explicitly says live validation.
Use repository just recipes and run <scoped test command>.
Commit the scoped result with a descriptive message.
In the handoff report include: commit SHA, files changed, tests run/results, assumptions,
contract gaps, and any live validation still required.
```

The integration owner must receive every workstream's commit SHA and handoff report. A branch is not ready to merge merely because its local unit tests pass; it must also respect the frozen contract, owned-file boundary, security rules, and acceptance criteria above.
