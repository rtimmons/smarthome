# Climate and fans

Home Assistant connects integrations to stable household entities. Not every integration is declared in YAML: some credentials and configuration are owned by Home Assistant’s UI and private storage.

## Climate and ESPHome fans

The documented Nest integration provides four thermostats through Google Device Access and Pub/Sub updates. Home Assistant owns the OAuth credentials. No repository automation automatically changes HVAC settings.

The Living Room Nest starts the external ESPHome fans during heating or cooling. After heating, each cabinet's fans keep running until the cabinet is within 3 °F of the seating-area sensor. Home Assistant uses the Nest's room temperature when the seating-area sensor is unavailable. The Nest thermostat's own fan timer is a separate control.

Start with the thermostat state and then the ESPHome device connection. Preserve entity names when replacing a device; changing them silently can detach an automation.

## Configuration and recovery

The [Nest runbook](../../docs/operations/nest-integration.md) records the authorized integration and entity names. The [fan controller runbook](../../docs/operations/esphome-fancontrollers.md) owns controller inventory, firmware configuration, and onboarding.

Recover Home Assistant’s integration state and the relevant ESPHome configurations from their backups. Rebuilding an add-on alone does not recover an OAuth refresh token or device firmware configuration.
