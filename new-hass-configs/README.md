# Home Assistant Configuration Management

Modern TypeScript-based configuration management system for Home Assistant with safe deployment workflows.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Workflows](#workflows)
- [Migration Plan](#migration-plan)
- [TypeScript Generator Design](#typescript-generator-design)
- [Backup Strategy](#backup-strategy)
- [Legacy Systems](#legacy-systems)

---

## Overview

This directory manages Home Assistant configuration using a modern TypeScript-based generator that replaces the legacy Python MetaHassConfig tool. The system provides:

- **Type-safe configuration** - Catch errors before deployment
- **Modern Z-Wave JS support** - Compatible with current Home Assistant
- **Incremental migration** - Gradual transition from legacy configs
- **Safe deployment** - Validation and automatic rollback on failure
- **Git-friendly** - Track high-level config, not generated YAML

### Current Status

- **Production**: Home Assistant at `homeassistant.local` (SSH port 22)
- **Migration**: Transitioning from legacy MetaHassConfig (40+ scenes, 88+ automations)
- **New system**: TypeScript generator (in development)

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
│
├── HomeAssistantConfig/       # LEGACY: Old configs (being phased out)
│   ├── metaconfig.yaml        # Old meta-configuration
│   └── ...
│
└── MetaHassConfig/            # LEGACY: Old Python generator (deprecated)
    └── ...
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
just push

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

# 5. Deploy to production
just push
```

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
just push      # Deploy
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

---

## Migration Plan

### Phase 1: Setup & Backup ✓ (COMPLETED)

**Goals:**
- Set up comprehensive backup system
- Create TypeScript generator scaffolding
- Verify fetch/check/push workflow

**Tasks:**
- [x] Document current architecture
- [x] Add `just backup` / `just restore` commands
- [x] Initialize TypeScript project (`config-generator/`)
- [x] Create base types (`types.ts`)
- [x] Test backup/restore workflow

**Completed:**
- Added `just backup`, `just backups`, `just restore` commands to Justfile
- Created TypeScript project with full type definitions
- Implemented generator logic (TypeScript → YAML)
- Added `just generate` command for config generation
- Created directory structure (generated/, manual/, backups/)
- Configured .gitignore for new workflow
- Verified TypeScript compilation and generator functionality
- Confirmed Home Assistant server connectivity

### Phase 2: Device Registry ✓ (COMPLETED)

**Goals:**
- Map old device names → new Z-Wave JS device names
- Document Z-Wave device event mappings
- Create device type definitions

**Tasks:**
- [x] Fetch current live config with new device names
- [x] Create TypeScript device registry (`devices.ts`)
- [x] Map old metaconfig entities → new entities
- [x] Document Z-Wave JS event format (scene_id, scene_data)
- [x] Create device capability types (dimmer, RGBW, outlet, etc.)

**Completed:**
- Fetched current Home Assistant configuration
- Mapped all office devices (5 lights, 1 outlet, 1 Z-Wave switch)
- Created 2 scenes (office_toggle_doubleup, office_toggle_doubledown)
- Created 2 automations (Z-Wave switch double-tap triggers)
- Successfully generated valid YAML from TypeScript
- Verified generator produces Home Assistant-compatible configuration

**Example Output:**
```typescript
// config-generator/src/devices.ts
export const devices = {
  lights: {
    bedroom_main: {
      entity: "light.bedroom_ceiling_rgbw",
      type: "rgbw",
      capabilities: ["brightness", "color"]
    },
    office_main: {
      entity: "light.office_ceiling",
      type: "dimmer",
      capabilities: ["brightness"]
    }
  },
  switches: {
    bedroom_bedside: {
      entity: "switch.bedroom_bedside_switch",
      type: "zwave_dimmer_46203",
      events: {
        doubleUp: { scene_id: 1, scene_data: 7860 },
        doubleDown: { scene_id: 2, scene_data: 7860 }
      }
    }
  }
}
```

### Phase 3: Migrate Scenes (Gradual)

**Goals:**
- Convert metaconfig scenes → TypeScript definitions
- Generate scenes.yaml
- Deploy incrementally (5-10 scenes at a time)

**Tasks:**
- [ ] Create scene type definitions
- [ ] Convert bedroom scenes (high/medium/low/off)
- [ ] Generate & deploy bedroom scenes
- [ ] Test bedroom scenes work correctly
- [ ] Convert office scenes
- [ ] Convert kitchen/living scenes
- [ ] Convert bathroom scenes
- [ ] Convert all remaining scenes

**Migration Example:**

Old metaconfig.yaml:
```yaml
scenes:
  scene_bedroom_high:
    bedroom_main: hue_high
    bedroom_accent: hue_medium
```

New TypeScript:
```typescript
export const scenes = {
  bedroom_high: {
    name: "Bedroom - High",
    lights: [
      { device: "bedroom_main", brightness: 255, rgb: [255, 255, 255] },
      { device: "bedroom_accent", brightness: 180, rgb: [255, 200, 150] }
    ]
  }
}
```

### Phase 4: Migrate Automations (Gradual)

**Goals:**
- Convert Z-Wave switch automations (most complex)
- Convert webhook automations (Siri, etc.)
- Convert timer automations
- Deploy incrementally

**Tasks:**
- [ ] Create automation type definitions
- [ ] Implement Z-Wave JS trigger generator
- [ ] Convert bedroom switch automations
- [ ] Test bedroom automations
- [ ] Convert office switch automations
- [ ] Convert kitchen/living switch automations
- [ ] Convert webhook automations (Siri, Flic)
- [ ] Convert timer automations
- [ ] Convert all remaining automations

**Migration Example:**

Old metaconfig.yaml:
```yaml
entities:
  bedroom_switch_bedside:
    type: dimmer switch 46203
    on_up_double: scene_bedroom_high
    on_down_double: scene_bedroom_off
```

Old generated automation (Z-Wave Classic):
```yaml
- alias: bedroom_switch_bedside on_up_double
  trigger:
    platform: event
    event_type: zwave.scene_activated
    event_data:
      entity_id: zwave.bedroom_switch_bedside
      scene_id: 1
      scene_data: 7860
  action:
    service: scene.turn_on
    entity_id: scene.bedroom_high
```

New TypeScript:
```typescript
export const automations = {
  bedroom_switch_doubleup: {
    alias: "Bedroom Switch - Double Up → High",
    trigger: {
      type: "zwave_js_scene",
      device: "bedroom_bedside_switch",
      event: "doubleUp"
    },
    action: {
      type: "scene",
      scene: "bedroom_high"
    }
  }
}
```

New generated automation (Z-Wave JS):
```yaml
- alias: Bedroom Switch - Double Up → High
  trigger:
    platform: event
    event_type: zwave_js_value_notification
    event_data:
      device_id: <device_id>
      command_class_name: "Central Scene"
      property_key_name: "001"
      value: "KeyPressed2x"
  action:
    service: scene.turn_on
    target:
      entity_id: scene.bedroom_high
```

### Phase 5: Cleanup

**Goals:**
- Remove legacy Python MetaHassConfig
- Archive old configs
- Update documentation

**Tasks:**
- [ ] Archive `HomeAssistantConfig/` directory
- [ ] Remove `MetaHassConfig/` Python tool
- [ ] Update main `CLAUDE.md` with new workflow
- [ ] Document TypeScript generator usage
- [ ] Clean up git history (optional)

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

- Run before every `just push`
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

If Home Assistant fails to start after `just push`:

1. SSH into Home Assistant: `ssh root@homeassistant.local`
2. Check logs: `ha core logs`
3. Restore from remote backup: `rsync -a /tmp/hass-config-backup/ /config/`
4. Restart: `ha core restart`

Or use local backups:

```bash
just restore latest
```

---

## Legacy Systems

### MetaHassConfig (Deprecated)

**Location:** `MetaHassConfig/`

**Purpose:** Python-based configuration generator (pre-Z-Wave JS)

**Usage (DO NOT USE):**
```bash
cd MetaHassConfig
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py develop
hassmetagen ../HomeAssistantConfig/metaconfig.yaml
```

**Status:** Being replaced by TypeScript generator

### Old Configs (Legacy)

**Location:** `HomeAssistantConfig/`

**Contains:**
- Old `metaconfig.yaml` (217 entities, 40+ scenes)
- Generated `automations.yaml` (88 automations)
- Z-Wave Classic device configs

**Status:** Reference only, will be archived after migration

### Key Differences: Old vs New

| Aspect | Old (MetaHassConfig) | New (TypeScript) |
|--------|---------------------|------------------|
| Language | Python 2.7 | TypeScript |
| Z-Wave | Classic (deprecated) | Z-Wave JS |
| Event format | `zwave.scene_activated` | `zwave_js_value_notification` |
| Type safety | None | Full TypeScript types |
| Validation | Runtime only | Compile-time + runtime |
| Tooling | Basic | Modern IDE support |
| Testability | Difficult | Easy (Jest, etc.) |

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
just push
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

### `just push` restarts but scenes don't work

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

## Next Steps

### Immediate (Phase 1)
1. Add backup/restore commands to Justfile
2. Initialize TypeScript project structure
3. Create base type definitions
4. Test backup/restore workflow

### Short-term (Phase 2-3)
1. Map old → new device names
2. Implement scene generator
3. Migrate 5-10 test scenes
4. Validate scene functionality

### Long-term (Phase 4-5)
1. Implement automation generator
2. Migrate all automations
3. Clean up legacy code
4. Document new workflow

---

## References

- [Home Assistant Configuration](https://www.home-assistant.io/docs/configuration/)
- [Z-Wave JS Integration](https://www.home-assistant.io/integrations/zwave_js/)
- [Scene Documentation](https://www.home-assistant.io/integrations/scene/)
- [Automation Triggers](https://www.home-assistant.io/docs/automation/trigger/)
- [Just Command Runner](https://github.com/casey/just)

---

**Last Updated:** 2025-11-18
**Status:** Phase 1 Complete ✓ | Phase 2 Complete ✓ | Ready for Phase 3 (Scene Migration)
**Contact:** See main repository README

## Session Summary (2025-11-18)

### Phase 1 - Setup & Backup (COMPLETED)

Successfully established the foundation for the new TypeScript-based configuration system:

- **Backup System:** Full backup/restore workflow with timestamped snapshots and safety rollback
- **TypeScript Generator:** Type-safe configuration generator with complete type definitions
- **Build Pipeline:** Automated generation with `just generate` command
- **Directory Structure:** Organized separation of generated, manual, and backup configs
- **Documentation:** Comprehensive README and inline documentation

### Phase 2 - Device Registry (COMPLETED)

Successfully mapped current Home Assistant configuration to TypeScript:

- **Device Mapping:** Mapped all office devices (5 lights, 1 outlet, 1 Z-Wave switch)
- **Scene Migration:** Migrated 2 office scenes from live HA config
- **Automation Migration:** Migrated 2 Z-Wave switch automations
- **Generator Validation:** Successfully generated valid YAML matching HA format
- **Z-Wave JS Support:** Confirmed correct event mapping for Z-Wave JS triggers

### Current State

The TypeScript generator is fully functional and producing valid Home Assistant configuration. The office room serves as a proof-of-concept demonstrating the complete workflow:

1. Define devices in TypeScript with type safety
2. Create scenes referencing devices by logical names
3. Create automations linking Z-Wave triggers to scenes
4. Generate YAML that matches Home Assistant's expected format

### Next Steps

**Phase 3 - Migrate Remaining Scenes:**
- Review legacy metaconfig.yaml for complete device inventory
- Map remaining rooms (bedroom, kitchen, living, bathroom, etc.)
- Migrate all 40+ scenes to TypeScript
- Test each room's scenes before proceeding

**Important Notes:**
- ✅ **FIXED:** The `just fetch` command now uses `--filter='protect ...'` to prevent deletion of local-only directories
- Protected directories: `config-generator/`, `generated/`, `manual/`, `backups/`, `HomeAssistantConfig/`, `MetaHassConfig/`, `.git/`
- These directories are safe from `rsync --delete` and will be preserved during fetch operations

**Legacy Systems (Migration References - DO NOT DELETE):**
- **`HomeAssistantConfig/metaconfig.yaml`** - Contains all 217 entities, 40+ scenes, 88+ automations from old system
- **`MetaHassConfig/`** - Python-based generator (deprecated) - serves as reference for understanding old logic
- Both protected by `--filter='protect .../***'` in Justfile
