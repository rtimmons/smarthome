# Dashboard and controls

The Grid Dashboard is the household interface for room lighting, Sonos shortcuts, and the LED Grid Wall. Open it from Home Assistant’s sidebar so Home Assistant manages the session.

## What happens when you press a control

The browser talks to the Grid Dashboard server. Lighting requests go through Home Assistant and the generated fast-scene scripts. Sonos requests go through the separate Sonos API. The wall uses its dedicated LEDGrid endpoint at the reserved address `192.168.1.98:5000`.

The dashboard’s room labels must agree with the lighting scene and automation model. Changing one label alone can disconnect the visible control from its target.

## Daily use and troubleshooting

Choose the intended room before changing a scene or music group. If the whole dashboard is unavailable, check Home Assistant access and the add-on first. If only music fails, inspect Sonos API health. If only the wall fails, check that device’s reserved address and power.

Avoid repeated scene presses as a generic repair: the scene engine already paces Z-Wave traffic and reconciles overlapping intent. If a control works in Home Assistant but fails in the dashboard, preserve that comparison for the maintainer.

## Configuration and recovery

UI and server sources live under `grid-dashboard/ExpressServer`; add-on network and dependency declarations live in its manifest. The LED Grid Wall integration is in the Home Assistant packages. Deploy through the root recipes, and use the [maintenance guide](maintenance.md) for validation and recovery. Restore application configuration from the appropriate Home Assistant backup rather than changing device addresses to match a stale bookmark.

See [lighting](lighting.md), [audio](audio.md), and the [dashboard contributor guide](../../grid-dashboard/AGENTS.md).
