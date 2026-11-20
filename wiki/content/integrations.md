# Climate and fans

Home Assistant connects integrations to stable household entities. Not every integration is declared in YAML: some credentials and configuration are owned by Home Assistant’s UI and private storage.

## Climate and ESPHome fans

The documented Nest integration provides four thermostats through Google Device Access and Pub/Sub updates. Home Assistant owns the OAuth credentials. Home Assistant maintains daily heating setpoints for all four Nests: Living Room, Bedroom, Kitchen, and Office.

The Living Room Nest starts the external ESPHome fans during heating or cooling. When a heat call ends and the Nest goes idle, each cabinet’s fans keep running while that cabinet is more than **1 °F warmer** than the seating area. Each cabinet shuts off independently. Home Assistant uses the Nest’s measured temperature if the seating-area sensor is unavailable. The thermostat’s own fan timer is a separate control.

Start with the thermostat state and then the ESPHome device connection. Preserve entity names when replacing a device; changing them silently can detach an automation.

### Nest heating schedules

Every day, in Eastern time, Home Assistant maintains these targets for **Living Room, Bedroom, Kitchen, and Office** while each thermostat is in Heat mode and outside Eco mode.

| Time | Nest target | Purpose |
| --- | --- | --- |
| 8 a.m.–10 p.m. | 73 °F | Start warming one hour before the 9 a.m. comfort window |
| 10 p.m.–8 a.m. | 72 °F | Overnight setback |

Open **Living Room Climate → Room schedules** for the four thermostats and an **Automatic setpoints** pause/resume control for each room. The existing Heating view retains the living-room control and sensor graphs. Pause a room's schedule before holding a manual target. While enabled, the automation restores its current target if a manual adjustment or an existing Nest program changes the setpoint. This reconciliation avoids competing schedule owners; it differs from the original boundary-only living-room trial. Off, cooling, and Eco modes take precedence. The current target is restored after startup, reconnection, return to Heat mode, exit from Eco, or re-enabling that room's schedule. A matching target skips the API write. Each room operates independently.

The package `new-hass-configs/packages/nest_heating_schedules.yaml` owns the four automations. It retains `automation.living_room_heating_schedule` and adds `automation.bedroom_heating_schedule`, `automation.kitchen_heating_schedule`, and `automation.office_heating_schedule`. The native dashboard sources live in `new-hass-configs/dashboards/`. Deploy the package and dashboard together from the repository root with `./wiki/run with-deployment --scope home-assistant-config -- just --justfile new-hass-configs/Justfile deploy living-room-dashboard`. The publisher backs up the existing dashboard under ignored `new-hass-configs/inventory_snapshots/dashboard-backups/` before updating its schedule card and Room schedules view.

The one-hour warm-up and one-degree setback are an initial trial. Evaluate the living-room knee-height sensor at 9 a.m. and through the 9 a.m.–10 p.m. comfort window, alongside panel energy and outdoor temperature. That sensor does not measure the other rooms; evaluate their Nest readings and occupant comfort separately. The Nest's target and the seating sensor's measured temperature describe different locations. The seating sensor held 72.0–72.5 °F overnight on November 17–18 with the Nest at 73 °F. The preceding ventilation period and sensor move affect comparisons across that evening.

The all-room rollout raises some previous Kitchen and Office targets, including their deeper native overnight setbacks. Compare total energy with the changed comfort targets in mind: a before/after panel comparison now combines schedule expansion and the living-room Heat Pump Balance change. The living-room cabinet fans continue to use their 1 °F residual-heat cutoff.

### Auxiliary heat and Heat Pump Balance

Read-only Nest web inspection on **November 19, 2026** found the following configuration. These settings belong to Nest and are not exposed or deployed by the Home Assistant SDM integration.

| Room | Equipment reported by Nest | Heat Pump Balance after review |
| --- | --- | --- |
| Living Room | Electric heat pump and electric auxiliary heat, AUX wire on W1 | **Max savings**, changed from Balanced |
| Bedroom | Electric heat pump and electric auxiliary heat, AUX wire on W1 | Balanced |
| Kitchen | Electric heat pump and electric auxiliary heat, AUX wire on W1 | Balanced |
| Office | Electric heat pump, no auxiliary wire or AUX stage reported | No Heat Pump Balance option |

