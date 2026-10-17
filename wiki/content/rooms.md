# Rooms and device locations

Start with the [room-by-room catalog](wiki-reference:rooms). It shows each physical device's area, its identifying entity, the dashboard's speaker/lighting/temperature mapping, and presets that reach across room boundaries. Expand a room's controls and helpers to find its scripts, scenes, automations and intent helpers. Wiki search also finds exact entity IDs. The [lighting catalog](wiki-reference:devices) adds logical names, hardware models and power protections.

## How room assignments work

Home Assistant **areas** describe physical rooms. Fixed Sonos rooms and dashboard selections use the same names. Home Assistant geographic zones remain location/geofencing concepts; playback groups remain temporary audio groupings.

The [generated name comparison](wiki-reference:rooms#speaker-names) shows what Sonos speakers reported beside their Home Assistant player/device names and physical areas. Refresh it with `just rooms-verify --record-verification`. Offline speakers remain explicitly unverified; a new wiki build alone does not claim a fresh live check.

Set the area on a physical device so all its entities inherit it: lights, fans, sensors, switches, diagnostics and disabled endpoints stay together. Controls without a device, such as room-specific scene scripts, receive an explicit entity area. An area assignment does not add a light to any scene, expose it to voice assistants, change playback, or change its entity ID.

The Dining Room nook stays in **Dining Room**, as confirmed by Ryan on October 16, 2026. Kitchen presets also control it; those are separate facts. Dining Room and Maker Room keep their physical areas even though they have no dashboard tile. The Maker Room Roam belongs to Maker Room but remains outside the dashboard playback/join-all allowlist.

The portable Move remains unassigned. Its dashboard selection controls Outdoor lighting and shows outdoor weather. Shared infrastructure, whole-home controls and portable equipment are intentionally unassigned. Unidentified Sense loads remain **location unconfirmed**, per Ryan's instruction. The five named kitchen appliances are assigned to Kitchen. Both retired SHIELD players were removed; Bedroom Chromecast remains.

The unused legacy scenes `scene.scene_001_keypressed2x` and `scene.scene_002_keypressed2x` were removed after Ryan confirmed their retirement on October 16, 2026. They were orphaned registry entries with no remaining configured scene definitions. The catalog records them under Retired. The temporarily removed Outdoor cafe lights keep their desired Outdoor placement; assigning areas does not restore retired hardware or clear scene exclusions.

## Confirm or correct a location

1. Open a room in the [catalog](wiki-reference:rooms) and find the device's anchor entity.
2. In Home Assistant, open **Settings → Devices & services → Entities**, search that entity ID, then open its device. Confirm the device's area and check that its entities inherit it. Under **Settings → Areas, labels & zones**, browse the corresponding area's members.
3. If a physical location is wrong, update the device entry in `home-model/device-catalog.json`. Keep logical lighting areas in `devices.ts` and known hardware references in the product catalog consistent; tests check that agreement. Update `home-model/rooms.json` only when the dashboard's control mapping changes.
4. Run `just areas-audit` to see proposed metadata changes, then `just areas-apply --record-verification`. Unknown entities, unexpected associations and explicit entity-area overrides require review. These commands do not guess locations from names or remove retired devices automatically.
5. Review the affected wiki components and publish with `just wiki-deploy`.

The catalog separates desired placement from the **dated registry verification**. Verification totals include disabled entities; they do not prove that a device is online or physically in the stated room. A catalog change makes the previous verification visibly stale until checked again.

Room tables, dashboard mappings, device placements, cross-room presets, helper lists, hardware references, retirement records and verification comparisons are generated on every wiki build from their repository sources. The prose explains policy and confirmation decisions; it does not duplicate the full mapping. Normal successful deployments publish the wiki automatically; use `just wiki-deploy` for documentation-only updates.

Before any assignment batch, the tool saves private registry metadata and its plan under ignored `build/room-alignment/`. To undo a placement, use that plan's `from` area in Home Assistant's device/entity editor; a null value means unassigned. Reconcile the catalog to the correction before running the tool again. No restart or configuration deployment is needed for registry area edits.
