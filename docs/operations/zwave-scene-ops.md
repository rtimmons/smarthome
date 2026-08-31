# Z-Wave Scene Operations

Reference workflow for diagnosing and fixing slow Home Assistant scenes that are dominated by Z-Wave devices.

## Goals

- Keep scene activation bounded and latest-intent so one slow node or stale room request does not block newer lighting input or flood the controller.
- Normalize Z-Wave ramp and transition parameters to instant or fastest-safe values.
- Capture timestamped local audit snapshots for future comparison.
- Check device registry correctness before assuming the network is the only problem.

## Primary Commands

From the repo root:

```bash
just zwave-diagnose
just zwave-inventory
just zwave-apply-instant-ramps
just zwave-verify-instant-ramps
```

From [`new-hass-configs/Justfile`](/Users/rtimmons/Projects/smarthome/new-hass-configs/Justfile):

```bash
just zwave-diagnose --scene living_room_high --scene all_off
just zwave-inventory
just zwave-apply-instant-ramps
just zwave-verify-instant-ramps
```

`just zwave-inventory` writes a timestamped snapshot under `new-hass-configs/inventory_snapshots/zwave-scene-audits/`.

Connection failures are stage-specific. Use the ignored repository identity explicitly with `ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local`. `SSH_HOSTNAME_RESOLUTION_FAILED` means `homeassistant.local` failed before authentication: retry the same hostname-based command once outside the Codex sandbox, never substitute an IP, and report mDNS/network failure if it persists. `SSH_AUTHENTICATION_FAILED` means the host was reached: stop and ask Ryan to rerun the human-only `just ha-ssh-key-copy`; do not fall back to 1Password or alternate credentials.

## Standard Workflow

1. Run `just zwave-inventory` to capture the current network, scene, and registry state.
2. Review `inventory-report.json` for:
   - `scene_parallelism_findings`
   - `scene_availability_findings`
   - `unhealthy_zwave_nodes`
   - `entity_audit_findings`
   - `suspicious_log_summary.nodeCounts`
3. If `live_ramp_plan` is non-empty, run `just zwave-apply-instant-ramps` and then `just zwave-verify-instant-ramps`.
4. If scenes still lag, inspect the generated fast scene calls. The GE 46203 and on/off-only Minoston MP22ZD fixtures expose Switch Multilevel CC38, not Binary Switch CC37. They use isolated `zwave_js.set_value` calls with `wait_for_result: false` and an explicit zero-second transition.
5. If a target entity is `unavailable` or its node-status sensor is `dead`, treat the underlying fault as a device/platform issue. The generated dispatcher skips it so the fault does not block healthy targets, but that resilience is not a substitute for repairing or removing the node.

## Failed-Node Removal and Re-Inclusion

Before removing a failed node, save a Z-Wave JS NVM backup. Submit one failed-node removal request and wait for the controller response. If the request is accepted but the WebSocket completion event times out, do not submit a duplicate removal: inspect the persistent Z-Wave log and controller state first. When a later operation reports `node_not_found`, restart only the Z-Wave JS add-on once to reconcile its runtime with the controller NVM, then verify the node is absent from the fresh startup list and that Home Assistant removed the corresponding active device and entity registry entries.

As of 2026-08-21, former nodes 2 (`living_palm`, Minoston MP22ZD) and 16 (`outdoor_cafe`, Minoston MP22ZD) are intentionally absent. Their desired entity IDs remain in `devices.ts` with `inventoryStatus: "temporarily_removed"`; inventory reports them separately and does not count their expected absence as registry drift. The post-removal controller baseline is 31 nodes, all Alive and ready, with zero unhealthy Z-Wave nodes.

To re-add either plug later:

1. Exclude or factory-reset the plug as needed, then include it normally.
2. Restore its desired entity ID (`light.light_living_palm` or `light.light_outdoor_cafe`).
3. Remove `inventoryStatus: "temporarily_removed"` from `devices.ts`.
4. Run `just zwave-inventory`; the entity must be active, healthy, and free of registry drift before relying on scenes.

