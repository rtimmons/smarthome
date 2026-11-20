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

The climate entities support heat, cool, heat/cool, off, fan on/off, and Eco preset control. The Living Room Nest's `hvac_action` attribute starts the external ESPHome heat-pump fans. After a heat call, each cabinet's temperature determines how long its fans keep running. See [`esphome-fancontrollers.md`](esphome-fancontrollers.md).

## Heating schedules and auxiliary heat

`new-hass-configs/packages/nest_heating_schedules.yaml` defines four independent automations: `automation.living_room_heating_schedule`, `automation.bedroom_heating_schedule`, `automation.kitchen_heating_schedule`, and `automation.office_heating_schedule`. Each maintains its corresponding thermostat at 73 °F from 08:00 to 22:00 and 60 °F overnight in Home Assistant's `America/New_York` timezone, every day. The 60 °F overnight trial begins November 19, 2026; the initial overnight target was 72 °F.

Each automation reconciles on a boundary, startup, return to Heat mode or connectivity, temperature or preset changes, and re-enabling. Heat mode and a non-Eco preset are required. Matching targets skip the API call. While enabled, the schedule restores its target after native Nest program or manual setpoint changes. Pause **Automatic setpoints** for that room before a manual hold; Off, cooling, and Eco take precedence. Room failures and pause controls are independent.

**Living Room Climate → Room schedules** contains four thermostats and schedule switches. The Heating view retains the living-room graphs and schedule control. Dashboard sources are in `new-hass-configs/dashboards/`; publish through `just --justfile new-hass-configs/Justfile living-room-dashboard`. The [wiki climate guide](../../wiki/content/integrations.md#nest-heating-schedules) includes the combined configuration/dashboard deployment command and comfort/energy methodology.

Native Nest settings were inspected on November 19, 2026. Living Room, Bedroom, and Kitchen report electric auxiliary heat wired to W1. Living Room Heat Pump Balance was changed from Balanced to **Max savings**; Bedroom and Kitchen report Balanced. Office reports a heat pump without an AUX wire/stage and has no Heat Pump Balance option. These are Nest-owned settings, outside the SDM API and Git deployment. The [wiki auxiliary-heat explanation](../../wiki/content/integrations.md#auxiliary-heat-and-heat-pump-balance) records the dated inventory and evidence connecting Sense's Mystery Heat to living-room recovery. The circuit mapping remains an inference.

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
