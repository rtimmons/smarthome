# Home Assistant Sonos migration validation

This record is the evidence log for `docs/plan-replace-sonos-node-api.md`. It contains no Home Assistant token, signed artwork URL, speaker UUID, IP address, or private configuration payload.

## Candidate and baseline

| Item | Value |
| --- | --- |
| Baseline Git revision | `36882c3` |
| Candidate branch | `codex/docs-sonos-replacement-plan` (merged to `master` as `598e76b`) |
| Runtime candidate revision | `915730d0ccfb6e90b4ed842a21a6dc3f45985bab` (`Specify Sonos source compatibility across backends`). |
| Validation evidence revision | This evidence update is documentation-only; runtime/package inputs remain at the candidate revision above. |
| Home Assistant Core | 2026.8.3 |
| Baseline Sonos API add-on | 1.0.0, node backend via `http://local-node-sonos-http-api:5005` |
| Baseline Node Sonos HTTP API add-on | 1.0.2 |
| Prepared Sonos API / Grid Dashboard source version | 1.1.1 / 1.1.1 |
| Currently deployed Sonos API / Grid Dashboard | 1.1.1 / 1.1.1, deployed from the merged candidate; Sonos API backend is explicitly `home_assistant` |
| Deployed MongoDB metadata package | 0.0.1; metadata-only version activation explicitly approved on 2026-08-28 |
| Home Assistant Supervisor | 2026.08.0, healthy and supported |
| Baseline capture | 2026-08-28, before deployment or speaker mutation |

### Restorable live state

- Topology: one eight-room group coordinated by Bathroom.
- Members: Bathroom, Closet, Bedroom, Move, Kitchen, Living Room, Guest Bathroom, and Office.
- Volume: 20 on every member; mute false.
- Playback: playing.
- Source/station: `CH 735 - Steve Aoki's Remix Radio` (`735 - Steve Aoki's Remix Radio` in the Home Assistant source list).
- The Home Assistant `group_members` set and node `/zones` member set matched at capture. Home Assistant identified Bathroom as the first member/coordinator.
- Node returned Bathroom as coordinator but did not place it first in the member array, confirming that non-coordinator/member ordering is not a compatibility invariant.
- The node and HA representations differ materially for live-radio title, album, and elapsed time; candidate comparison must use the frozen, documented projection rather than treating these as small drift.
- All active Dashboard favorites were present in every room's Home Assistant `source_list`.
- Every room also advertised the physical `Line-in` and `TV` inputs; no `Apple Music` provider source name was present.

### Full restoration acceptance

The old diagnostic pause/play restoration is useful history but does not satisfy the immutable candidate. After every final-candidate live mutation, all rows below must be re-observed at the same restoration checkpoint. If a private just-in-time capture shows that a person intentionally changed the household state before the test, the test must stop and the newer target must be recorded before any restore command is sent.

| Field | Required restored observation | Final immutable evidence |
| --- | --- | --- |
| Group count and coordinator | Exactly one group, Bathroom coordinator | Pass at 2026-08-29T04:59Z via Home Assistant `group_members`, Sonos API, and Grid zones |
| Member set | Bathroom, Closet, Bedroom, Move, Kitchen, Living Room, Guest Bathroom, Office; non-coordinator order ignored | Pass at 2026-08-29T04:59Z via Home Assistant and Sonos API |
| Volumes | All eight rooms exactly 20 | Pass at 2026-08-29T04:59Z via Home Assistant state and Sonos API |
| Mute | All eight rooms false | Pass at 2026-08-29T04:59Z via Home Assistant state and Sonos API |
| Playback | Bathroom-coordinated group playing; no test-caused paused/stopped/buffering room and no pending operation | Pass at 2026-08-29T04:59Z via Home Assistant state and Sonos API |
| Station | HA source `735 - Steve Aoki's Remix Radio`; live channel `CH 735 - Steve Aoki's Remix Radio` | Pass at 2026-08-29T04:59Z via Home Assistant state, Sonos API, and Grid state |
| Agreement surfaces | HA `group_members`, Sonos API and Grid zones/state, and Sonos app agree | API surfaces pass at 04:59Z; Sonos-app visual confirmation remains pending because no local Sonos app is available |

Changing track title, artist, or album on the live station is expected and is not a restoration failure. Changing the station is a failure.

### Characterized compatibility behavior

- Pinned node group-volume logic adds a positive delta to each member when raising volume; lowering volume scales members proportionally using `ceil(member / oldGroupVolume * desiredGroupVolume)`; values below 1 set every member to 0.
- The active private preset inventory contains the three repository TV presets plus an `example` preset containing out-of-allowlist `TV Room`. The candidate must reject/deprecate `example`; it must not migrate that target.
- Active node preset data is under add-on `/data`, so a verified Supervisor add-on-state backup is required before node uninstall.