## Interpretation Notes

- Live websocket reads are authoritative for Z-Wave config verification. Cache files can lag after writes.
- In this repo, preserve grouping for Hue or other non-Z-Wave lights while isolating every Z-Wave-backed entity. There is currently no Z-Wave multicast allowlist: repeated operational failures on 2026-08-30 and 2026-08-31 invalidated the former Minoston MP22ZD group.
- Registry mismatches matter. If a configured device entity does not exist live, fix the device registry before changing scene logic.
- Repeated timeout, decode, nonce, or invalid-payload entries isolated to one node usually indicate a bad or noisy route. Clusters spanning multiple nodes at the exact time of a large scene are evidence that the scene's RF concurrency is still too high.

## Current Bathroom Lighting Baseline

As of 2026-08-10, the five main bathroom bulbs are Zigbee devices on ZHA:

| Device key | Active entity ID | High | Medium | Low | Off / All Off |
| --- | --- | ---: | ---: | --- | --- |
| `bathroom_vanity_left` | `light.light_bathroom_vanity_left` | 254 | 155 | 50 | off |
| `bathroom_vanity_right` | `light.light_bathroom_vanity_right` | 254 | 155 | 50 | off |
| `bathroom_abovesauna` | `light.light_bathroom_abovesauna` | 254 | 155 | off | off |
| `bathroom_edison_top` | `light.light_bathroom_edison_top` | 254 | 155 | 50 | off |
| `bathroom_edison_bottom` | `light.light_bathroom_edison_bottom` | 254 | 155 | 50 | off |

- The vanity and above-sauna bulbs are Third Reality `3RCB01057Z` color bulbs supporting `color_temp` and `xy`. Edison-top and Edison-bottom are brightness-only Sengled `E11-N1G` bulbs. All five report 254 as maximum brightness.
- Compatible on/off calls should be grouped as non-Z-Wave targets. The above-sauna bulb must not be isolated or paced as a Z-Wave load.
- Former Z-Wave nodes 38 (vanity-left), 39 (vanity-right), and 40 (above-sauna) are retired and absent from the active device registry and Z-Wave value inventory.
- The retired entity IDs `light.light_bathroom_vanityleft` and `light.light_bathroom_vanityright` must not appear in source or generated configuration.
- Home Assistant retains records for removed entities under `core.entity_registry.data.deleted_entities`. These are deletion tombstones, not active entities or callable service targets; active-remnant audits must inspect `data.entities`, the device registry, and the live state machine.
- Dashboard webhooks `scene_bathroom_high`, `scene_bathroom_medium`, and `scene_bathroom_off` route to their blocking `script.fast_scene_bathroom_*` wrappers. `bathroom_low` is available as a generated scene/script even though it has no dashboard webhook.

## Scene Dispatch and Concurrency Contract

All generated scene entry points must follow this path:

```text
button/webhook/dashboard
  -> script.fast_scene_<scene_id> (mode: restart; blocks script/automation callers)
  -> script.fast_scene_dispatch (mode: restart; newest intent wins)
  -> script.fast_scene_dispatch_worker (mode: restart; generated scene choices)
  -> health/state filter
  -> non-Z-Wave and Z-Wave branches start concurrently
  -> one Z-Wave submission per batch, paced 250 ms apart
  -> after 2 s, resubmit only targets whose actual state still differs
```

The layers are intentionally separate:

