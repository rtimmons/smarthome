# Google Nest integration

This document records the non-secret operational state for the Google Nest integration. The integration is configured through Home Assistant's UI and stored in Home Assistant's `.storage` data; it is not declared in `configuration.yaml`.

## Current topology

The integration was rebuilt and verified on 2026-08-27.

| Component | Current value |
| --- | --- |
| Home Assistant entry | `300 Newark` |
| Google Cloud project | `newark-hass-integration` |
| OAuth client name | `Home Assistant Nest` |
| Device Access project | `hass-integration-300-ewr` (`7fb41b07-c100-49b6-b3a8-752d8b4ff97f`) |
| Pub/Sub topic | `projects/newark-hass-integration/topics/home-assistant-nest` |
| Pub/Sub subscription | `projects/newark-hass-integration/subscriptions/home-assistant-nest-sub` |

The OAuth client secret, Google refresh token, and Home Assistant application credential must remain in their respective secret stores. Do not copy them into this repository or diagnostic output.

Google Device Access is authorized for the four thermostats and their home/room metadata. The Pub/Sub topic and subscription provide event-driven updates to Home Assistant.

## Home Assistant entities

The devices are assigned to matching Home Assistant areas. Entity IDs were normalized after setup so automations and dashboards do not inherit the duplicated room names generated during initial discovery.

| Area | Climate entity | Temperature | Humidity | Fan timer timeout |
| --- | --- | --- | --- | --- |
| Bedroom | `climate.bedroom` | `sensor.bedroom_temperature` | `sensor.bedroom_humidity` | `sensor.bedroom_fan_timer_timeout` |
| Living Room | `climate.living_room` | `sensor.living_room_temperature` | `sensor.living_room_humidity` | `sensor.living_room_fan_timer_timeout` |
| Office | `climate.office` | `sensor.office_temperature` | `sensor.office_humidity` | `sensor.office_fan_timer_timeout` |
| Kitchen | `climate.kitchen` | `sensor.kitchen_temperature` | `sensor.kitchen_humidity` | `sensor.kitchen_fan_timer_timeout` |

The climate entities support heat, cool, heat/cool, off, fan on/off, and Eco preset control. No repository automation changes HVAC settings automatically.

## Verification

Use the repository-owned Home Assistant client rather than reading secrets from `.storage`:

```sh
just ha-state climate.bedroom
just ha-state climate.living_room
just ha-state climate.office
just ha-state climate.kitchen
```

Refresh the ignored local registry snapshots after device or entity changes:

```sh
just ha-inventory
```

Healthy climate entities should be available and include current temperature, humidity, target temperature, HVAC action, fan mode, and preset mode.

## Maintenance

- Reauthorize from **Settings → Devices & services → Nest** if Google revokes the grant or Home Assistant reports an authentication issue.
- Rotate the Home Assistant application credential if the OAuth client secret changes. Update the Device Access project to reference the same OAuth client before reauthorizing.
- If live updates stop but entity reads still work, verify that the Device Access project still publishes to the topic above and that the subscription still exists.
- Keep the OAuth redirect URI set to `https://my.home-assistant.io/redirect/oauth`.
- Preserve the concise entity IDs in this document if the integration is removed and re-added.

Official references: [Home Assistant Nest integration](https://www.home-assistant.io/integrations/nest/), [Google Device Access authorization](https://developers.google.com/nest/device-access/authorize), and [Google Device Access events](https://developers.google.com/nest/device-access/subscribe-to-events).
