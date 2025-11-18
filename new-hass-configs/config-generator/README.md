# Home Assistant Configuration Generator

TypeScript-based configuration generator for Home Assistant. Provides type-safe, maintainable configuration with modern tooling support.

## Quick Start

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Generate YAML configs
npm run generate

# Or use the Justfile command from parent directory
cd .. && just generate
```

## Architecture

### Core Files

- **src/types.ts** - TypeScript type definitions for all config objects
- **src/devices.ts** - Device registry mapping logical names to HA entities
- **src/scenes.ts** - Scene definitions (desired states for devices)
- **src/automations.ts** - Automation rules (triggers + actions)
- **src/generate.ts** - Generator that converts TypeScript to YAML

### Workflow

1. Define devices in `devices.ts` (entity IDs, capabilities, events)
2. Define scenes in `scenes.ts` (reference devices by logical name)
3. Define automations in `automations.ts` (reference devices and scenes)
4. Run `npm run generate` to create YAML files
5. Generated files output to `../generated/`
6. Use `just check` and `just push` to deploy

## Type Safety Benefits

- **Compile-time validation** - Catch errors before deployment
- **IDE autocomplete** - IntelliSense for all config options
- **Refactoring support** - Rename devices/scenes safely
- **Documentation** - Types serve as inline documentation

## Migration from Legacy System

The config-generator replaces the Python MetaHassConfig tool and supports:

- Modern Z-Wave JS (vs deprecated Z-Wave Classic)
- Type-safe configuration
- Better tooling and IDE support
- Incremental migration from legacy configs

## Example: Adding a Scene

```typescript
// src/scenes.ts
export const scenes = {
  bedroom_romantic: {
    name: "Bedroom - Romantic",
    icon: "mdi:candle",
    lights: [
      {
        device: "bedroom_main", // Logical name from devices.ts
        brightness: 50,
        rgb_color: [255, 100, 100]
      }
    ]
  }
};
```

## Example: Adding an Automation

```typescript
// src/automations.ts
export const automations = {
  bedroom_switch_romantic: {
    alias: "Bedroom Switch - Triple Up → Romantic",
    trigger: {
      type: "zwave_js_scene",
      device: "bedroom_bedside_switch",
      event: "tripleUp"
    },
    action: {
      type: "scene",
      scene: "bedroom_romantic"
    }
  }
};
```

## Z-Wave JS Event Mapping

Z-Wave JS uses different event formats than Z-Wave Classic:

### Event Values (Dimmer 46203)
- `KeyPressed` - Single press
- `KeyPressed2x` - Double press
- `KeyPressed3x` - Triple press
- `KeyHeldDown` - Hold start
- `KeyReleased` - Hold end

### Device Configuration

```typescript
// src/devices.ts
switches: {
  bedroom_bedside_switch: {
    entity: "switch.bedroom_bedside",
    type: "zwave_dimmer_46203",
    device_id: "abc123...", // Get from HA device registry
    events: {
      doubleUp: {
        command_class_name: "Central Scene",
        property_key_name: "001",
        value: "KeyPressed2x"
      }
    }
  }
}
```

## Development

```bash
# Watch mode (auto-rebuild on changes)
npm run watch

# Clean build artifacts
npm run clean

# Full rebuild
npm run clean && npm run build
```

## Troubleshooting

### "Device not found" error
- Ensure device is defined in `devices.ts`
- Check logical name matches exactly

### "Scene not found" error
- Ensure scene is defined in `scenes.ts`
- Check scene key matches exactly

### Z-Wave automation not triggering
- Verify `device_id` is correct in device definition
- Check event mapping matches actual device events
- Monitor HA events: Developer Tools > Events > `zwave_js_value_notification`