- The public wrapper and shared dispatcher both use `restart`. A newer request cancels unsent batches from an older room/preset instead of waiting behind stale work.
- Generated scene automations use `restart` and call `script.fast_scene_<scene_id>` directly as an action. Do not generate `script.turn_on` inside those automations: direct script actions preserve end-to-end cancellation when an automation restarts.
- The dashboard's authenticated Core API route necessarily starts the wrapper through `script.turn_on`; its one-second request gate still handles duplicate browser delivery, while the wrapper's own `restart` mode makes a later accepted request authoritative.
- Compatible `zwave_dimmer_46203` and `zwave_switch_light` targets use Switch Multilevel CC38 `zwave_js.set_value` with `wait_for_result: false`, `targetValue`, and `transitionDuration: 0s`. The on/off-only type still represents dimmer hardware, so on/off levels are 99/0 rather than CC37 booleans.
- Non-Z-Wave calls and the bounded Z-Wave branch begin concurrently. A slow Hue, ZHA, or switch service response must not create a one-second gate before the first Z-Wave transmission.
- Multicast remains deny-by-default, with no current allowlist. The former Minoston MP22ZD group initially passed controlled trials but later failed repeatedly in normal operation, so all compatible devices now use isolated non-waiting CC38 `set_value`. GE 46203 and Zooz ZEN31 devices remain isolated as well.
- Before dispatch, unavailable/unknown entities and entities whose enabled Z-Wave node-status sensor is `dead`, `unavailable`, or `unknown` are omitted. Off scenes also omit targets that are already off, which avoids wasting RF transactions on satisfied loads.
- Every service action uses `continue_on_error: true`. An action-level failure is logged by Home Assistant but does not abort the remaining healthy work.
- Empty Z-Wave batches are skipped. The 250 ms delay occurs only before a later batch that actually has work, so dead and already-off targets do not add artificial latency.
- Skipped targets fire `fast_scene_targets_skipped`. The manual `Fast Scene Skipped Targets Alert` automation turns that into one replace-in-place persistent notification; it does not retry the target inside the scene.
- Devices with `fastScenePriority: "last"` are placed after normal Z-Wave loads. Nodes 23 and 28 currently use it so their acknowledgement timeouts start only after healthy loads have been dispatched.
- `DEFAULT_MAX_ZWAVE_CALLS_PER_STEP` is one. After removing the failed Minoston multicast allowlist, a live two-call Living High/Off replay still produced a same-burst decode/invalid-payload cluster on nodes 4 and 6, so submissions were serialized on 2026-08-31. `DEFAULT_ZWAVE_BATCH_DELAY_MS` remains 250 ms: non-waiting value submissions avoid an acknowledgement drain while retaining enough spacing to avoid collapsing the scene into one burst.
- After the initial worker dispatch and a two-second delay, the dispatcher calls the same compact worker in mismatch-only mode. The delay and correction are canceled by newer intent. This is required because restart can cancel unsent script work but cannot revoke an integration service call already in flight; without convergence, a stale Living High call left `living_light_floor` on after All Off. Keeping the scene choices in one worker avoids duplicating the generated YAML for the correction pass.
- Do not replace the wrapper's direct `script.fast_scene_dispatch` action with non-blocking `script.turn_on`; the blocking link is what allows restart cancellation to propagate to unsent dispatcher work.
- Native `scene.<scene_id>` entities remain generated for Home Assistant UI/compatibility, but operational controls, diagnostics, automations, and tests must activate `script.fast_scene_<scene_id>`. Calling `scene.turn_on` bypasses health filtering, bounded Z-Wave batching, skipped-target reporting, and latest-intent cancellation.
- Never turn off an outlet that supplies a smart bulb. Mark it `includeInAllOff: false` and `allowSceneTurnOff: false`, leave it out of room-off/low scenes, and turn the bulb entity off instead. The generator rejects any future scene that tries to cut a protected outlet.

After changing this path, test both a scene and its opposite in one exercise, for example:

```bash
just zwave-exercise-scene --scene kitchen_high --scene kitchen_off
```

The exerciser must wait for `script.fast_scene_dispatch` to return to `off`, not merely for targets to momentarily match. Otherwise an earlier scene can still be sending commands after a later scene starts.
Targets that are missing or already `unavailable` before the exercise are reported and skipped. A target that becomes unavailable during the exercise still fails it; this distinction caught the smart-bulb power-cut bug without making known dead devices render every exercise useless.
Transition duration is a command option, not a persisted state attribute, so the exerciser does not compare it. It accepts a one-point Home Assistant brightness difference caused by round-tripping Z-Wave's 0..99 level through Home Assistant's 0..255 scale.
The exerciser reads one bulk Home Assistant state snapshot per poll and records `targetTimings` for each entity. Its console prints first/median/last response for targets that actually changed. Overall settle time includes the two-second convergence window; use the changed-target timing to judge visible responsiveness and settle time to judge end-to-end correctness.