### Source-family research (2026-08-29)

The live inventory and source review confirm that Home Assistant source values
are not interchangeable with node API inputs:

- The restored SiriusXM station reports `media_content_type: music`, an
  `x-sonosapi-hls:` media ID, the current song in `media_title`/`media_artist`,
  the station in `media_channel`, and no provider-valued `source`. The node
  projection classifies the same URI as `radio` and keeps the station in
  `stationName`.
- Apple Music is not present as a physical `source_list` entry. Home Assistant
  uses `media_player.play_media` (share link or favorite item ID), while the
  node API's `/applemusic/{now,next,queue}` actions construct service-specific
  track/container URIs and queue behavior. No Apple Music-specific route is
  silently mapped to `select_source` in the candidate.
- TV/SPDIF and line-in are physical, model-dependent inputs. Home Assistant
  accepts exact `TV` or `Line-in` source names and generates dynamic stream
  URIs; legacy presets/actions persisted raw UUID-bearing
  `x-sonos-htastream`/`x-rincon-stream` values. Candidate presets contain only
  `TV`, and dynamic stream UUIDs are not compared literally.
- Metadata/artwork/transport are coordinator-owned in grouped state; volume
  and mute remain requested-member-owned for every source family.

The normative matrix is [Sonos source compatibility](source-compatibility.md).
Automated source projection and exact source-selection regressions were added
in the candidate tree; they must be rerun at the final immutable commit before
any observation clock starts. Live Apple Music, TV, and line-in checks remain
pilot-only and must restore the captured station/group/volume state.

### Retained route inventory, callers, and disposition

This is the frozen two-layer inventory. Except where a row says otherwise, the Grid Dashboard route is forwarded to the same method/path on Sonos API. JSON responses use `application/json`; validation, availability, and backend failures use the normalized `{error, code, retryable?}` shape with the row's `4xx`, `502`, or `503` status, and Grid preserves that upstream status/body/content type. Read responses carry `X-Sonos-Response-Source`, `X-Sonos-Response-Stale`, `X-Sonos-Observed-At`, and `X-Sonos-Age-Ms`. Artwork additionally carries `X-Content-Type-Options: nosniff`. Every Home Assistant-backed write requires a `live` snapshot; stale or unknown writes return normalized `503` with zero Home Assistant service calls, including at disconnect age zero.

Named route evidence used below:

- **HA success matrix:** `every retained HA route has a frozen success response contract` in `sonos-api/src/server/home-assistant-sonos-runtime.spec.ts`.
- **HA failure matrix:** `every parameterized HA route family has a normalized failure contract` and `real HA router preserves read, encoded action, validation, and binary artwork contracts` in the same suite.
- **HA policy matrix:** `topology, preset, status, and retained convenience policies are explicit` and `zones fail closed when any configured room has unknown topology` in the same suite.
- **Grid contract matrix:** `preserves the complete retained success and non-2xx contract matrix` and `passes deprecated roots through for normalized 410 responses with zero writes` in `grid-dashboard/ExpressServer/src/server/sonos.spec.ts`.
- **Grid alias matrix:** `maps registered browser intent routes to the internal aliases` in `grid-dashboard/ExpressServer/src/server/sonos.spec.ts`.
- **Backend isolation matrices:** `shadow mode routes every retained mutating action only to node`, `node and HA modes route the same retained action matrix to exactly one backend`, `node and HA modes route every retained read family to exactly one backend`, and `shadow comparison failure cannot alter the real node response` in `sonos-api/src/server/sonos-service.spec.ts`.