The Living Room Nest's **Max savings** setting asks Nest to minimize auxiliary heat use; it can allow more compressor runtime and a slower warm-up. It does not change the 73/72 °F targets or disable auxiliary heat. Bedroom and Kitchen still report Balanced. Existing Nest Auto-Schedule was on only in Living Room; Early-On was on only in Office. Existing native programs remain in Nest, and the Home Assistant automations reconcile their setpoint changes while enabled. Pausing an automation lets the native Nest controls and program operate again.

Sense's **Mystery Heat** is a high-confidence candidate for the living-room auxiliary stage, not a separately metered AUX circuit. In the November 12–19 history, all 14 detections longer than five minutes began during living-room heating, and 13 ended within two minutes of that heat call ending. On November 19, the 72 °F maintenance call at 7:14–7:57 a.m. had no Mystery Heat, whereas the 8 a.m. change to 73 °F coincided with about 2.85 kW of Mystery Heat for roughly 48 minutes. Outdoor temperature was about 40 °F during both calls, and the other three Nests were idle. The detected load used about 2.2–2.3 kWh. This is evidence for auxiliary heat during recovery, not proof of the circuit's physical identity or a guaranteed savings estimate.

Use [Google's Heat Pump Balance guidance](https://support.google.com/googlehome/answer/9248719?hl=en) for the native setting. The [Google HVAC trait](https://developers.google.com/nest/device-access/traits/device/thermostat-hvac) reports only heating, cooling, or off, so Home Assistant cannot directly distinguish compressor and auxiliary stages. Sense cloud power updates also have minute-scale timing; compare complete calls rather than treating every timestamp as an exact relay transition.

### What the temperature readings represent

- The standalone sensor near the seats is the comfort reference. It moved from waist height to knee height by November 18, 2026. Treat its new position as a new comfort baseline and keep it fixed while evaluating the schedule. The Nest measures near an exterior door and supplies the HVAC cycle timing and setpoint as well as its own room temperature. Compare both measured temperatures to see whether those two locations track each other.
- Each controller measures inside its HVAC cabinet. The cabinet-to-room difference indicates whether there may be residual heat to circulate. To estimate heat delivered by the fans, measure discharge-air temperature relative to room air and the airflow. The 1 °F margin is a trial cutoff that leaves room for sensor and placement differences near equal temperatures.

### How to evaluate a heating cycle

1. Pull Home Assistant history for the room and cabinet temperatures, Nest `hvac_action` and setpoint, and the fan output states. Align the records by timestamp. For a comfort average or time within a temperature band, weight each available reading by the time until the next reading. Account for unavailable intervals and state how much of the window had readings. When a sensor has just been re-paired or moved, report its initial readings separately and state the settling interval used.
2. For each complete heat call, measure from the Nest’s `heating` → `idle` transition to each cabinet’s fan shutoff. Record the cabinet-to-room difference at shutoff and how the seating-area temperature changes through the idle period. The [fan controller runbook](../../docs/operations/esphome-fancontrollers.md#living-room-heat-pump-automation) lists the entities and the fallback behavior.
3. Compare several cycles with similar outdoor temperatures and the same setpoint and seating-area comfort. Use combined heat-pump and fan electricity to evaluate energy savings. Warmer cabinet readings or longer fan runtime alone cannot show whether the system used less energy.

On November 13, 2026, after the first 10 minutes of post-pairing readings, the seating area stayed within 1 °F of the Nest and within 1 °F of the 74 °F setpoint about 93% of the observed time. In the one complete cycle under the previous 3 °F rule, cabinet 2 ran for another 6 min 39 sec after the Nest went idle, and cabinet 1 ran for 11 min 37 sec. Both stopped with their cabinets about 2.6–2.7 °F warmer than the seating area. Those readings are the baseline for the 1 °F trial.

## Configuration and recovery

The [Nest runbook](../../docs/operations/nest-integration.md) records the authorized integration and entity names. The [fan controller runbook](../../docs/operations/esphome-fancontrollers.md) owns controller inventory, firmware configuration, and onboarding.

Recover Home Assistant’s integration state and the relevant ESPHome configurations from their backups. Rebuilding an add-on alone does not recover an OAuth refresh token or device firmware configuration.