`new-hass-configs/scripts.yaml` is a merged deployment artifact produced by `just generate`. It is ignored and untracked; edit `config-generator/src/scene-generation.ts` and related TypeScript sources, and review `generated/scripts.yaml` when inspecting output. `just check` and deployment prechecks regenerate the root file before syncing it.

## Grid Dashboard Lighting Contract

The grid dashboard's Sun, Dim, and Moon controls call the fast scripts through:

```text
Lights.Scene
  -> POST /scenes/scene_<room>_<preset>
  -> script.fast_scene_<room>_<preset>
```

- Room-to-scene IDs are explicit in `config.js` (`lightSceneRooms`); do not derive them only by lowercasing the Sonos room display name.
- Every mapped dashboard room must have generated `high`, `medium`, and `off` scripts. The dashboard test suite checks this against `generated/scripts.yaml`.
- Dashboard room names may intentionally point at a differently named lighting area. `Move` maps to `outdoor`, so its Sun, Dim, and Moon buttons call `outdoor_high`, `outdoor_medium`, and `outdoor_off`.
- The Moon double-press action is global `all_off`. Its single-click action must be delayed/cancelled so a desktop double-click cannot run both room-off and all-off.
- The dashboard server coalesces identical scene requests received within one second. This catches duplicate browser/touch delivery while preserving intentional retries after the window; Home Assistant's restart-mode wrapper makes the newest accepted request authoritative.
- The authenticated add-on path starts a fast-scene wrapper through the Core API and returns promptly. Standalone development can use `HASS_WEBHOOK_BASE`; that fallback retains its request timeout, but generated webhook automations now use the same restart/latest-intent path.
- Validate at least one live dashboard pair after deployment: click Sun, verify the intended `script.fast_scene_*_high` `last_triggered`, click Moon, and confirm every target is off.

## Persistent Logs and Route Maintenance

Keep Z-Wave JS file logging enabled so a host restart does not erase the evidence:

- `log_to_file: true`
- `log_level: info`
- `log_max_files: 7`
- logs: `/addon_configs/core_zwave_js/logs/zwavejs_YYYY-MM-DD.log`

Individual route rebuilds are Home Assistant WebSocket commands, not registered services in this installation:

```json
{
  "type": "zwave_js/rebuild_node_routes",
  "device_id": "<home-assistant-device-id>"
}
```

Run rebuilds sequentially. Confirm `rebuilt routes successfully` for each node in the persistent log before starting the next one.

## Home Assistant and Community Guidance