| Browser method/path | Sonos API method/path | Repository caller classification | Frozen HA-mode success contract | Failure/disposition | Named automated evidence | Remaining live/approval evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `GET /sonos/zones` | `GET /sonos/zones` | Active: Dashboard topology polling and membership controls | `200`; full legacy zone array, coordinator first and other members sorted; freshness headers | `503 topology_incomplete` rather than empty/partial/synthetic topology; retained | HA success/failure/policy, Grid contract, backend read isolation | Live HA/node/UI/Sonos-app parity pending |
| `GET /sonos/:room/state` | Same | Active: Dashboard room-state polling | `200`; complete legacy state object with requested-member volume/mute and coordinator transport/metadata/artwork; freshness headers | `404 unknown_room`; unavailable/unknown projection fails with normalized `503`; retained | HA success/failure, Grid contract, complete golden projection in `home-assistant-sonos-state.spec.ts` | Every-room live parity pending |
| `GET /sonos/:room/artwork` | Same | Active: URL returned by room-state and rendered by Dashboard | `200`; exact allowlisted raster bytes and MIME, freshness headers, `nosniff` | `404` missing/invalid room or art; normalized `502` for safe upstream failure; active content, redirects, unsafe URLs, and oversize bodies rejected; retained | HA success/failure, Grid contract, `sonos-artwork.spec.ts`, `http.spec.ts` | Direct-port and ingress panel proof pending |
| `GET /sonos/:room/play` | Same | Retained compatibility; no active first-party browser action found | `200 {status:"success"}`; requested member receives `media_play` | `404` invalid room; `503` non-live/unavailable; `502` backend failure; retained pending external-caller observation | HA success/failure, Grid contract, action and backend isolation matrices | External-caller audit and live parity pending |
| `GET /sonos/:room/pause` | Same | Active: `Music.Pause` | `200 {status:"success"}`; requested member receives `media_pause` | Same normalized write failures; retained | HA success/failure, Grid contract, action and backend isolation matrices | Live parity pending |
| `GET /sonos/:room/playpause` | Same | Active: `Music.PlayPause` | `200 {status:"success"}`; requested member receives `media_play_pause` | Same normalized write failures; retained | HA success/failure, Grid contract, action and backend isolation matrices | Live parity pending |
| `GET /sonos/:room/next` | Same | Active: `Music.Next` | `200 {status:"success"}`; requested member receives `media_next_track` | Same normalized write failures; retained | HA success/failure, Grid contract, action and backend isolation matrices | Live parity pending |
| `GET /sonos/:room/favorite/:name` | Same | Active: configured `Music.Favorite` controls | `200 {status:"success"}` after allowlist and live `source_list` validation; requested member receives `select_source` | `404 unknown_room` or `unknown_favorite`; `503` non-live/unavailable/source mismatch; zero calls on rejection; retained | HA success/failure, Grid contract, `home-assistant-sonos-actions.spec.ts`, backend isolation | Each configured favorite live parity pending |
| `GET /sonos/:room/join/:target` | Same | Active: room membership toggle | `202 {operation}`; destination resolves to its observed coordinator | `404` invalid room/target; `503` non-live/unavailable/invalid topology; terminal failure visible in status; retained | HA success/failure/policy, Grid contract, `home-assistant-sonos-actions.spec.ts`, `sonos-operation-queue.spec.ts` | Structured live join matrix pending |
| `GET /sonos/:room/leave` | Same | Active: room membership toggle | `202 {operation}`; standalone leave is idempotent with zero writes | `404` invalid room; `503` non-live/unavailable; terminal failure visible; retained | HA success/failure/policy, Grid contract, action/queue suites | Structured live leave matrix pending |
| `GET /sonos/:room/groupVolume/:value` | Same | Active: `Music.VolumeUp`, `Music.VolumeDown`, and `Music.SetVolume` | `200 {status:"success"}`; frozen relative/absolute group policy and clamping, per member | `400 invalid_volume`; `404` invalid room; `503` non-live/unavailable; partial failures are explicit; retained | HA success/failure, Grid contract, action and backend isolation matrices | Live unequal-volume parity pending |
| `GET /sonos/:room/volume/:value` | Same | Retained compatibility; active Dashboard uses `groupVolume`, not this route | `200 {status:"success"}`; requested member receives `volume_set` | `400 invalid_volume`; `404` invalid room; `503` non-live/unavailable; retained pending external-caller observation | HA success/failure, Grid contract, action and backend isolation matrices | External-caller audit and live parity pending |
| `GET /same/:room` | Same | Active: `Music.VolumeSame` | `200 {status:"success"}`; normalize observed group to requested member's volume and skip unchanged members | `404` invalid room; `503` non-live/unavailable; partial member failures explicit; retained | HA success/failure, Grid contract, action and backend isolation matrices | Live parity pending |
| `GET /sonos/:room/preset/:name` | Same | Active: three room TV preset controls | `202 {operation}`; allowlisted repository preset | `404 unknown_preset/room`; `503` non-live/unavailable/source mismatch; failed step and observed topology retained in terminal status; retained | HA success/failure/policy, Grid contract, `home-assistant-sonos-presets.spec.ts`, runtime preset tests | All three live preset matrices pending |
| `POST /sonos-intents/group-all` | `POST /intents/sonos/group-all`; direct Sonos API alias `/sonos-intents/group-all` is also retained | Active: Dashboard group-all | `202 {intent}`; zero writes if satisfied, normally one join, or exactly one ordered unjoin plus one join when requested target begins as a follower | `400 invalid_request` for missing/empty/duplicate/mismatched list; `404` invalid room; `503` non-live/unavailable target; retained | HA success/failure/policy, Grid contract/alias, action/queue suites | Live singleton/follower/double-tap matrix pending |
| `GET /sonos-intents/status` | `GET /intents/sonos/status`; direct Sonos API alias `/sonos-intents/status` is also retained | Active: Dashboard operation polling | `200 {activeIntent, recentIntent, serverTime}` with frozen lifecycle and retention | Normalized `502` connection/backend failure at Grid boundary; retained | HA success/policy, Grid contract/alias, `intents.spec.ts`, `status-proxy.spec.ts`, queue suite | Live operation correlation pending |
| `GET /up` | `GET /up` | Retained convenience; no active first-party browser caller found | `200 {status:"success"}`; frozen current-group volume-up policy | Normalized write failures including `503` when not live; retained pending external-caller observation | HA success/policy, Grid contract, action/backend isolation | External-caller audit, approval if behavior changes, and live parity pending |
| `GET /down` | `GET /down` | Retained convenience; no active first-party browser caller found | `200 {status:"success"}`; frozen current-group volume-down policy | Normalized write failures including `503` when not live; retained pending external-caller observation | HA success/policy, Grid contract, action/backend isolation | External-caller audit, approval if behavior changes, and live parity pending |
| `GET /pause`, `/play`, `/tv`, `/07`, `/quiet` | Same five paths | No active first-party browser caller found; external callers remain unknown until observation | In HA mode: `410 {error, code:"deprecated_route"}` and zero writes. Node/shadow remain exact pass-through for rollback | Proposed HA-only deprecation; not accepted yet | HA success/policy and Grid deprecated-route matrix | Explicit user approval and external-caller observation pending; blocks Phase 0 |

