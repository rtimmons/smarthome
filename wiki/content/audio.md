# Audio and Sonos

The dashboard uses `sonos-api` to present consistent room, favorite, playback, and grouping controls. The active target path is Grid Dashboard → Sonos API → Home Assistant’s Sonos integration → speakers.

## Daily use

Choose a room or group before adjusting volume. A grouping action can remain pending while the API waits for Home Assistant to confirm the topology. If an operation is partial, inspect which room failed instead of repeating every write.

## Current architecture and retained rollback

The October 9, 2026 deployment record reports Home Assistant-backed Sonos API healthy and the legacy Node service persistently disabled. The legacy source and installed add-on remain for rollback; they are not an active dependency or an instruction to restart it. The generated service table reflects the manifest’s disabled status.

Normal Sonos controls were confirmed after the October 22 gateway changes. Final legacy removal still needs the acceptance, observation and reinstall safeguards in the [remaining-work checklist](../../docs/plan-replace-sonos-node-api.md). Calendar time since disablement alone does not prove those checks passed.

## Configuration, diagnosis, and recovery

Sonos API enforces the allowed room-to-entity map generated from the shared `home-model/rooms.json`, and owns favorites, TV presets, and backend selection. Fixed rooms use the same names as Home Assistant areas, including Patio (formerly Move). Patio retains the existing `outdoor` lighting routes. Additional physical areas do not automatically become playback destinations. See the [dashboard guide](dashboard.md) for room maintenance. The browser does not receive Home Assistant credentials or signed artwork URLs. Topology operations wait for authoritative state rather than assuming a successful write means speakers have regrouped.

If all audio controls fail, check Sonos API readiness and Home Assistant connectivity. If only one room fails, inspect that speaker’s reachability and group membership. Bonjour/multicast problems belong to the network investigation, not to arbitrary application restarts.

Preserve playback, volume, and groups during diagnosis. Restore saved configuration through the deployment and backup workflows; selecting the retained Node backend requires a deliberate rollback, not merely starting the old container.

Read the [architecture](../../docs/sonos/overview.md), [routing contract](../../docs/sonos/routing-guide.md), and [dated migration evidence](../../docs/sonos/ha-migration-validation.md).

Unconfigured Sonos speakers do not invalidate all dashboard groups. When an
unconfigured speaker is a follower, group and room-state reads show the configured
members using the real configured coordinator. When the coordinator itself is
unconfigured, affected configured rooms are marked unavailable and omitted from
group reads; independent groups remain visible. No follower is promoted to an
invented coordinator. Group-changing commands still validate full membership and
reject groups containing unconfigured speakers. Adding a speaker to the dashboard
remains an explicit room-catalog change.
