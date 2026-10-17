# Shared home rooms

`rooms.json` is the source for physical area names and dashboard room controls.
Area IDs and room IDs are stable identifiers; display names are not identifiers.
The `rooms` array preserves tile and Sonos allowlist order. `groupAllOrder`
preserves the existing join-all dispatch order independently of the layouts.

Each dashboard room explicitly selects its Sonos entity, lighting scene family,
temperature source, and icon. Move uses Outdoor as its control context and is
portable; this does not locate or permanently assign the speaker to Outdoor.
Dining Room and Maker Room are physical areas without dashboard tiles. Extra
areas never expand the Sonos allowlist or lighting targets automatically.

## Change and validate

1. Edit `rooms.json`.
2. Run `just rooms-generate` to refresh the checked-in browser/server catalog and
   typed Sonos map. Generated files are included in the normal add-on packages.
3. Run `just test grid-dashboard` and `just test sonos-api`. Both suites reject
   stale generated catalogs; existing scene-contract tests validate lighting routes.
4. Update and review the dashboard/audio guides, then deploy the affected add-ons.

`just rooms-check` verifies generated files without rewriting them. Area names
are reconciled explicitly, not during add-on startup or every Sonos rename.

## Live area maintenance

`just rooms-verify` compares each Sonos speaker's read-only device-description
room name with its Home Assistant player/device names and assigned area.
`--record-verification` saves only those names, areas and outcomes for the
generated wiki. Sleeping/offline speakers are explicitly unverified; mismatches
fail the check. Changes to either room or device catalog mark the receipt stale.
This does not rename speakers, change groups or start the retired node service.

`just rooms-audit` reads the registries through the repository HA client and
checks known legacy area IDs against all device/entity assignments (including
disabled entities), stored UI configuration, and YAML/template text. It emits
only reference filenames, not their contents. It uses the repository SSH key
and the SSH environment's standard file-search tools for the reference scan.

`just rooms-apply` updates known display names and merges historical voice
aliases, preserving area IDs and existing metadata. It refuses unknown name
changes or unexpected fixed-speaker assignments. It does not change playback,
entity IDs, geographic zones, lighting scenes, or assign portable speakers.

`just rooms-apply --remove-empty-legacy` also deletes explicitly enumerated,
empty, unreferenced legacy areas. Areas with any detected references are
retained for manual review; missing areas are not recreated. Private before/after
area metadata and the plan are saved under ignored `build/room-alignment/`.
To undo a rename, use the HA area editor/API with the saved original name and
aliases. Deleted empty areas can be recreated from the saved metadata if needed.

The reference scan is conservative textual checking, not a proof about arbitrary
external clients or dynamically computed templates. It only removes the known
legacy areas; additional physical spaces remain outside cleanup scope.

## Devices and entity placement

`device-catalog.json` is the reviewed placement catalog. Each device uses a stable
anchor entity and inherits its assigned area to every attached entity, including
disabled diagnostics. `relatedEntityIds` connects additional logical lighting
entities to that same device. `entities` lists standalone controls/helpers with
explicit areas. Portable, shared, unconfirmed, temporarily removed and retired
entries remain distinct. No live name-prefix guessing occurs during reconciliation.

`just areas-audit` compares all registered entities to this catalog. It reports
unknown entities and fails on unexpected device associations or any entity-level
override on a cataloged device. Review those before updating the catalog. The two
entity-less HomeKit bridge devices remain unassigned shared infrastructure.

`just areas-apply --record-verification` applies only area metadata, saves private
before/after registries and the exact plan in ignored `build/room-alignment/`, then
records sanitized counts and a catalog digest in `area-verification.json`. Audit
with `--record-verification` can refresh the receipt without writing to HA if the
catalog already matches. An outdated digest is shown explicitly in the wiki.
Unconfirmed records are never assigned; absent hardware is not recreated, and
retired records are audit-only, never an automatic deletion instruction.

Logical lighting area fields in `devices.ts` and the hardware product catalog's
`knownRepoReferences[].area` must match this catalog. Tests check those contracts.
Neither area fields nor this maintenance command affect scene targets, entity IDs,
availability, disable/exposure settings, playback groups or power protections.

The generated wiki room catalog is the human review surface: physical devices,
dashboard controls, cross-room presets, standalone helpers, unresolved locations,
retirements and dated verification totals. To roll back metadata, apply the saved
plan's `from` values through HA's device/entity editor and correct the catalog.
