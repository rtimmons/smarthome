# Lighting and automation

Room controls select desired lighting states. The repository’s TypeScript model generates Home Assistant scenes, automation triggers, and the scripts that apply them.

## Everyday use

Use the room controls in the dashboard or normal wall switches. Room requests can coexist when they control different targets. For overlapping targets the newest request wins; whole-home all-off overrides every scope.

Operational automation must call `script.fast_scene_<scene_id>`. Native `scene.turn_on` bypasses the repository’s dispatch protections.

## Why a scene can take time

Z-Wave commands share a paced queue. Health filtering skips unavailable targets; later passes reconcile mismatches. Switch-originated requests suppress the already-operated local load initially and briefly allow the radio network to settle. Non-Z-Wave work starts alongside the Z-Wave branch.

The October 13 investigation reproduced a driver defect that affects otherwise responsive lights: Z-Wave JS 15.31.1 rejects valid fragment-completion replies after a security session renews, retries a command the light has already accepted, and eventually times out. That unnecessary wait delays other lights in the shared queue. A repository-owned compatibility plugin restores the missing protocol exception while preserving security checks on lighting commands. It survives restarts, is limited to the verified driver version, and must be reviewed when Z-Wave JS updates. See the runbook for evidence, deployment, rollback, and live test results. The USB hub has not been established as a cause.

A second measured problem was repeated use of failing radio rates and indirect paths. The controller now has 26 individually tested route preferences, mostly using 40 kbit/s. One light's transmission fell from 2,430 ms to 10 ms with that change. In the final living-room test, all available targets reported the requested state within 4.9 seconds and confirmation finished within eight seconds, with no radio errors during the test; Ryan confirmed the restored lighting looked right. The dead desk lamps were skipped. Two Z-Wave devices remain offline, so this result does not mean every device has been repaired.

Installed RGBW strips use aggregate endpoint 1 once. Separate white endpoint entities are diagnostic and may report on without lighting the strips. Multicast remains disabled. Outlets that power smart bulbs must not be turned off by scenes.

## Configuration and troubleshooting

The device registry owns logical names and entity mappings. Scene definitions own desired states; automation definitions connect triggers to those scenes. Generated scripts are deployment output, not a second source of truth.

Read the generated device table before assuming a missing light is a new fault: temporarily removed and scene-excluded devices are intentional configuration. Do not clear those markers without the required repair evidence.

Begin with `just ha-state <entity_id>` and the documented inventory/health commands. Record which targets changed and which did not. Never expand a command across diagnostic endpoints or remove a Z-Wave node simply to retry a scene.

The [Z-Wave runbook](../../docs/operations/zwave-scene-ops.md) explains evidence collection, radio pacing, device exceptions, and repair boundaries. The [generator guide](../../new-hass-configs/config-generator/README.md) explains editing and generation. Home Assistant configuration backups and the repository model are both needed for recovery; regenerating YAML does not restore the Z-Wave controller’s network.