No route in the table is authorized for removal. “No active first-party browser caller found” is not proof that an external caller does not exist; those rows remain retained and their external disposition remains pending until the new immutable shadow observation is complete.

### Frozen operational limits and rollout policy

| Limit or policy | Frozen value |
| --- | --- |
| WebSocket liveness | HA protocol traffic must be observed within 45 seconds; a missed watchdog deadline marks the transport disconnected. |
| Stale/unknown boundary | Stale begins on transport loss; it remains stale through 29,999 ms and becomes unknown at 30,000 ms. |
| Topology operation deadline | 45 seconds from acceptance to terminal status. |
| Dashboard pending deadline | 50 seconds, with an earlier release on a correlated terminal operation status. |
| Terminal-status retention | 5 minutes after terminal completion. |
| REST/service request timeout | 10 seconds per request; an accepted topology mutation is never automatically resubmitted. |
| WebSocket reconnect | 0.5, 1, 2, 4, 8, then 10 seconds maximum between attempts. |
| Shadow convergence grace | 5 seconds after either backend's observation before a mismatch is persistent. |
| Artwork limit | 5 MiB declared and streamed; JPEG, PNG, GIF, and WebP only. |
| Elapsed comparison policy | Excluded from shadow equality for all media because node and Home Assistant advance elapsed position from independent clocks. Elapsed projection correctness remains covered independently; it is never used to classify a shadow mismatch. |
| Rollback RTO | 10 minutes from trigger to verified node-mode health. |
| Rollback artifact retention | 30 days after node uninstall, with a concrete retention-until date recorded at uninstall. |
| P0 | Credential exposure, unsafe artwork proxying, destructive/wrong-room control, irrecoverable topology, or loss of both dashboard paths; immediate rollback. |
| P1 | Persistent topology/coordinator contradiction, duplicate topology writes, crash loop, or a control path unavailable for more than 5 minutes; immediate rollback. |
| Shadow/pilot latency budget | Read p95 no more than 250 ms above baseline; accepted action p95 no more than 1,000 ms above baseline, excluding physical topology convergence. |
| Memory/restart budget | Sonos API peak RSS no more than 192 MiB and no more than 20% above baseline; zero unexpected restarts per observation stage. |
| Topology-timeout rollback trigger | One accepted topology operation reaching its 45-second deadline in any rolling 15-minute window. |
| Subscription-loss rollback trigger | Any loss lasting 30 seconds while HA is healthy, or more than one loss in any rolling 15-minute window. |
| Pending-deadline rollback trigger | Any Dashboard operation remaining pending for 50 seconds. |
| Control-error rollback trigger | Two consecutive control failures, or more than 5% failures after at least 20 controls in a rolling 15-minute window. |
| Restart rollback trigger | One unexpected Sonos API restart during any observation stage. |
| Restart/startup evidence source | `docker inspect addon_local_sonos_api` fields `.RestartCount` and `.State.StartedAt`, captured immediately before and after each planned restart and at every observation sample. A changed value without a recorded planned restart is unexpected. |
| Shadow evidence cadence | Every 5 minutes, request Sonos API `/sonos/zones` to trigger comparison, then retain sanitized `/health`, app stats, Docker restart/start time, recent Sonos API logs, and topology/state summaries in the private validation directory. |

