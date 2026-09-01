# Home Assistant Configuration Generator

TypeScript-based configuration generator for Home Assistant. Provides type-safe, maintainable configuration with modern tooling support.

## Table of Contents

- [Quick Start](#quick-start)
- [Naming Conventions](#naming-conventions)
- [Architecture](#architecture)
- [Adding a New Room](#adding-a-new-room)
- [Scene Levels](#scene-levels)
- [Webhook Integration](#webhook-integration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

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

---

## Naming Conventions

### Room Names

**CRITICAL**: Room names must match exactly between three systems:

1. **Dashboard** (`grid-dashboard/ExpressServer/src/public/js/config.js`)
   - Defined in `config.rooms` array
   - Example: `"Living Room"`, `"Office"`, `"Bathroom"`

2. **Scene IDs** (`src/scenes.ts`)
   - Format: `{room}_{level}` (lowercase, spaces → underscores)
   - Example: `living_room_high`, `office_medium`, `bathroom_off`

3. **Webhook IDs** (auto-generated in automations)
   - Format: `scene_{room}_{level}` (lowercase, spaces → underscores)
   - Example: `scene_living_room_high`, `scene_office_medium`

### Conversion Flow

```
Dashboard Room: "Living Room"
       ↓ (lowercase, spaces → underscores)
Scene ID: living_room_high
       ↓ (prepend "scene_")
Webhook ID: scene_living_room_high
       ↓ (reliability entry point)
Script: script.fast_scene_living_room_high
```

**Examples:**
- "Living Room" → `living_room_high` → `scene_living_room_high` → `script.fast_scene_living_room_high`
- "Office" → `office_medium` → `scene_office_medium` → `script.fast_scene_office_medium`
- "Guest Bathroom" → `guest_bathroom_off` → `scene_guest_bathroom_off` → `script.fast_scene_guest_bathroom_off`

---

## Architecture

### Core Files

- **src/types.ts** - TypeScript type definitions for all config objects
- **src/devices.ts** - Device registry mapping logical names to HA entities
- **src/scenes.ts** - Scene definitions (desired states for devices)
- **src/automations.ts** - Automation rules (triggers + actions)
- **src/generate.ts** - Generator that converts TypeScript to YAML

### Dashboard → Home Assistant Flow

1. **User presses scene button** on dashboard (☀️ Sun / 🌘 Dim / 🌑 Moon emoji)
   - Dashboard calls: `Lights.Scene` action with `['$room', 'High']`

2. **LightController** (`grid-dashboard/.../light-controller.js`)
   - Replaces `$room` with active room name (e.g., "Living Room")
   - Creates URL: `/scenes/scene_{room}_{level}` (lowercase, spaces→underscores)
   - Example: `/scenes/scene_living_room_high`

3. **Express Server** (`grid-dashboard/.../hass.ts`)
   - Receives request at `/scenes/:scene`
   - In Home Assistant, starts `script.fast_scene_<scene_id>` through the authenticated Core API
   - Coalesces identical browser/touch requests received within one second
   - Uses the webhook only for standalone development without a Supervisor token

4. **Fast Scene Wrapper** (generated in `scripts.yaml`)
   - `script.fast_scene_living_room_high` runs in `single` mode
   - Calls `script.fast_scene_dispatch` directly and remains active until it finishes
   - Generated webhook and switch automations also call this wrapper directly; they do not use non-blocking `script.turn_on`

5. **Shared Dispatcher**
   - Serializes scene work in `queued` mode
   - Skips unavailable/unknown entities and dead Z-Wave nodes
   - Groups compatible non-Z-Wave calls and sends isolated Z-Wave calls in paced batches of at most two
   - Continues after individual action errors and reports skipped targets

Native `scene.<scene_id>` entities are still generated for UI/compatibility, but controls, tests, and diagnostics must use `script.fast_scene_<scene_id>`; `scene.turn_on` bypasses the reliability path.

### Workflow

1. Define devices in `devices.ts` (entity IDs, capabilities, events)
2. Define scenes in `scenes.ts` (reference devices by logical name)
3. Define automations in `automations.ts` (reference devices and scenes)
4. Run `npm run generate` to create YAML files
5. Generated files output to `../generated/`
6. Parent `just generate` rebuilds merged deployment files, including ignored/untracked `scripts.yaml`
7. Use `just test`, `just check`, and `just deploy` to validate and deploy

---

## Adding a New Room

Follow these steps to add a new room with scenes and webhook automations:

### Step 1: Add Devices (if needed)

Edit `src/devices.ts` to add any new light or switch devices for the room:

```typescript
export const devices = {
  lights: {
    bedroom_ceiling: {
      entity: "light.bedroom_ceiling",
      name: "Bedroom Ceiling Light"
    },
    bedroom_nightstand: {
      entity: "light.bedroom_nightstand",
      name: "Bedroom Nightstand"
    }
  },
  switches: {
    bedroom_fan: {
      entity: "switch.bedroom_fan",
      name: "Bedroom Fan"
    }
  }
};
```

### Step 2: Add Scenes

Edit `src/scenes.ts` to add the **four standard scenes** for the room:

```typescript
export const scenes: SceneRegistry = {
  // ... existing scenes ...

  // ============================================================================
  // Bedroom Scenes
  // ============================================================================

  bedroom_high: {
    name: "Bedroom - High",
    lights: [
      { device: "bedroom_ceiling", state: "on", brightness: 255 },
      { device: "bedroom_nightstand", state: "on", brightness: 255 }
    ]
  },

  bedroom_medium: {
    name: "Bedroom - Medium",
    lights: [
      { device: "bedroom_ceiling", state: "on", brightness: 180 },
      { device: "bedroom_nightstand", state: "on", brightness: 180 }
    ]
  },

  bedroom_low: {
    name: "Bedroom - Low",
    lights: [
      { device: "bedroom_nightstand", state: "on", brightness: 50 }
    ]
  },

  bedroom_off: {
    name: "Bedroom - Off",
    lights: [
      { device: "bedroom_ceiling", state: "off" },
      { device: "bedroom_nightstand", state: "off" }
    ]
  },
};
```

**Naming Convention:**
- Scene IDs: `{room}_{level}` (lowercase, underscores for spaces)
- Scene Names: `{Room} - {Level}` (proper case, readable)

### Step 3: Add Webhook Automations

Edit `src/automations.ts` to add **three webhook automations** for the dashboard buttons (High, Medium, Off):

```typescript
export const automations: AutomationRegistry = {
  // ... existing automations ...

  // ============================================================================
  // Bedroom Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  bedroom_webhook_high: {
    alias: "Bedroom Webhook → High",
    description: "Dashboard button: Bedroom High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_high"
    },
    action: {
      type: "scene",
      scene: "bedroom_high"
    },
    mode: "single"
  },

  bedroom_webhook_medium: {
    alias: "Bedroom Webhook → Medium",
    description: "Dashboard button: Bedroom Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_medium"
    },
    action: {
      type: "scene",
      scene: "bedroom_medium"
    },
    mode: "single"
  },

  bedroom_webhook_off: {
    alias: "Bedroom Webhook → Off",
    description: "Dashboard button: Bedroom Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_off"
    },
    action: {
      type: "scene",
      scene: "bedroom_off"
    },
    mode: "single"
  },
};
```

**Pattern for Webhook Automations:**
- Automation ID: `{room}_webhook_{level}`
- Alias: `{Room} Webhook → {Level}`
- Webhook ID: `scene_{room}_{level}`
- Scene reference: `{room}_{level}`

### Step 4: Ensure Room is in Dashboard

Verify the room exists in the dashboard configuration with **exact name match**:

Edit `grid-dashboard/ExpressServer/src/public/js/config.js`:

```javascript
rooms: [
  'Living Room',
  'Bedroom',      // ← Ensure room name matches exactly (case-sensitive!)
  'Kitchen',
  'Bathroom',
  'Office',
  'Guest Bathroom',
  'Closet',
  'Move',
],
```

### Step 5: Generate and Deploy

```bash
cd /path/to/new-hass-configs

# Generate YAML files from TypeScript
just generate

# Validate configuration (optional but recommended)
just check

# Deploy to Home Assistant
just deploy
```

---

## Scene Levels

Each room should have **four standard scene levels**:

### 1. High (☀️ Sun Button)
- **Purpose**: Maximum brightness, all lights on
- **Brightness**: 255 (100%)
- **Typical use**: Daytime, active work/activities
- **Dashboard**: Accessible via Sun button

### 2. Medium (🌘 Dim Button)
- **Purpose**: Comfortable ambient lighting
- **Brightness**: 180 (70%)
- **Typical use**: Evening relaxation, entertaining
- **Dashboard**: Accessible via Dim button

### 3. Low (no dashboard button)
- **Purpose**: Minimal lighting for nighttime
- **Brightness**: 50 (20%)
- **Typical use**: Night light, minimal illumination
- **Dashboard**: NOT accessible (only via automations/switches)
- **Note**: Typically only some lights are on in Low mode

### 4. Off (🌑 Moon Button)
- **Purpose**: Turn off all lights in the room
- **State**: All lights off
- **Typical use**: Leaving room, going to sleep
- **Dashboard**: Accessible via Moon button

### Dashboard Scene Buttons

The dashboard shows **three buttons** per room (located at y:2, x:7-9 in grid):

```javascript
// From grid-dashboard config.js
{ w:1, h:1, y:2, x:7, emoji: 'Sun',   onPress: {action: 'Lights.Scene', args: ['$room','High']} },
{ w:1, h:1, y:2, x:8, emoji: 'Dim',   onPress: {action: 'Lights.Scene', args: ['$room','Medium']} },
{ w:1, h:1, y:2, x:9, emoji: 'Moon',  onPress: {action: 'Lights.Scene', args: ['$room','Off']} },
```

**Important:** Only create webhook automations for High, Medium, and Off (not Low).

---

## Webhook Integration

Webhook automations connect dashboard scene buttons to Home Assistant scenes.

### When to Add Webhooks

**✅ Always add webhook automations for:**
- `scene_{room}_high` → `{room}_high`
- `scene_{room}_medium` → `{room}_medium`
- `scene_{room}_off` → `{room}_off`

**❌ Don't add webhook automations for:**
- `{room}_low` (not accessible from dashboard)

### Webhook Automation Template

```typescript
{room}_webhook_{level}: {
  alias: "{Room} Webhook → {Level}",
  description: "Dashboard button: {Room} {Level} scene",
  trigger: {
    type: "webhook",
    webhook_id: "scene_{room}_{level}"
  },
  action: {
    type: "scene",
    scene: "{room}_{level}"
  },
  mode: "single"
}
```

### Testing Webhooks

After deployment, test webhooks manually:

```bash
# Test Office High scene
curl -X POST http://homeassistant.local:8123/api/webhook/scene_office_high

# Test Living Room Medium scene
curl -X POST http://homeassistant.local:8123/api/webhook/scene_living_room_medium

# Test Bathroom Off scene
curl -X POST http://homeassistant.local:8123/api/webhook/scene_bathroom_off
```

---

## Common Patterns

### Multi-Zone Rooms

For rooms with multiple lighting zones (some zones may have lower brightness in High mode):

```typescript
living_room_high: {
  name: "Living Room - High",
  lights: [
    // Main lighting - full brightness
    { device: "living_floor", state: "on", brightness: 255 },
    { device: "living_nook", state: "on", brightness: 255 },
    { device: "living_curtains", state: "on", brightness: 255 },

    // Accent lighting - medium brightness even in High mode
    { device: "living_windowsillleft", state: "on", brightness: 180 },
    { device: "living_windowsillright", state: "on", brightness: 180 },
  ]
}
```

### Including Switches

Some rooms may have non-dimmable switches:

```typescript
office_high: {
  name: "Office - High",
  lights: [
    { device: "office_ceiling", state: "on", brightness: 255 }
  ],
  switches: {
    office_pianolight: "on"  // Non-dimmable switch
  }
}
```

### Color Temperature

For lights that support color temperature:

```typescript
lights: [
  {
    device: "bedroom_nightstand",
    state: "on",
    brightness: 255,
    color_temp_kelvin: 2732  // Warm white
  }
]
```

### RGBW Endpoint Selection

Zooz ZEN31 and Fibaro RGBW controllers expose an aggregate RGBW light on endpoint 1 and individual channels on endpoints 2-5. The canonical `_white` entity must be bound to endpoint 5.

Scenes select exactly one endpoint. White brightness targets `_white`; RGB color targets the aggregate entity; off scenes target the aggregate entity once so every channel is extinguished. The generator deliberately does not auto-pair these targets because that doubles traffic to the same Z-Wave node and can produce contradictory state feedback.

#### White scene

```typescript
office_high: {
  name: "Office - High",
  lights: [
    {
      device: "office_abovetv_white",
      state: "on",
      brightness: 255
    }
  ]
}
```

The generated scene contains only endpoint 5:

```yaml
- id: office_high
  name: Office - High
  entities:
    light.light_office_abovetv_white:
      state: on
      brightness: 255
```

#### Color and off scenes

```typescript
lights: [
  {
    device: "office_abovetv",
    state: "on",
    rgbw_color: [255, 0, 0, 0],
    brightness: 255
  }
]

// A separate off scene uses the aggregate endpoint once.
lights: [
  {
    device: "office_abovetv",
    state: "off"
  }
]
```

#### Verifying Scene Behavior

After deploying scene changes, verify the intended physical endpoint and the generated calls:

```bash
just zwave-exercise-scene --scene office_high
just ha-state light.light_office_abovecouch_white
```

When adding an RGBW controller, register both logical entities and verify `_white` by its immutable Z-Wave value ID:

```typescript
lights: {
  new_rgbw_light: {
    entity: "light.light_new_rgbw",
    type: "zwave_zen31_rgbw",
    capabilities: ["brightness", "rgbw_color"]
  },
  new_rgbw_light_white: {
    entity: "light.light_new_rgbw_white",
    type: "dimmer_light",
    capabilities: ["brightness"]
  }
}
```

Use only the endpoint required by each scene:

```typescript
lights: [
  {
    device: "new_rgbw_light_white",
    state: "on",
    brightness: 255
  }
]
```

Run the tests and inspect the generated output:

```bash
cd config-generator
npm test
```

---

## Type Safety Benefits

- **Compile-time validation** - Catch errors before deployment
- **IDE autocomplete** - IntelliSense for all config options
- **Refactoring support** - Rename devices/scenes safely
- **Documentation** - Types serve as inline documentation

---

## Development

```bash
# Watch mode (auto-rebuild on changes)
npm run watch

# Clean build artifacts
npm run clean

# Full rebuild
npm run clean && npm run build

# Generate configs
npm run generate
```

---

## Troubleshooting

### Scene not working from dashboard

1. **Check room name matches exactly**
   - Dashboard room name must match scene ID conversion
   - "Living Room" → `living_room_high` (lowercase, spaces → underscores)
   - Room names are case-sensitive in dashboard config!

2. **Verify webhook ID matches**
   - Dashboard creates: `scene_{room}_{level}`
   - Example: "Office" + "High" → `scene_office_high`

3. **Check automation is enabled**
   - Home Assistant → Settings → Automations & Scenes
   - Look for "{Room} Webhook → {Level}"
   - Ensure automation is enabled

4. **Test webhook directly**
   ```bash
   curl -X POST http://homeassistant.local:8123/api/webhook/scene_office_high
   ```

5. **Check Express server logs**
   - Dashboard should POST to `/scenes/scene_{room}_{level}`
   - In production the server should target `script.fast_scene_{room}_{level}` through the authenticated Core API

6. **Exercise the generated path**
   ```bash
   just zwave-exercise-scene --scene office_high --scene office_off
   ```
   This waits for both entity state and `script.fast_scene_dispatch`; a direct native scene call does not test the reliability contract.

### "Device not found" error

- Ensure device is defined in `devices.ts`
- Check logical name matches exactly (case-sensitive)
- Verify device type (lights vs switches vs outlets)

### "Scene not found" error

- Ensure scene is defined in `scenes.ts`
- Check scene key matches exactly
- Verify scene references valid devices

### TypeScript compilation errors

```bash
cd config-generator
npm run build
# Check for type errors in output
```

### Scene not appearing in Home Assistant

1. **Check scene ID is valid**
   - Must be lowercase
   - Use underscores, not spaces or hyphens
   - No special characters

2. **Regenerate and redeploy**
   ```bash
   cd /path/to/new-hass-configs
   just generate
   just deploy
   ```

3. **Check Home Assistant logs**
   - Settings → System → Logs
   - Look for scene loading errors

### Z-Wave automation not triggering

- Verify `device_id` is correct in device definition
- Check event mapping matches actual device events
- Monitor HA events: Developer Tools > Events > `zwave_js_value_notification`

### Webhook automation not triggering

1. **Enable HA webhook logging**
   ```yaml
   # configuration.yaml
   logger:
     default: info
     logs:
       homeassistant.components.webhook: debug
   ```

2. **Check webhook was registered**
   - Developer Tools → States
   - Filter for automation entities
   - Check automation state

3. **Verify webhook endpoint**
   - Dashboard should use: `http://supervisor/core/api/webhook/{webhook_id}`
   - Check `HASS_WEBHOOK_BASE` environment variable in dashboard

---

## Migration from Legacy System

The config-generator replaces the Python MetaHassConfig tool and supports:

- Modern Z-Wave JS (vs deprecated Z-Wave Classic)
- Type-safe configuration
- Better tooling and IDE support
- Incremental migration from legacy configs

### Z-Wave JS Event Mapping

Z-Wave JS uses different event formats than Z-Wave Classic:

#### Event Values (Dimmer 46203)
- `KeyPressed` - Single press
- `KeyPressed2x` - Double press
- `KeyPressed3x` - Triple press
- `KeyHeldDown` - Hold start
- `KeyReleased` - Hold end

#### Device Configuration Example

```typescript
// src/devices.ts
switches: {
  office_wall_switch: {
    entity: "switch.office_wall",
    type: "zwave_dimmer_46203",
    device_id: "44ca863fc3d89c94bdfb7471c370a932", // Get from HA device registry
    events: {
      doubleUp: {
        command_class_name: "Central Scene",
        property_key_name: "001",
        value: "KeyPressed2x"
      },
      doubleDown: {
        command_class_name: "Central Scene",
        property_key_name: "002",
        value: "KeyPressed2x"
      }
    }
  }
}
```

---

## Quick Reference

### Adding a Room Checklist

- [ ] Add devices to `src/devices.ts`
- [ ] Add 4 scenes to `src/scenes.ts` (high, medium, low, off)
- [ ] Add 3 webhook automations to `src/automations.ts` (high, medium, off)
- [ ] Verify room name in dashboard `config.js` matches exactly
- [ ] Run `just generate`
- [ ] Run `just check` (optional)
- [ ] Run `just deploy`
- [ ] Test scene buttons in dashboard

### File Locations

- Dashboard room names: `grid-dashboard/ExpressServer/src/public/js/config.js`
- Device definitions: `new-hass-configs/config-generator/src/devices.ts`
- Scene definitions: `new-hass-configs/config-generator/src/scenes.ts`
- Automation definitions: `new-hass-configs/config-generator/src/automations.ts`
- Generated YAML: `new-hass-configs/generated/`
- Final merged YAML: `new-hass-configs/scenes.yaml` and `automations.yaml`
