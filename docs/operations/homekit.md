# Apple Home and Siri

The existing paired Home Assistant bridge exports an explicit catalog of household
fixtures and public scene-wrapper scripts. Home Assistant's UI owns this bridge;
the repository owns its desired export list and naming contract. Apple Home owns
its cached accessory names, room assignments, Display As choices and native scenes.

## Everyday controls

Assign each fixture to its physical room using the names in `home-model/rooms.json`.
Use short fixture names within the room: **Upper Cabinets**, **Floor Lamp** or
**Curtain Lights**. The full request identifies the room when needed, for example
“Turn off the kitchen upper cabinets.” The piano and dining lamps display as
lights even though their HA entities are switches.

Room presets use **Bright**, **Medium**, **Dim** and **Off**. The fixed-output Closet
has **On** and **Off** only. Patio uses the stable `outdoor` scene family. Dining
Room fixtures retain their physical placement; existing Kitchen presets also reach
the dining nook. This cleanup does not invent a separate Dining Room scene family.
**House Lights Out** activates the whole-home all-off wrapper. **LED Wall Ten
Percent** activates the existing wall brightness wrapper.

Use “Set the Office Bright scene” to request the curated preset. Ordinary room
on/off and brightness requests act directly on exposed fixtures; they do not
implicitly invoke the scene dispatcher. A future logical room-light interface
would need separately defined brightness/state semantics and dispatch behavior.

## Preset implementation

HomeKit Bridge represents HA scripts as activate-only switch accessories. Export
only the named `script.fast_scene_<scene_id>` wrappers, never native HA scene
entities or internal dispatchers. The script IDs and Assist names stay intact.

For each cataloged preset:

1. Rename its Apple Home trigger to **Apply <preset>** and assign it to the
   corresponding room. The whole-home trigger is kept in Living Room.
2. Keep the trigger's Display As setting at **Switch** and turn **Add to Home View**
   off. Hiding a tile does not remove Siri access, so the **Apply** prefix keeps
   trigger names distinct from native scene names.
3. Create a native Apple Home scene called **<preset>** containing exactly that
   trigger, set to **Turn On**. Include no individual bulb states.
4. Keep room scenes out of Home View so they appear in their room without filling
   the main view. Turn off **Show Suggested Scenes** in Home Settings (or **Hide
   Suggested Scenes** in a suggested scene's context menu) so Home does not add
   recommendations beside the chosen shortcut. **House Lights Out** is the
   main-view shortcut.

The trigger resets automatically; its switch state does not represent a persistent
lighting mode or prove that every physical light reached the requested state.
The wrapper retains RF pacing, health filtering, target-scope intent and convergence.
Do not duplicate those behaviors in Home automations or scene bulb snapshots.

## Reconcile and verify

1. Edit `home-model/homekit-catalog.json`. Its explicit fixture and preset lists
   select exports; both inherit areas from `device-catalog.json` and room names
   from `rooms.json`. Shared preset labels in `scene-presets.ts` also supply HA
   script voice metadata; existing Assist aliases remain unchanged. Only the
   three existing special Apple names need `presetNames` overrides. Missing or
   unconfirmed placements, diagnostic patterns, protected supplies, missing scene
   wrappers, ambiguous names and bridge capacity violations fail validation.
2. Run `just homekit-audit` and review the names, unavailable fixtures and export
   plan. Run the HA configuration tests and TypeScript build for source changes.
3. Run `just homekit-apply` to update the existing bridge in place. It saves the
   original bridge options, pairing state, accessory/characteristic allocations and
   name changes under ignored `build/homekit-cleanup/`, with directory mode 0700 and
   file mode 0600. These snapshots contain credentials and must never enter Git,
   wiki sources or chat.
4. Verify the complete catalog in Apple Home: room names, each fixture's name and
   category, **Apply** trigger names and visibility, and one **Turn On** action per
   native scene. The CLI does not read Apple's Home database and cannot certify
   this step. Rebuilding HA YAML does not reproduce Apple-owned metadata.
5. Review the lighting and dashboard wiki components and publish the documentation.

The CLI verifies the same bridge entry, data and pairing identity, exact explicit
filter, HA name readback and each resolved retained accessory ID. Domain includes
remain empty so new entities cannot silently appear. A timeout or incomplete HTTP
response must be followed by readback before retrying; options-flow completion
responses intentionally omit the saved options data.

Both bridge configurations are UI-created. Adding `homekit:` YAML would create
another instance. Never reset/unpair the existing bridge, change its port/identity,
delete its state files, or rename entity IDs as a naming migration. The unused
unpaired companion bridge is outside this reconciliation's mutation scope.

The catalog deduplication preserves the resolved 38 fixtures, 36 preset names and
trigger names, and 74 exported entity IDs. It also preserves all generated scripts
and the bridge configuration. It requires no live apply, new pairing or Apple
scene recreation. The two Dim scripts for Patio and Guest Bathroom now have
explicit entries in the shared placement catalog, matching their existing Home
room contract; this repository change does not itself update HA registry areas.

## Hub and availability checks

On November 19, 2026, Apple Home reported its Living Room hub as unresponsive and
rejected a rename and creation of Bedroom. Ryan assigned the online Bedroom Apple
TV to the newly created Bedroom in **My Home**. Home then reported **Bedroom Apple
TV** as **Active Home Hub**, and room/name edits succeeded. Preserve that assignment.
Relaunching the Mac Home app refreshed its stale main view and removed the old hub
warning. Room views already showed the new metadata before the main view refreshed.

If edits fail again, check **Home Settings → Home Hubs & Bridges** first. An online
Apple TV is eligible after its **Settings → AirPlay and Apple Home → Room** points
to this Home and its default user is the Home's owner. Do not reset the Home or
bridge to work around an unavailable hub. The older Living Room Apple TV's own
No Response status is separate from whether Bedroom is the active hub.

Fixture availability is also separate. Compare the specific HA entity with Apple
Home before diagnosing a bridge problem. This cleanup retains known unavailable
fixtures and existing device/scene exclusions; a naming change is not a repair or
a continuous availability check. UniFi inspection is read-only unless Ryan approves
a concrete network change under `network-infra/unifi-mcp/POLICY.md`.

## Recovery

Use the saved `entity-name-plan.json` to restore each HA registry name and aliases
through its supported entity-registry update API. Restore the previous export
selection through the same bridge's normal options flow. Keep retained entity IDs
and the bridge entry unchanged. Apple Home names and rooms can be edited back in
the Home app; cataloged scene definitions make their intended actions reviewable.
Pairing state files are emergency recovery evidence, not the normal rollback path:
do not overwrite a running integration's storage or discard newer pairings.

Sources: [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/),
[organizing Apple Home](https://support.apple.com/en-us/126180),
[Siri control](https://support.apple.com/en-us/105027), and
[Home hubs](https://support.apple.com/en-gb/102557).