The invalidated pre-commit diagnostic sample recorded node-mode HTTP p95 19.359 ms across 7,269 requests and shadow-mode HTTP p95 7.879 ms across 2,716 requests. Shadow RSS was 31.5 MiB. A corrected-deployment node-mode RSS sample and action-latency baseline are still required before the observation clock starts; these diagnostic values cannot satisfy the immutable-candidate gate.

### Temporary rollback artifacts

These copies cover the active validation session. Runtime retirement requires moving verified copies to a durable retained location and recording exact reinstall commands before node uninstall.

| Artifact | SHA-256 |
| --- | --- |
| `/private/tmp/sonos_api-baseline-36882c3.tar.gz` | `8c880be6a96c2427d503e7977a4a9f29d2bb6af06c6124c38facd49ea46102af` |
| `/private/tmp/node_sonos_http_api-baseline-36882c3.tar.gz` | `032625bee1dcfaa351be821be671eebd5d663c2e486c015e8637af9470b939f4` |
| `/private/tmp/grid_dashboard-baseline-36882c3.tar.gz` | `ee572531826cca2f0a725b2eb9a54c660d7da1d3a865ab05c1a14615c275f7ce` |

## Automated validation

Only a command run from the clean, committed runtime candidate revision can close a candidate test gate. A later evidence-only documentation commit records those results without changing runtime, package, manifest, lockfile, or test inputs. Results below from the dirty 1.1.0 build remain recorded for diagnosis, but are explicitly superseded and must be rerun after the final 1.1.1 runtime commit. The baseline reproduction and verified live backup are historical prerequisites rather than proof of the final candidate.

| Gate | Result | Evidence |
| --- | --- | --- |
| Baseline live read | Pass | Node `/zones` and Home Assistant entity state matched the restorable state above. |
| Talos fast suite before implementation | Pass | 97 passed, 11 deselected. |
| Initial root `just test` | Environment stop | The clean worktree initially lacked JavaScript dependencies; `vitest` was not installed. Dependencies were then installed with the pinned lockfiles. |
| Clean `36882c3` baseline reproduction | Characterized pre-existing failure | A detached worktree was bootstrapped with `just setup`, then generated HA artifacts before rerunning root `just test`. Talos passed 97 tests (11 deselected), Grid Dashboard passed 36 tests plus TypeScript, and node dependency validation passed. The root command then stopped on the pre-existing Ruff formatting drift in `printer/docs/testing.md`; the candidate contains only Ruff's mechanical rewrite and its later root run passes. A separate baseline `just test sonos-api` passed the three enumerated legacy suites, TypeScript build, and container build. |
| Final candidate `just test sonos-api` | Pass | `just test sonos-api` at `915730d`: discovery runner, all Sonos suites, TypeScript build, and container build passed. |
| Final candidate `just test grid-dashboard` | Pass | Included in root `just test` at `915730d`: 14 files / 76 tests and TypeScript check passed. |
| Final candidate root `just test` | Pass | `just test` at `915730d`: Talos 116 passed (11 deselected), Grid 76 passed, Printer 198 passed (1 warning), Snapshot 7 passed, Sonos suites/build/container passed, TinyURL 16 passed/build, node validation, and all seven container builds passed. |
| Final package provenance | Pending | Record exact candidate SHA, source versions, installed versions, and SHA-256 digests for the uploaded Sonos API, Grid, and retained node packages. |
| Backup identity and add-on builder tests | Superseded; rerun pending | A pre-commit run passed 35 tests after adding repository-identity enforcement. Rerun and record exact counts at the final candidate SHA. |
| Repository unit/integration/root/container gate | Superseded; rerun pending | A pre-commit root `just test` passed Talos, Grid Dashboard, Sonos, Printer, Snapshot, TinyURL, node validation, and all seven package/container builds. Exact counts varied as acceptance fixes landed; only the final clean immutable run will be authoritative. |
| Separate-worktree SSH transport | Superseded; rerun pending | Pre-commit focused tests passed for common-worktree identity resolution and `IdentitiesOnly=yes`. Final candidate evidence is pending. |
| Shadow persistence/write isolation | Superseded; rerun pending | Pre-commit fake-clock and route tests covered the 5-second grace and one-node/zero-HA shadow writes. Final candidate evidence is pending. |
| Node-mode deployment | Pass (candidate deployment) | `just deploy` completed all seven add-ons on 2026-08-29; Supervisor metadata refresh and app inspection report Sonos API/Grid 1.1.1 with `update_available:false`. |
| Node-mode post-deploy parity | Pass (checkpoint; observation gates pending) | At 04:40Z direct node and deployed Sonos API matched on Bathroom state: `radio`, Steve Aoki channel, `PLAYING`, same HLS URI, volume 20, mute false; all eight members were restored. |
| MongoDB metadata activation | Pass | With explicit approval, MongoDB was versioned as 0.0.1, deployed, reloaded, and restarted. MongoDB, Printer, and TinyURL returned healthy before backup. The Supervisor app-info response still omits the `backup` field, so the backup preflight verifies the exact deployed `backup: cold` manifest when that API field is absent. |
| Supervisor add-on-state backup | Pass | Backup `1f8546aa` was created at 2026-08-29T02:52:54Z and downloaded to the ignored, mode-0700 validation directory. The compressed 1,383,516,160-byte archive has SHA-256 `a97b1117e03ab41487faabb6e8da959b24634d1cd73f6aff76457efd78e3a94a`, contains all seven local add-ons plus `share`, excludes Core, and passed nested node-state checks for `presets.json`, preset contents, and `settings.json`. The failed uncompressed attempt `f759d7a4` was removed before the successful run. |

