# Dashboard and controls

The [room and device catalog](wiki-reference:rooms) shows physical areas, Sonos players, lighting families and temperature sources together. See [Rooms and device locations](rooms.md) to confirm assignments and understand cross-room presets.

The Grid Dashboard is the household interface for room lighting, Sonos shortcuts, and the LED Grid Wall. Open it from Home Assistant’s sidebar so Home Assistant manages the session.

## What happens when you press a control

The browser talks to the Grid Dashboard server. Lighting requests go through Home Assistant and the generated fast-scene scripts. Sonos requests go through the separate Sonos API. The wall uses its dedicated LEDGrid endpoint at the reserved address `192.168.1.98:5000`.

The dashboard, Sonos API, and Home Assistant use the same names for fixed rooms: Bathroom, Closet, Bedroom, Patio, Kitchen, Living Room, Guest Bathroom, and Office. Home Assistant calls physical rooms **areas**; its geographic zones and Sonos playback groups have separate purposes. The old Main Bathroom and Main Closet names remain voice aliases.

The speaker formerly called Move is permanently assigned to **Patio** and now uses Patio as its Sonos, Home Assistant and dashboard name. Saved Move dashboard selections become Patio on reload. Patio replaces the former Outdoor area, including its lights; the stable `outdoor` area ID and lighting routes remain, and the Patio selection still shows outdoor weather. Dining Room and Maker Room remain valid Home Assistant areas without dashboard selections. Grouping speakers for playback never changes their physical areas.

The shared definition in `home-model/rooms.json` connects each selection to its area, Sonos player, lighting scene family, temperature source, and icon. Both dashboard layouts and the Sonos allowlist are built from it. Lighting still uses the generated fast-scene scripts, including their pacing, device exclusions, and smart-light power protections; area membership does not automatically expand scene targets.

## Daily use and troubleshooting

Choose the intended room before changing a scene or music group. If the whole dashboard is unavailable, check Home Assistant access and the add-on first. If only music fails, inspect Sonos API health. If only the wall fails, check that device’s reserved address and power.

Avoid repeated scene presses as a generic repair: the scene engine already paces Z-Wave traffic and reconciles overlapping intent. If a control works in Home Assistant but fails in the dashboard, preserve that comparison for the maintainer.

## Configuration and recovery

UI and server sources live under `grid-dashboard/ExpressServer`; add-on network and dependency declarations live in its manifest. The LED Grid Wall uses its installed native Home Assistant integration; the repository package supplies the compatibility and fast-scene scripts. Keep that native package when deploying: the former template/REST package would duplicate its entities. Living room scene behavior is described in the [lighting guide](lighting.md). Deploy through the root recipes, and use the [maintenance guide](maintenance.md) for validation and recovery. Restore application configuration from the appropriate Home Assistant backup rather than changing device addresses to match a stale bookmark.

After editing the shared room definition, run `just rooms-generate`, test both Grid Dashboard and Sonos API, and deploy both services. `just rooms-check` detects stale generated definitions. `just rooms-audit` compares live area names and fixed-speaker assignments and checks known legacy areas for members and references. `just rooms-apply` aligns known names and preserves existing IDs and aliases. Its optional `--remove-empty-legacy` flag removes only explicitly listed legacy areas that have no devices, no entities (including disabled ones), and no detected stored configuration references. It saves private area recovery metadata before changes. These are explicit maintenance operations; there is no automatic name synchronization from Sonos.

See [lighting](lighting.md), [audio](audio.md), and the [dashboard contributor guide](../../grid-dashboard/AGENTS.md).
