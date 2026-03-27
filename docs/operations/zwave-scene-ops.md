# Z-Wave Scene Operations

Reference workflow for diagnosing and fixing slow Home Assistant scenes that are dominated by Z-Wave devices.

## Goals

- Keep scene activation parallel so one slow node does not block unrelated loads.
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
- Repeated timeout, decode, nonce, or invalid-payload log entries usually indicate a specific bad or noisy node, not a global scene bug.

## Files Involved

- [`new-hass-configs/config-generator/src/scene-generation.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/scene-generation.ts)
- [`new-hass-configs/config-generator/src/cli/zwave-scenes.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/cli/zwave-scenes.ts)
- [`new-hass-configs/config-generator/src/devices.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/devices.ts)
- [`new-hass-configs/config-generator/src/scenes.ts`](/Users/rtimmons/Projects/smarthome/new-hass-configs/config-generator/src/scenes.ts)

## When To Patch The Generator

Patch the generator when one of these is true:

- a Z-Wave-backed light or switch is still grouped with other loads
- a scene includes a controller-only entity that should never be toggled directly
- a paired RGBW/white device is not being expanded correctly
- a device registry entry points at the wrong live entity

Do not patch the generator to compensate for an entity that is simply offline or unavailable.