- Home Assistant scripts are sequential by default, stop on an action error by default, and wait for every branch in a `parallel` block. Use `continue_on_error` for expected device failures, but do not mistake parallel syntax for a timeout: [Home Assistant script syntax](https://www.home-assistant.io/docs/scripts).
- The Z-Wave JS integration exposes a node-status diagnostic sensor for each node and explicitly shows using it to detect and ping dead nodes. It also exposes per-node statistics and a per-device **Rebuild routes** action for diagnosing unexpected delays: [Home Assistant Z-Wave integration](https://www.home-assistant.io/integrations/zwave_js/).
- Home Assistant recommends a USB extension cable as the first RF/USB-interference troubleshooting step, followed by rebuilding routes for the affected device. Network-wide route discovery is heavy and should be used sparingly; polling can flood a low-bandwidth Z-Wave network and is a last resort: [Home Assistant Z-Wave troubleshooting](https://www.home-assistant.io/integrations/zwave_js/#troubleshooting).
- Community reports describe large group-off bursts producing dead nodes and commonly use paced, sequential ping recovery rather than simultaneous retries. That pattern supports this repo's low-concurrency dispatcher, but automatic pinging is not used as a permanent mask for a repeatedly dead mains node: [dead-node automation discussion](https://community.home-assistant.io/t/automate-zwavejs-ping-dead-nodes/374307?page=9) and [paced ping example](https://community.home-assistant.io/t/automate-zwavejs-ping-dead-nodes/374307?page=7).
- Whole-house scene users independently report that one unavailable light aborts later actions unless `continue_on_error` is set: [continue after unavailable device](https://community.home-assistant.io/t/automation-to-continue-after-device-unavailable/616876) and [whole automation failed because one light was unavailable](https://community.home-assistant.io/t/whole-automation-failed-because-one-light-was-unavailable/766510).

Operationally, a dead mains-powered node should be repaired, excluded, or replaced. Pinging can confirm/recover a transient failure; it should not be scheduled aggressively while scenes are running, because that adds exactly the traffic this dispatcher is designed to bound.

## 2026-08 Incident Findings

- Five controller `jammed` states were present in recorder history; four immediately followed large native-scene fanouts. This was the strongest evidence that unbounded scene concurrency was the initiating fault.
- Kitchen nodes 12, 13, and 14 became dead during the incident and recovered after the controller/host restart. Their routes, plus noisy node 23, were rebuilt successfully afterward.
- Four-call batches without an inter-batch delay still produced a large invalid-payload flood. Two-call batches paced one second apart removed that flood in a live All Off replay and kept the dispatcher active for the actual 27-second drain interval.
- The paced replay isolated residual timeouts to nodes 23 and 28. Node 28 (`switch.light_living_sillleftpower`) then failed all five neighbor-refresh attempts during a route rebuild. Treat that as a physical mesh/device-path problem; inspect power, placement, nearby repeaters, or replace/exclude-reinclude the outlet rather than rebooting the host or increasing scene concurrency.
- A Z-Wave stick unplug immediately before the host reboot explains the final USB disconnect messages only. Do not misclassify a user-initiated unplug as the original fault when symptoms predate it.
- A first high-to-off exercise exposed a false-positive test: target states briefly matched while the high script was still running, then late high commands overwrote the off commands. This led to the shared dispatcher and dispatcher-aware exercise polling.
- After remediation, the live dashboard Kitchen Sun/Moon path reached the correct fast scripts and a high-to-off exercise settled in roughly two seconds per scene without a new controller jam or command timeout.
- Live All Off verification exposed a separate power-model error: it cut power to the Flamingo Hue bulb, making the bulb unavailable. The power outlet is now excluded from All Off and bedroom off/low scenes.
- The 2026-08-20 post-deployment All Off replay settled all 50 reachable targets in 27.46 seconds and skipped five unavailable entities without aborting. Nodes 2 and 16 were already dead and were omitted; the only new RF errors were two timeouts from node 4 and one from last-priority node 28. This confirms the resilience path works while also showing that batching cannot repair weak physical routes.
- On 2026-08-21, nodes 2 and 16 were removed from the controller. Each removal was accepted but its completion event timed out; a single Z-Wave JS restart reconciled runtime state with controller NVM and Home Assistant then cleaned the active device/entity registry. A fresh inventory showed all 31 remaining nodes Alive and ready, with zero unhealthy Z-Wave nodes. The pre-removal NVM backup is ignored at `new-hass-configs/backups/zwave-js/zwave_js_backup_2026-08-21_before-removing-nodes-2-16.bin` (SHA-256 `0430357f705cd330f1c3dbb94eab6a229dbb35170b1a3403b8a5a965312e7356`).
- Later on 2026-08-21, recorder/logbook history showed the shared queued dispatcher active for 19.3 seconds while Living Room, Guest Bathroom, and Kitchen requests waited behind one another. Guest Bathroom Medium was requested at 22:02:00 but its two lights were not commanded until 22:02:06/07. This was stale-work serialization, not unavoidable RF latency.
- Guest-bath hold notifications were received as `KeyHeldDown`/`KeyReleased`; they were not lost events. Those holds directly changed the local loads after the paired-off scene, which explains the apparent scene reversal. Only single/double taps are mapped to room scenes today; use direct Z-Wave association if synchronized hold-to-dim behavior is desired rather than adding an HA polling loop.
- A same-value `zwave_js.multicast_set_value` trial on nodes 23 and 24 partially updated node 23, left node 24 unchanged, and logged `Unable to set value via multicast`. A later GE 46203 group trial generated an invalid-payload storm, and a Zooz ZEN31 group was a no-op. Those devices remain isolated.
- A model-homogeneous multicast trial on Minoston MP22ZD nodes 4, 6, 9, and 12 initially succeeded in both directions: all four state timestamps landed within 2 ms, with the action completing in 187–339 ms. Normal-operation calls later failed at 2026-08-30 23:59, 2026-08-31 01:51, and 2026-08-31 08:17 with `Unable to set value via multicast`; the allowlist was removed on 2026-08-31 and the four plugs returned to bounded unicast.
- The first bounded-unicast Living High/Off replay then changed every responsive target but produced a same-burst decode/invalid-payload cluster on nodes 4 and 6. This met the runbook's multi-node concurrency heuristic, so the production cap was reduced from two simultaneous submissions to one on 2026-08-31 while retaining 250 ms pacing.
- After switching wrappers/automations/dispatcher to `restart`, using `wait_for_result: false`, forcing `transitionDuration: 0s`, and reducing residual pacing to 250 ms, the pre-convergence guest-bath dispatcher returned to `off` in about 10 ms. A real off-to-medium exercise settled both nodes in 1.36 seconds and medium-to-off in 1.27 seconds, with no new Core scene-service error. The current public dispatcher deliberately remains active through its convergence check.
- Node 23 continues to time out while acknowledging commands even after a targeted route rebuild completed successfully. Its load still changes, but the device/security exchange is defective. Keep it isolated and non-waiting; plan to exclude/re-include or replace node 23 if the timeout traffic continues.
- Live inventory exposed a protocol regression in Kitchen High: nodes 12, 19, and 20 have CC38 `targetValue` but no CC37 value, so Core rejected the generated Binary Switch commands and three lights never turned on. The generator now uses CC38 99/0 for every `zwave_switch_light`; five repeated Kitchen High/Off cycles then settled all 9/9 targets.
- A 100 ms pacing trial made Living High faster but produced four invalid payloads and a new node-3 timeout, so the production cadence remains 250 ms. Running the independent non-Z-Wave branch concurrently still provides immediate visible response while isolated Z-Wave calls remain bounded.
- In two final rapid sequences (Living High, Kitchen High, Guest Bathroom Medium, All Off at 300 ms intervals), All Off was accepted in 39–92 ms, all 46 reachable targets were off 3.9–5.9 seconds after the final request, and no stale command reactivated a target during either five-second quiet window. Before the mismatch-only convergence pass, the same test left `living_light_floor` on for more than 30 seconds.

## Files Involved

- [`new-hass-configs/config-generator/src/scene-generation.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/scene-generation.ts)
- [`new-hass-configs/config-generator/src/cli/zwave-scenes.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/cli/zwave-scenes.ts)
- [`new-hass-configs/config-generator/src/devices.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/devices.ts)
- [`new-hass-configs/config-generator/src/scenes.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/scenes.ts)
- [`docs/operations/zwave-product-catalog.json`](/Users/rtimmons/Projects/smarthome/docs/operations/zwave-product-catalog.json) for stable make/model/product identity references. Do not use it for live health; use fresh inventory snapshots for node status and availability.

## When To Patch The Generator

Patch the generator when one of these is true:

- a Z-Wave-backed light or switch is grouped without an explicit live-verified multicast allowlist, or a compatible CC38 device waits for a command result
- a scene includes a controller-only entity that should never be toggled directly
- a paired RGBW/white device is not being expanded correctly
- a device registry entry points at the wrong live entity
- a generated automation or operational tool invokes `scene.turn_on`, queues stale scene work, or loses direct restart cancellation by using `script.turn_on` inside the automation

Do not patch the generator to compensate for an entity that is simply offline or unavailable.