### Automated behavior traceability

“Automated complete” below means the named regression exists and passed in the pre-commit integration runs. It does not close the immutable-candidate gate: every named suite must run again from the clean runtime candidate SHA, and live rows remain pending regardless of automated coverage.

| Contract or plan gate | Named automated evidence | Automated status | Evidence still required |
| --- | --- | --- | --- |
| Test discovery and zero-suite failure | Discovery runner in `sonos-api/scripts/run-tests.cjs`; route suite `home-assistant-sonos-runtime.spec.ts` is reported by `just test sonos-api` | Automated complete | Final clean-SHA command, discovered path list, counts, TypeScript, and container result pending |
| REST/WebSocket authentication, timeout, subscription, liveness, redaction, and cancellation | `home-assistant-client.spec.ts` | Automated complete | Final clean-SHA rerun and controlled live reconnect pending |
| Gap-free initial snapshot/reconnect, duplicate/out-of-order events, disconnect during resnapshot, exact backoff/reset, stale/unknown boundary, and shutdown timers | `home-assistant-state-store.spec.ts`, including delays `500, 1000, 2000, 4000, 8000, 10000, 10000` and reset after an authenticated resnapshot | Automated complete | Final clean-SHA rerun and controlled live reconnect pending |
| Complete state projection, requested-member/coordinator ownership, all coordinators, multi-group/singleton shapes, malformed topology, and freshness headers | `home-assistant-sonos-state.spec.ts`; `zones and room-state headers and bodies each derive from one immutable snapshot`; `zones fail closed when any configured room has unknown topology` | Automated complete | Final clean-SHA rerun and live eight-room/UI/Sonos-app comparison pending |
| Artwork bytes, coordinator ownership, revision stability/change, URL allowlist, MIME, redirect, size boundaries, `nosniff`, and credential isolation | `sonos-artwork.spec.ts`; `artwork revision follows coordinator media identity, not volume or signed URL churn`; Grid `requestBinary` and Sonos proxy suites | Automated complete | Final clean-SHA rerun plus direct-port and ingress live proof pending |
| Every write requires live state and exact disconnect-age-zero rejection | `home-assistant-sonos-actions.spec.ts` assertion `playback, favorite, volume, and topology writes all fail closed at disconnect age zero`; runtime failure matrix | Automated complete | Final clean-SHA rerun pending |
| Playback/favorite/volume/group service mappings, validation, complete room allowlist, and group-volume input/clamp matrix | `home-assistant-sonos-actions.spec.ts`; `real HA router preserves read, encoded action, validation, and binary artwork contracts`; `real HA router preserves the frozen group-volume input and clamp matrix`; `real HA router accepts exactly the configured room allowlist` | Automated complete | Final clean-SHA rerun and live parity pending |
| Topology serialization, coalescing/supersession, follower-target unjoin-then-join, partial availability, observation ordering, no resubmission, and operation boundaries | `home-assistant-sonos-actions.spec.ts`; `sonos-operation-queue.spec.ts`, including 44,999/45,000 ms; `status exposes the newest queued intent over its superseded active predecessor` | Automated complete | Final clean-SHA rerun and structured live operation matrix pending |
| Preset structure, ordering, failures, supersession, convergence, and source readiness | `home-assistant-sonos-presets.spec.ts`; runtime tests `preset completes only after authoritative coordinator, members, source, and volumes converge`, `preset failure status exposes the failed step and sanitized observed topology`, `pauseOthers preset waits for every non-member to be authoritatively paused`, `superseding a preset during a service call prevents every later preset write`, and `preset convergence consumes the operation acceptance deadline and times out` | Automated complete | Final clean-SHA rerun, all three live preset checks, and explicit deprecated-route approval pending |
| Two-layer route success/error contracts and intent aliases | HA success/failure/policy matrices and Grid contract/alias matrices named in the route inventory above | Automated complete for retained route families represented in the inventory | Final clean-SHA rerun; external-caller observation and five deprecated-route approvals pending |
| Node/shadow/HA read and write backend isolation; comparison failures preserve node responses | Four backend-isolation matrices named in the route inventory; `shadow mismatch logging waits for the full grace interval and resets on convergence`; `shadow observer comparison failure cannot alter the real node response` | Automated complete | Final clean-SHA rerun and correlated live node-write/zero-HA-write evidence pending |
| Shadow semantic comparison excludes ordering, elapsed time for every medium, and artwork URL while retaining topology/playback/volume/metadata signal | `sonos-shadow-compare.spec.ts` and shadow grace tests in `sonos-service.spec.ts` | Automated complete | Final clean-SHA rerun and new uninterrupted shadow evidence pending |
| Source-family inputs and projection (SiriusXM/radio, Apple Music track/container URIs, TV/SPDIF, line-in, exact favorites, coordinator/member ownership) | `home-assistant-sonos-state.spec.ts` source projection matrix and `home-assistant-sonos-actions.spec.ts` exact source-selection matrix | Pass at `915730d` | Live Apple Music, TV, and line-in observations are required in the HA pilot when available; restore the frozen station/group state |
| Dashboard authoritative membership, pending lifecycle, stale/unknown/fresh recovery, metadata/art clearing, request generations, and ingress URLs | `app.spec.ts`, `gridview.spec.ts` (`recovers stale then unknown presentation when fresh memberships arrive`), `listeners.spec.ts`, `music-controller.spec.ts`, and `sonos-operation-state.spec.ts` | Automated complete | Final clean-SHA rerun and actual-panel pilot pending |
| Safari 12 directly served first-party syntax | `checks every directly served first-party Grid Dashboard script` in `safari12-compat.spec.ts` | Automated complete | Final clean-SHA rerun and actual iOS 12 panel proof pending |
| Add-on options/default mode, launcher/package/container, repository identity transport, and backup manifest | `config.spec.ts`, relevant Talos add-on/launcher/backup/worktree tests, and pre-commit root/container run | Automated complete only for the current pre-commit tree | Final immutable root/container/transport reruns, package digests, and later retirement/clean-install evidence pending |

