# Home Assistant Configuration Management

Modern TypeScript-based configuration management system for Home Assistant with safe deployment workflows.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Workflows](#workflows)
- [Bidirectional Sync](#bidirectional-sync)
- [TypeScript Generator Design](#typescript-generator-design)
- [Backup Strategy](#backup-strategy)

---

## Overview

This directory manages Home Assistant configuration using a modern TypeScript-based generator that serves as the single source of truth for Home Assistant. The system provides:

- **Type-safe configuration** - Catch errors before deployment
- **Modern Z-Wave JS support** - Compatible with current Home Assistant
- **Safe deployment** - Validation and automatic rollback on failure
- **Bidirectional sync** - Protects UI-created configurations from overwrites
- **Git-friendly** - Track high-level config, not generated YAML

### Current Status

- **Production**: Home Assistant at `homeassistant.local` (SSH port 22)
- **Source of truth**: TypeScript generator + manual overrides
- **Deployment flow**: `just generate`, `just check`, `just deploy`

---

## Architecture

```
new-hass-configs/
├── README.md                   # This file
├── Justfile                    # Deployment automation (fetch/check/push)
│
├── config-generator/           # TypeScript configuration generator
│   ├── src/
│   │   ├── types.ts           # Type definitions (devices, scenes, automations)
│   │   ├── devices.ts         # Device registry (entities, capabilities)
│   │   ├── scenes.ts          # Scene definitions (high-level)
│   │   ├── automations.ts     # Automation rules (high-level)
│   │   └── generate.ts        # Generator logic (TypeScript → YAML)
│   ├── package.json
│   └── tsconfig.json
│
├── generated/                  # Generated YAML (git-ignored)
│   ├── scenes.yaml            # Auto-generated scenes
│   └── automations.yaml       # Auto-generated automations
│
├── manual/                     # Hand-written configs (for exceptions)
│   ├── scenes.yaml            # Manual scenes not suitable for generator
│   └── automations.yaml       # Manual automations (webhooks, etc.)
│
├── scenes.yaml                # MERGED: generated + manual
├── automations.yaml           # MERGED: generated + manual
├── scripts.yaml               # Scripts
├── configuration.yaml         # Main Home Assistant config
├── secrets.yaml               # Secrets (git-ignored)
│
├── blueprints/                # Reusable automation blueprints
│   ├── automation/
│   └── script/
│
├── backups/                   # Timestamped config backups (git-ignored)
│   └── YYYYMMDD-HHMMSS/
└── inventory_snapshots/       # Device/entity inventories captured by iterate.sh
```

---

## Quick Start

### Prerequisites

- Passwordless SSH access to `homeassistant.local` on port 22
- `just` command runner installed
- Node.js 18+ (for TypeScript generator)

### Basic Commands

```bash
# Fetch current config from Home Assistant
just fetch

# Generate YAML from TypeScript sources
just generate

# Validate config and show diff (dry-run, no changes)
just check

# Deploy validated config to Home Assistant
just deploy

# Create timestamped backup
just backup

# List available backups
just backups

# Restore from backup
just restore <timestamp>
```

---

## Workflows

### Development Workflow

```bash
# 1. Fetch latest live config
just fetch

# 2. Edit TypeScript configuration
cd config-generator
vim src/scenes.ts

# 3. Generate YAML
just generate

# 4. Validate and preview changes
just check

# 5. Deploy to production (now includes sync protection)
just deploy
```

---

## Bidirectional Sync

The configuration system includes bidirectional sync protection to prevent accidental overwrites of UI-created content.

### Protected Deployment

```bash
# Standard deployment now includes automatic sync checking
just deploy
```

If UI-modified configurations are detected, deployment is blocked with resolution options.

### Handling Conflicts

```bash
# Option 1: Fetch UI changes into repository (recommended)
just fetch-config
git diff && git add . && git commit -m "Sync live HA changes"
just deploy

# Option 2: Force deploy (loses UI changes)
just deploy-force

# Option 3: Force deploy with backup
just deploy-force --backup

# Option 4: Manual reconciliation
just reconcile scenes.yaml
```

### Monitoring

```bash
# Check for configuration drift
just detect-changes

# Show detailed diff for specific files
just reconcile automations.yaml
```

> **📖 Complete Documentation**: See [Configuration Sync Guide](../docs/development/configuration-sync.md) for detailed usage, troubleshooting, and implementation details.

### Emergency Rollback

```bash
# List recent backups
just backups

# Restore specific backup
just restore 20250118-143022

# Or restore most recent
just restore latest
```

### Adding a New Scene

```typescript
// config-generator/src/scenes.ts
export const scenes = {
  // ... existing scenes ...

  bedroom_romantic: {
    name: "Bedroom - Romantic",
    lights: [
      {
        device: "bedroom_main",
        brightness: 50,
        rgb: [255, 100, 100]
      }
    ]
  }
}
```

```bash
just generate  # Generate YAML
just check     # Validate
just deploy    # Deploy
```

### Adding a New Automation

```typescript
// config-generator/src/automations.ts
export const automations = {
  // ... existing automations ...

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
}
```

### Debugging & Scene Snapshots

Use `iterate.sh` to capture before/after inventories around a scene application. This is helpful when validating new wiring or switch automations.

```bash
cd new-hass-configs
./iterate.sh  # runs just inventory, applies scene.guest_bathroom_high via hass-cli, runs inventory again
ls inventory_snapshots/2025*/  # view captured device/entity snapshots
```

Requirements:
- `just inventory` working (hass-cli configured for your Home Assistant instance)
- `hass-cli` installed locally and authenticated

---

## Naming Conventions & Dashboard Integration

### Room-Scene-Webhook Naming Convention

**CRITICAL**: Room names must match exactly across three systems for the dashboard scene buttons to work properly.

#### 1. Dashboard Room Names
- **Location**: `grid-dashboard/ExpressServer/src/public/js/config.js`
- **Format**: Proper case with spaces (e.g., "Living Room", "Office", "Guest Bathroom")
- **Example**:
  ```javascript
  rooms: [
    'Living Room',
    'Bedroom',
    'Kitchen',
    'Bathroom',
    'Office',
  ]
  ```

#### 2. Scene IDs
- **Location**: `config-generator/src/scenes.ts`
- **Format**: `{room}_{level}` (lowercase, spaces → underscores)
- **Levels**: `high`, `medium`, `low`, `off`
- **Example**: `living_room_high`, `office_medium`, `bathroom_off`

#### 3. Webhook IDs
- **Location**: `config-generator/src/automations.ts` (webhook triggers)
- **Format**: `scene_{room}_{level}` (lowercase, spaces → underscores)
- **Example**: `scene_living_room_high`, `scene_office_medium`

### Conversion Flow

```
Dashboard: "Living Room" button + Sun button (High)
    ↓ (Dashboard LightController converts to URL)
URL: /scenes/scene_living_room_high
    ↓ (Express server POSTs to Home Assistant webhook)
Webhook: scene_living_room_high
    ↓ (Home Assistant automation triggers scene)
Scene: scene.living_room_high
    ↓ (Scene applies light states)
Lights: Turn on at specified brightness
```

### Scene Levels

Each room should have **four standard scenes**:

| Level  | Button | Brightness | Use Case                        | Webhook? |
|--------|--------|------------|---------------------------------|----------|
| High   | ☀️ Sun | 255 (100%) | Daytime, active work            | ✅ Yes   |
| Medium | 🌘 Dim | 180 (70%)  | Evening, relaxation             | ✅ Yes   |
| Low    | -      | 50 (20%)   | Night light, minimal            | ❌ No    |
| Off    | 🌑 Moon| 0 (off)    | Leaving room, sleep             | ✅ Yes   |

**Note**: Only High, Medium, and Off are accessible from dashboard buttons. Low is available via physical switch automations.

### Adding a New Room

See detailed guide in [config-generator/README.md](config-generator/README.md) and [config-generator/TEMPLATE_NEW_ROOM.md](config-generator/TEMPLATE_NEW_ROOM.md).

**Quick steps:**
1. Add devices to `config-generator/src/devices.ts`
2. Add scenes to `config-generator/src/scenes.ts` (can use helper functions)
3. Add webhook automations to `config-generator/src/automations.ts` (can use helper functions)
4. Verify room in dashboard `config.js`
5. Run `just generate && just deploy`

**Example using helpers:**
```typescript
// scenes.ts
import { createStandardRoomScenes } from "./helpers";

export const scenes: SceneRegistry = {
  ...createStandardRoomScenes({
    roomDisplayName: "Bedroom",
    roomId: "bedroom",
    devices: ["bedroom_ceiling", "bedroom_nightstand"]
  }),
};

// automations.ts
import { createStandardWebhooks } from "./helpers";

export const automations: AutomationRegistry = {
  ...createStandardWebhooks({
    roomDisplayName: "Bedroom",
    roomId: "bedroom"
  }),
};
```

### Dashboard Scene Buttons

Dashboard displays three scene buttons per room at grid coordinates `y:2, x:7-9`:

```javascript
// From grid-dashboard config.js
{ emoji: 'Sun',  onPress: {action: 'Lights.Scene', args: ['$room','High']} },   // x:7
{ emoji: 'Dim',  onPress: {action: 'Lights.Scene', args: ['$room','Medium']} }, // x:8
{ emoji: 'Moon', onPress: {action: 'Lights.Scene', args: ['$room','Off']} },    // x:9
```

When pressed, these buttons:
1. Replace `$room` with current room name
2. POST to `/scenes/scene_{room}_{level}`
3. Express server forwards to Home Assistant webhook
4. Webhook automation triggers the corresponding scene

---

## TypeScript Generator Design

### Core Types

```typescript
// config-generator/src/types.ts

export type DeviceType =
  | "rgbw_light"
  | "dimmer_light"
  | "color_light"
  | "outlet"
  | "zwave_dimmer_46203"
  | "zwave_zen31_rgbw";

export type ZWaveEvent =
  | "singleUp"
  | "singleDown"
  | "doubleUp"
  | "doubleDown"
  | "tripleUp"
  | "tripleDown"
  | "holdStart"
  | "holdEnd";

export interface Device {
  entity: string;
  type: DeviceType;
  capabilities?: string[];
  events?: Record<ZWaveEvent, { scene_id: number; scene_data: number }>;
}

export interface LightState {
  device: string;
  state?: "on" | "off";
  brightness?: number;
  rgb?: [number, number, number];
  kelvin?: number;
}

export interface Scene {
  name: string;
  lights: LightState[];
}

export interface Automation {
  alias: string;
  trigger: Trigger;
  action: Action;
  condition?: Condition;
}
```

### Generator Logic

```typescript
// config-generator/src/generate.ts

import * as yaml from "yaml";
import { devices } from "./devices";
import { scenes } from "./scenes";
import { automations } from "./automations";

export function generateScenes(): string {
  const output = [];

  for (const [id, scene] of Object.entries(scenes)) {
    const entities = {};

    for (const light of scene.lights) {
      const device = devices.lights[light.device];
      entities[device.entity] = {
        state: light.state || "on",
        ...(light.brightness && { brightness: light.brightness }),
        ...(light.rgb && { rgb_color: light.rgb }),
      };
    }

    output.push({
      id: id,
      name: scene.name,
      entities
    });
  }

  return yaml.stringify(output);
}

export function generateAutomations(): string {
  // Convert automations to Home Assistant YAML format
  // Handle Z-Wave JS triggers, scene actions, etc.
}
```

### Build & Generate

```bash
cd config-generator
npm install
npm run build
npm run generate  # Outputs to ../generated/
```

### Integration with Justfile

```bash
# Add to Justfile
generate:
    cd config-generator && npm run generate
    cat generated/scenes.yaml manual/scenes.yaml > scenes.yaml
    cat generated/automations.yaml manual/automations.yaml > automations.yaml
```

---

## Backup Strategy

### Automatic Backups

- Run before every `just deploy`
- Stored locally in `backups/` directory
- Timestamped: `backups/YYYYMMDD-HHMMSS/`
- Includes full `/config/` directory
- Retained for 30 days (configurable)

### Backup Contents

Each backup includes:
- `automations.yaml`
- `scenes.yaml`
- `scripts.yaml`
- `configuration.yaml`
- All YAML/JSON/shell scripts
- Excludes: `.storage/`, `secrets.yaml`, `*.db`, logs

### Manual Backups

```bash
# Create manual backup
just backup

# Backup with description
just backup "before-migration-phase-3"
```

### Restore Process

```bash
# List backups
just backups

# Restore specific backup
just restore 20250118-143022

# Restore with validation
just restore 20250118-143022 --check
```

### Emergency Recovery

If Home Assistant fails to start after `just deploy`:

1. SSH into Home Assistant: `ssh root@homeassistant.local`
2. Check logs: `ha core logs`
3. Restore from remote backup: `rsync -a /tmp/hass-config-backup/ /config/`
4. Restart: `ha core restart`

**SSH System Control**: The `ha` command provides comprehensive system management:
- **Device discovery**: Entity registry at `/config/.storage/core.entity_registry`
- **System control**: `ha core restart`, `ha core info`, `ha core check`
- **Logs**: `ha core logs`, `ha supervisor logs`
- **Backups**: `ha backups list`, `ha backups new --name "backup-name"`
- **Add-ons**: `ha addons list`, `ha addons info addon-name`

Or use local backups:

```bash
just restore latest
```

---

## Development Notes

### Z-Wave JS Event Mapping

Z-Wave JS uses different event formats than Z-Wave Classic:

**Old (Z-Wave Classic):**
```yaml
trigger:
  platform: event
  event_type: zwave.scene_activated
  event_data:
    entity_id: zwave.bedroom_switch
    scene_id: 1
    scene_data: 7860
```

**New (Z-Wave JS):**
```yaml
trigger:
  platform: event
  event_type: zwave_js_value_notification
  event_data:
    device_id: <device_id>
    command_class_name: "Central Scene"
    property_key_name: "001"
    value: "KeyPressed2x"
```

**Event Value Mappings (Dimmer 46203):**
- `KeyPressed` - Single press
- `KeyPressed2x` - Double press
- `KeyPressed3x` - Triple press
- `KeyHeldDown` - Hold start
- `KeyReleased` - Hold end

### Device ID Resolution

Z-Wave JS uses device IDs instead of entity IDs for triggers. The generator must:

1. Look up device ID from entity ID
2. Use Home Assistant API or `.storage/core.device_registry`
3. Cache device IDs in `devices.ts`

### Testing Strategy

```bash
# Validate generated YAML syntax
just generate
just check

# Test specific scene on HA
just deploy
# Then in HA UI: Developer Tools > Services > scene.turn_on

# Test automation trigger
# Physically press switch, check HA logs
```

---

## Troubleshooting

### `just check` fails validation

1. Check YAML syntax: `yamllint scenes.yaml`
2. Review Home Assistant logs on server
3. Validate entity IDs exist in HA
4. Check for duplicate IDs

### `just deploy` restarts but scenes don't work

1. Verify entity IDs match current HA installation
2. Check device capabilities (RGBW vs dimmer)
3. Review HA logs for errors
4. Test scene manually in HA UI

### Z-Wave automations not triggering

1. Check device ID is correct
2. Verify Z-Wave JS integration is active
3. Monitor HA events: Developer Tools > Events > `zwave_js_value_notification`
4. Confirm Central Scene command class is supported

### SSH connection fails

1. Verify Home Assistant is running: `ping homeassistant.local`
2. Check SSH key is added: `ssh-add -l`
3. Test manual connection: `ssh -p 22 root@homeassistant.local`
4. Check Home Assistant SSH add-on is installed

---

## Notes

- The legacy `HomeAssistantConfig/` and `MetaHassConfig/` directories have been removed; the TypeScript generator plus manual overrides are the active source of truth.
- `just generate`, `just check`, and `just deploy` remain the supported workflow, with `just backup`/`just restore` available for safety.
