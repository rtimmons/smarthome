# Audio and Sonos

The dashboard uses `sonos-api` to present consistent room, favorite, playback, and grouping controls. The active target path is Grid Dashboard → Sonos API → Home Assistant’s Sonos integration → speakers.

## Daily use

Choose a room or group before adjusting volume. A grouping action can remain pending while the API waits for Home Assistant to confirm the topology. If an operation is partial, inspect which room failed instead of repeating every write.

## Current architecture and retained rollback

The October 9, 2026 deployment record reports Home Assistant-backed Sonos API healthy and the legacy Node service persistently disabled. The legacy source and installed add-on remain for rollback; they are not an active dependency or an instruction to restart it. The generated service table reflects the manifest’s disabled status.

Earlier migration sections describe staged tests and unresolved acceptance windows. Read the newest dated record before interpreting those historical tables as current service state.

## Configuration, diagnosis, and recovery

Sonos API enforces the allowed room-to-entity map generated from the shared `home-model/rooms.json`, and owns favorites, TV presets, and backend selection. Fixed rooms use the same names as Home Assistant areas except Move, which keeps its speaker/dashboard name and is permanently assigned to Patio. Patio retains the existing `outdoor` lighting routes. Additional physical areas do not automatically become playback destinations. See the [dashboard guide](dashboard.md) for room maintenance. The browser does not receive Home Assistant credentials or signed artwork URLs. Topology operations wait for authoritative state rather than assuming a successful write means speakers have regrouped.

If all audio controls fail, check Sonos API readiness and Home Assistant connectivity. If only one room fails, inspect that speaker’s reachability and group membership. Bonjour/multicast problems belong to the network investigation, not to arbitrary application restarts.

Preserve playback, volume, and groups during diagnosis. Restore saved configuration through the deployment and backup workflows; selecting the retained Node backend requires a deliberate rollback, not merely starting the old container.

Read the [architecture](../../docs/sonos/overview.md), [routing contract](../../docs/sonos/routing-guide.md), and [dated migration evidence](../../docs/sonos/ha-migration-validation.md).