## Acceptance traceability

An unchecked plan criterion remains a blocker. A green root command alone does not advance a phase.

| Gate | Status | Current evidence | Remaining blocker |
| --- | --- | --- | --- |
| Phase 0 contract freeze | In progress | Room map, backend modes, numeric protocol/operation/artwork limits, baseline topology/volume/preset inventory, discovery-based test runner, sanitized fixtures, complete retained-route/caller/disposition inventory, and named automated traceability are recorded. | Immutable candidate SHA/package digests, final clean-SHA reruns, external-caller observation, and explicit approval for the five HA-only deprecated responses. |
| HA transport and state lifecycle | In progress | Pre-commit authenticated REST/WebSocket, stale/unknown, reconnect, snapshot/event race, deadline, and shutdown tests exist. | Commit the immutable candidate and rerun the final full suite at that SHA. |
| State, artwork, and Dashboard presentation | In progress | Pre-commit coordinator-owned artwork, binary/size/security, stale/unknown/pending, operation correlation, alternating-generation, ingress-relative, and Safari regressions exist. | Tie the complete two-layer route matrix and final rerun to the immutable candidate SHA. |
| Actions, topology, volume, and presets | In progress | Pre-commit exact service mappings, no duplicate topology writes, group-volume parity, `/same` skipping/partial failure, preset ordering/supersession/convergence, and terminal operation tests exist. | Tie complete Phase 3 scenario traceability to the immutable SHA, then collect structured live operation evidence. |
| Packaging, repository, and backup | In progress | The verified private Supervisor backup remains valid; pre-commit package, root, and worktree-transport results are superseded. | Clean immutable candidate root/container/transport reruns, package digests, and later retirement/clean-install gates. |
| Live shadow | Diagnostic only | Shadow health, latency sample, RSS ceiling, metadata/playback discoveries, and a restored pause/play check are recorded. | Corrected immutable redeploy, measured node RSS baseline, rollback/reconnect/caller exercises, and a new uninterrupted 24-hour window. |
| HA pilot / whole-house / stopped-node | Pending | None; no HA-backed speaker write has occurred. | Prior gates and the required 24/24/48/24-hour windows. |

