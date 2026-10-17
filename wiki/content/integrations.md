# Climate and fans

Home Assistant connects integrations to stable household entities. Not every integration is declared in YAML: some credentials and configuration are owned by Home Assistant’s UI and private storage.

## Climate and ESPHome fans

The documented Nest integration provides four thermostats through Google Device Access and Pub/Sub updates. Home Assistant owns the OAuth credentials. No repository automation automatically changes HVAC settings.

The Living Room thermostat’s `hvac_action` drives the external ESPHome heat-pump fans. That dependency is different from the Nest thermostat’s own fan timer. Before changing a fan automation, identify which fan and signal it controls.

Start with the thermostat state and then the ESPHome device connection. Preserve entity names when replacing a device; changing them silently can detach an automation.

## Configuration and recovery

The [Nest runbook](../../docs/operations/nest-integration.md) records the authorized integration and entity names. The [fan controller runbook](../../docs/operations/esphome-fancontrollers.md) owns controller inventory, firmware configuration, and onboarding.

Recover Home Assistant’s integration state and the relevant ESPHome configurations from their backups. Rebuilding an add-on alone does not recover an OAuth refresh token or device firmware configuration.
