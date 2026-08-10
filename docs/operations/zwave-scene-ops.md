# Z-Wave Scene Operations

Reference workflow for diagnosing and fixing slow Home Assistant scenes that are dominated by Z-Wave devices.

## Goals

- Keep scene activation bounded and parallel so one slow node does not block unrelated loads or flood the controller.
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

## Standard Workflow

1. Run `just zwave-inventory` to capture the current network, scene, and registry state.
2. Review `inventory-report.json` for:
   - `scene_parallelism_findings`
   - `scene_availability_findings`
   - `entity_audit_findings`
   - `suspicious_log_summary.nodeCounts`
3. If `live_ramp_plan` is non-empty, run `just zwave-apply-instant-ramps` and then `just zwave-verify-instant-ramps`.
4. If scenes still lag, inspect the generated fast scene calls and isolate any remaining Z-Wave-backed entities so they are sent in separate parallel service calls.
5. If a target entity is `unavailable`, treat that as a device/platform issue, not a scene-generation issue.

## Interpretation Notes

- Live websocket reads are authoritative for Z-Wave config verification. Cache files can lag after writes.
- In this repo, the right fix is usually to preserve grouping for Hue or other non-Z-Wave lights while isolating Z-Wave-backed entities.
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
  -> script.fast_scene_<scene_id> (mode: single, blocking)
  -> script.fast_scene_dispatch (mode: queued)
  -> batches of at most 2 parallel Z-Wave calls, paced 1 second apart
```

The layers are intentionally separate:

- The public wrapper remains active until the dispatcher finishes. Its `single` mode therefore coalesces repeated activation of the same scene.
- Generated and manual scene automations use `single`, not `restart`. Restarting a caller can cancel a blocking child call while controller transactions are still draining.
- The shared queued dispatcher prevents different scenes or rooms from multiplying the Z-Wave fanout.
- `DEFAULT_MAX_ZWAVE_CALLS_PER_STEP` is the global per-step Z-Wave cap. It is two because a live All Off exercise still produced multi-node timeout and invalid-payload clusters at four. `DEFAULT_ZWAVE_BATCH_DELAY_MS` is one second because Home Assistant service actions return after enqueueing work, not after RF completion; without a delay, adjacent YAML batches still became one burst. Keep both conservative unless a measured exercise and clean logs justify a change.
- Do not replace the wrapper's direct `script.fast_scene_dispatch` action with non-blocking `script.turn_on`; doing so makes wrapper `mode: single` ineffective.
- Never turn off an outlet that supplies a smart bulb. Mark that outlet `includeInAllOff: false`, leave it out of room-off/low scenes, and turn the bulb entity off instead.

After changing this path, test both a scene and its opposite in one exercise, for example:

```bash
just zwave-exercise-scene --scene kitchen_high --scene kitchen_off
```

The exerciser must wait for `script.fast_scene_dispatch` to return to `off`, not merely for targets to momentarily match. Otherwise an earlier scene can still be sending commands after a later scene starts.
Targets that are missing or already `unavailable` before the exercise are reported and skipped. A target that becomes unavailable during the exercise still fails it; this distinction caught the smart-bulb power-cut bug without making known dead devices render every exercise useless.

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

## 2026-08 Incident Findings

- Five controller `jammed` states were present in recorder history; four immediately followed large native-scene fanouts. This was the strongest evidence that unbounded scene concurrency was the initiating fault.
- Kitchen nodes 12, 13, and 14 became dead during the incident and recovered after the controller/host restart. Their routes, plus noisy node 23, were rebuilt successfully afterward.
- Four-call batches without an inter-batch delay still produced a large invalid-payload flood. Two-call batches paced one second apart removed that flood in a live All Off replay and kept the dispatcher active for the actual 27-second drain interval.
- The paced replay isolated residual timeouts to nodes 23 and 28. Node 28 (`switch.light_living_sillleftpower`) then failed all five neighbor-refresh attempts during a route rebuild. Treat that as a physical mesh/device-path problem; inspect power, placement, nearby repeaters, or replace/exclude-reinclude the outlet rather than rebooting the host or increasing scene concurrency.
- A Z-Wave stick unplug immediately before the host reboot explains the final USB disconnect messages only. Do not misclassify a user-initiated unplug as the original fault when symptoms predate it.
- A first high-to-off exercise exposed a false-positive test: target states briefly matched while the high script was still running, then late high commands overwrote the off commands. This led to the shared dispatcher and dispatcher-aware exercise polling.
- After remediation, the live dashboard Kitchen Sun/Moon path reached the correct fast scripts and a high-to-off exercise settled in roughly two seconds per scene without a new controller jam or command timeout.
- Live All Off verification exposed a separate power-model error: it cut power to the Flamingo Hue bulb, making the bulb unavailable. The power outlet is now excluded from All Off and bedroom off/low scenes.

## Files Involved

- [`new-hass-configs/config-generator/src/scene-generation.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/scene-generation.ts)
- [`new-hass-configs/config-generator/src/cli/zwave-scenes.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/cli/zwave-scenes.ts)
- [`new-hass-configs/config-generator/src/devices.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/devices.ts)
- [`new-hass-configs/config-generator/src/scenes.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/scenes.ts)
- [`docs/operations/zwave-product-catalog.json`](/Users/rtimmons/Projects/smarthome/docs/operations/zwave-product-catalog.json) for stable make/model/product identity references. Do not use it for live health; use fresh inventory snapshots for node status and availability.

## When To Patch The Generator

Patch the generator when one of these is true:

- a Z-Wave-backed light or switch is still grouped with other loads
- a scene includes a controller-only entity that should never be toggled directly
- a paired RGBW/white device is not being expanded correctly
- a device registry entry points at the wrong live entity

Do not patch the generator to compensate for an entity that is simply offline or unavailable.
