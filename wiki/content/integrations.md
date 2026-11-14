# Climate and fans

Home Assistant connects integrations to stable household entities. Not every integration is declared in YAML: some credentials and configuration are owned by Home Assistant’s UI and private storage.

## Climate and ESPHome fans

The documented Nest integration provides four thermostats through Google Device Access and Pub/Sub updates. Home Assistant owns the OAuth credentials. No repository automation automatically changes HVAC settings.

The Living Room Nest starts the external ESPHome fans during heating or cooling. When a heat call ends and the Nest goes idle, each cabinet’s fans keep running while that cabinet is more than **1 °F warmer** than the seating area. Each cabinet shuts off independently. Home Assistant uses the Nest’s measured temperature if the seating-area sensor is unavailable. The thermostat’s own fan timer is a separate control.

Start with the thermostat state and then the ESPHome device connection. Preserve entity names when replacing a device; changing them silently can detach an automation.

### What the temperature readings represent

- The standalone sensor near the seats is the comfort reference. The Nest measures near an exterior door and supplies the HVAC cycle timing and setpoint as well as its own room temperature. Compare both measured temperatures to see whether those two locations track each other.
- Each controller measures inside its HVAC cabinet. The cabinet-to-room difference indicates whether there may be residual heat to circulate. To estimate heat delivered by the fans, measure discharge-air temperature relative to room air and the airflow. The 1 °F margin is a trial cutoff that leaves room for sensor and placement differences near equal temperatures.

### How to evaluate a heating cycle

1. Pull Home Assistant history for the room and cabinet temperatures, Nest `hvac_action` and setpoint, and the fan output states. Align the records by timestamp. For a comfort average or time within a temperature band, weight each available reading by the time until the next reading. Account for unavailable intervals and state how much of the window had readings. When a sensor has just been re-paired or moved, report its initial readings separately and state the settling interval used.
2. For each complete heat call, measure from the Nest’s `heating` → `idle` transition to each cabinet’s fan shutoff. Record the cabinet-to-room difference at shutoff and how the seating-area temperature changes through the idle period. The [fan controller runbook](../../docs/operations/esphome-fancontrollers.md#living-room-heat-pump-automation) lists the entities and the fallback behavior.
3. Compare several cycles with similar outdoor temperatures and the same setpoint and seating-area comfort. Use combined heat-pump and fan electricity to evaluate energy savings. Warmer cabinet readings or longer fan runtime alone cannot show whether the system used less energy.

On November 13, 2026, after the first 10 minutes of post-pairing readings, the seating area stayed within 1 °F of the Nest and within 1 °F of the 74 °F setpoint about 93% of the observed time. In the one complete cycle under the previous 3 °F rule, cabinet 2 ran for another 6 min 39 sec after the Nest went idle, and cabinet 1 ran for 11 min 37 sec. Both stopped with their cabinets about 2.6–2.7 °F warmer than the seating area. Those readings are the baseline for the 1 °F trial.

## Configuration and recovery

The [Nest runbook](../../docs/operations/nest-integration.md) records the authorized integration and entity names. The [fan controller runbook](../../docs/operations/esphome-fancontrollers.md) owns controller inventory, firmware configuration, and onboarding.

Recover Home Assistant’s integration state and the relevant ESPHome configurations from their backups. Rebuilding an add-on alone does not recover an OAuth refresh token or device firmware configuration.
