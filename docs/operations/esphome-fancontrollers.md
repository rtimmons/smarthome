# ESPHome Fan Controllers

Operational notes for the ESPHome-based multi-fan controller boards installed in Home Assistant.

## Current Deployment

The fan controllers are ESPHome devices connected directly to Home Assistant through the ESPHome native API on port `6053`. They are not MQTT devices and are not referenced by generated scene config. A checked-in manual automation controls the two living-room boards from the Living Room Nest's active HVAC state.

| HA device name | Area | Web UI | ESPHome device name | MAC |
| --- | --- | --- | --- | --- |
| `fancontroller 1` | `living_room` | `http://192.168.1.238:80` | `fancontroller-r3-1-8b11b8` | `90:e5:b1:8b:11:b8` |
| `fancontroller 2` | `living_room` | `http://192.168.1.52:80` | `fancontroller-r3-1-8b12ee` | `90:e5:b1:8b:12:ee` |
| `fancontroller 3` | `bedroom` | `http://192.168.1.49:80` | `fancontroller-r3-1-8b12e0` | `90:e5:b1:8b:12:e0` |

The live ESPHome source is on the Home Assistant host:

```text
/config/esphome/config.yaml
```

An archived copy exists at:

```text
/config/esphome/archive/fancontroller-rev31-esp32s2.yaml
```

`new-hass-configs` intentionally protects `/config/esphome/**` during fetch/deploy, so these ESPHome YAML files are not part of normal Home Assistant config sync. Do not paste Wi-Fi credentials from live ESPHome YAML into git.

## Firmware Pattern

The same firmware/config is used for all boards:

```yaml
esphome:
  name: fancontroller-r3-1
  friendly_name: fancontroller
  name_add_mac_suffix: true
```

`name_add_mac_suffix: true` gives each board a stable unique device name based on its MAC suffix, for example `fancontroller-r3-1-8b11b8`.

The boards report as:

- Manufacturer: `Espressif`
- Model: `esp32-s2-saola-1`
- ESPHome version observed on existing boards: `2025.12.5`

Board-level product identity is tracked in [`zwave-product-catalog.json`](zwave-product-catalog.json) under `espressif-esp32-s2-saola-1-fancontroller-r3-1`. Home Assistant reports the Espressif development board target; it does not prove the vendor/model of the assembled fan controller PCB.

## Exposed Entities

Each controller exposes the same entity set. For controller 1, the active entities are:

```text
fan.fancontroller_1_fan_1
fan.fancontroller_1_fan_2
fan.fancontroller_1_fan_3
fan.fancontroller_1_fan_4
sensor.fancontroller_1_fan_1_speed
sensor.fancontroller_1_fan_2_speed
sensor.fancontroller_1_fan_3_speed
sensor.fancontroller_1_fan_4_speed
sensor.fancontroller_1_temperature
sensor.fancontroller_1_humidity
binary_sensor.fancontroller_1_usr1
binary_sensor.fancontroller_1_usr2
binary_sensor.fancontroller_1_usr3
light.fancontroller_1_neopixel_light
```

Controllers 2 and 3 use the same pattern with `fancontroller_2` and `fancontroller_3`.

## Living Room Heat Pump Automation

`Living Room Heat Pump Fans - Follow Nest` (`living_room_heat_pump_fans_follow_nest`) in `new-hass-configs/manual/automations.yaml` controls all four outputs on both living-room boards. It turns them on only while `climate.living_room` reports `hvac_action` as `heating` or `cooling`, and turns them off for idle, off, or unavailable states.

| Controller | Automation targets |
| --- | --- |
| `fancontroller 1` | `fan.fancontroller_1_fan_1`, `fan.fancontroller_1_fan_2`, `fan.fancontroller_1_fan_3`, `fan.fancontroller_1_fan_4` |
| `fancontroller 2` | `fan.fancontroller_2_fan_1`, `fan.fancontroller_2_fan_2`, `fan.fancontroller_2_fan_3`, `fan.fancontroller_2_fan_4` |

The automation also reconciles on Home Assistant startup and turns the fans back off if ESPHome restores an output to on while the Nest is inactive. `fan.turn_on` deliberately omits a percentage so each output keeps its configured/restored speed.

## Hardware Mapping

| Function | GPIO |
| --- | --- |
| Fan 1 PWM | `GPIO12` |
| Fan 2 PWM | `GPIO13` |
| Fan 3 PWM | `GPIO14` |
| Fan 4 PWM | `GPIO15` |
| Fan 1 tach/RPM | `GPIO16` |
| Fan 2 tach/RPM | `GPIO17` |
| Fan 3 tach/RPM | `GPIO18` |
| Fan 4 tach/RPM | `GPIO21` |
| I2C SDA | `GPIO33` |
| I2C SCL | `GPIO34` |
| User button 1 | `GPIO38` |
| User button 2 | `GPIO37` |
| User button 3 | `GPIO36` |
| Board/status LEDs | `GPIO01` |
| NeoPixel header | `GPIO42` |

The RPM sensors use pulse counters with `multiply: 0.5` because the fans output two pulses per revolution.

## Adding More Controllers

1. Open Home Assistant > ESPHome Device Builder.
2. Use the existing `/config/esphome/config.yaml` as the source config.
3. Flash the new board with that same config.
4. Let it join Wi-Fi and appear through ESPHome discovery.
5. Add the discovered ESPHome integration in Home Assistant if prompted.
6. Rename the HA device to the next sequence, such as `fancontroller 4`.
7. Let Home Assistant rename entities when prompted so the entity names follow the established pattern.
8. Assign the device to the correct HA area after identifying the physical board.

Because the firmware uses `name_add_mac_suffix`, do not manually change `esphome.name` per board unless intentionally breaking the shared-firmware pattern.

## First-Boot Behavior

On first boot, the firmware initializes all four fan outputs to 50% after a 5-second delay, then records that initialization in a restored global flag. After that, fan entities use `RESTORE_DEFAULT_ON`.

Practical implications:

- Test with fans connected or be ready for outputs to spin.
- Do not assume a newly flashed controller will remain off after power-up.
- If a board is reflashed or its persistent storage is cleared, first-boot initialization may run again.

## Useful Inspection Commands

```bash
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local ls -la /config/esphome
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local cat /config/esphome/config.yaml
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local cat /config/.storage/core.device_registry
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local cat /config/.storage/core.entity_registry
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local cat /config/.storage/core.config_entries
ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local ha addons info 5c53de3b_esphome
```

The ESPHome add-on slug is `5c53de3b_esphome`. As of the last inspection, the add-on was running with version `2026.5.3` and had `2026.6.4` available.