## Live rollout evidence

The merged 1.1.1 candidate is deployed and the live Sonos API is explicitly configured in `home_assistant` mode. The node add-on remains installed for rollback, but it was not used for the final restoration writes. The required long observation windows are still pending, so this evidence does not claim migration completion.

| Stage | Status | Evidence |
| --- | --- | --- |
| Shadow comparison | Diagnostic; restart required | Shadow began at 2026-08-29T02:59:39Z. Health is ready with node and HA both ready, all eight rooms present, and no unavailable rooms or missing favorite/preset sources. The first live comparison exposed the characterized structured live-radio metadata envelope and that node reports paused live radio as `STOPPED` while HA reports `paused`. Semantic metadata normalization and media-aware playback projection now have regressions, but this dirty-build window is invalid; redeploying an immutable candidate starts a new 24-hour clock. |
| Configuration rollback rehearsal | Pending | Must use the exact Supervisor options POST and separate restart in the plan, prove a new node-backend startup marker, parse ready/node health, verify node/API/Grid/state/action parity, satisfy full restoration, and finish within 10 minutes. |
| Home Assistant pilot matrix | Pending |  |
| Starting-state restoration | Pass (final-candidate checkpoint) | The 1.1.1 HA-backed deployment restored the original eight-room group, volume 20, unmuted, playing the Steve Aoki Remix Radio station; see the complete table above and the HA-backed evidence below. |
| Whole-house observation | Pending |  |
| Runtime retirement | Pending |  |

### HA-backed deployment and restoration evidence (2026-08-29)

Supervisor reports `local_sonos_api` version 1.1.1, `state: started`, and
`options.backend_mode: home_assistant`. Its health endpoint reports
`backendMode: home_assistant`, live freshness, and no missing rooms, favorites,
or preset sources. The user-facing
`http://homeassistant.local:3000/sonos/zones` and
`/sonos/Bathroom/state` responses carry `X-Sonos-Response-Source:
home_assistant`.

All eight rooms were grouped, set to volume 20 and unmuted, selected to the
Home Assistant source `735 - Steve Aoki's Remix Radio`, and started through
Home Assistant `media_player` services. A same-value
`GET /sonos/Bathroom/volume/20` through the dashboard returned
`{"status":"success"}`; the subsequent Home Assistant state remained playing
at volume 0.2 with the same eight-member group and station. This is the
low-risk control-path proof that dashboard control is using the HA-backed
adapter. Sonos-app visual confirmation, the 24/24/48/24-hour windows, and
explicit node-uninstall approval remain pending.

### Configuration rollback rehearsal evidence

The authoritative command sequence is in the plan's **Rollback** section. The rehearsal does not pass merely because Supervisor again reports `started`. Record all of the following in this file when it is run:

- UTC option-POST start, restart start, first new startup-log marker, first ready/node health, and completion timestamps, with total RTO under 10 minutes.
- Before/after `docker inspect addon_local_sonos_api` `.RestartCount` and `.State.StartedAt`, distinguishing the one planned restart from any unexpected restart.
- Sonos API, Grid, and node installed versions; the resulting `backend_mode`; sanitized health body; direct node, Sonos API, and Grid topology summaries; one room-state summary; and low-risk action result.
- Exact full restoration observations for group/coordinator/member set, all eight volume/mute pairs, playback, station, verification surfaces, and zero pending operations.
- Trigger or rehearsal purpose, command results, failures, and whether the shadow clock was invalidated. Switching back to shadow starts a new clock only after parsed node+HA readiness, state restoration, and a comparison clean beyond the 5-second grace.

### Final merge-to-main status

| Gate | Status | Required evidence |
| --- | --- | --- |
| Automated and live acceptance complete | Pending | Final immutable test/package evidence plus completed 24-hour shadow, 24-hour pilot, 48-hour whole-house, and 24-hour stopped-node windows; explicit behavior acceptance and node-uninstall approval. |
| Candidate provenance | Pending | Final candidate SHA, package digests, deployed versions, observation timestamps, retirement/clean-install evidence, and clean candidate worktree. |
| Preserve existing main work | Pending | Before/after main dirty-path status and patch/hash inventory proving the merge did not stash, reset, restore, clean, overwrite, stage, or commit unrelated user changes. |
| Merge result | Pending | Reviewed candidate commit range in main, merge/fast-forward SHA, post-merge checks, and unchanged pre-existing main dirty state. |

## Acceptance exceptions and parity approvals

No exception has been granted. Explicit user approval for the five HA-mode-only `410` responses (`/pause`, `/play`, `/tv`, `/07`, `/quiet`) is still pending; until it is recorded here, Phase 0 and a new shadow observation clock remain blocked.
