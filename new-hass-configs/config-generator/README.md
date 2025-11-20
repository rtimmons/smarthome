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
       ↓ (Home Assistant entity)
Entity: scene.living_room_high
```

**Examples:**
- "Living Room" → `living_room_high` → `scene_living_room_high` → `scene.living_room_high`
- "Office" → `office_medium` → `scene_office_medium` → `scene.office_medium`
- "Guest Bathroom" → `guest_bathroom_off` → `scene_guest_bathroom_off` → `scene.guest_bathroom_off`

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
   - POSTs to Home Assistant webhook: `${webhookBase}/${scene}`
   - Example: `http://supervisor/core/api/webhook/scene_living_room_high`

4. **Home Assistant Webhook Automation** (generated from `automations.ts`)
   - Listens for `webhook_id: scene_living_room_high`
   - Triggers scene: `scene.living_room_high`

5. **Home Assistant Scene** (generated from `scenes.ts`)
   - Applies defined light states to all devices in the scene

### Workflow

1. Define devices in `devices.ts` (entity IDs, capabilities, events)
2. Define scenes in `scenes.ts` (reference devices by logical name)
3. Define automations in `automations.ts` (reference devices and scenes)
4. Run `npm run generate` to create YAML files
5. Generated files output to `../generated/`
6. Use `just check` and `just deploy` to deploy

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
    color_temp: 2732  // Warm white (366 mireds)
  }
]
```

### RGBW Lights and Automatic Pairing

**IMPORTANT**: RGBW lights (e.g., Zooz ZEN31 RGBW Dimmer) expose **two separate entities** in Home Assistant:
1. **RGBW entity** - Controls RGBW color channels (e.g., `office_abovetv`)
2. **White entity** - Controls white-only channel (e.g., `office_abovetv_white`)

**The config-generator automatically synchronizes these paired entities!** You only need to specify **one** entity in your scene definition, and the paired entity will be automatically included with matching on/off state and brightness.

#### Example - Automatic Pairing

```typescript
// You only need to specify ONE entity:
office_high: {
  name: "Office - High",
  lights: [
    {
      device: "office_abovetv_white",  // Specify only the white entity
      state: "on",
      brightness: 255
    }
  ]
}
```

**Generated output includes BOTH entities automatically:**

```yaml
- id: office_high
  name: Office - High
  entities:
    light.light_office_abovetv_white:    # Explicitly defined
      state: on
      brightness: 255
    light.light_office_abovetv:          # Automatically added!
      state: on
      brightness: 255
```

#### Paired Devices

The following device pairs are **automatically synchronized**:

- `office_abovecouch` ↔ `office_abovecouch_white`
- `office_abovetv` ↔ `office_abovetv_white`
- `living_curtains` ↔ `living_curtains_white`
- `living_windowsillleft` ↔ `living_windowsillleft_white`
- `living_windowsillright` ↔ `living_windowsillright_white`
- `living_behindtv` ↔ `living_behindtv_white`
- `living_abovetv` ↔ `living_abovetv_white`
- `kitchen_upper` ↔ `kitchen_upper_white`
- `kitchen_lower` ↔ `kitchen_lower_white`
- `kitchen_dining_nook` ↔ `kitchen_dining_nook_white`

#### When to Specify Both Entities

If you need **different settings** for each entity, you can explicitly define both:

```typescript
lights: [
  {
    device: "office_abovetv",
    state: "on",
    rgbw_color: [255, 0, 0, 0],  // Red RGBW
    brightness: 255
  },
  {
    device: "office_abovetv_white",
    state: "on",
    brightness: 100  // Different brightness for white channel
  }
]
```

When both are explicitly defined, **auto-pairing is skipped** and your explicit settings are used.

#### Verifying Scene Behavior

After deploying scene changes, verify both entities are controlled correctly:

```bash
# Trigger the scene
hass-cli service call scene.turn_on --arguments 'entity_id=scene.office_high'

# Check both paired entities are in sync
hass-cli state get light.light_office_abovecouch
hass-cli state get light.light_office_abovecouch_white
```

Both entities should show the same on/off state and brightness. If they don't match:
1. Check that `generated/scenes.yaml` includes both entities
2. Run `just deploy` from `new-hass-configs/` to deploy the updated config
3. Verify the scene was reloaded in Home Assistant

#### Adding New Paired Devices

To add a new RGBW device with automatic pairing:

1. **Add both entities to `devices.ts`** with the `_white` suffix:

```typescript
lights: {
  new_rgbw_light: {
    entity: "light.light_new_rgbw",
    type: "zwave_zen31_rgbw",
    capabilities: ["brightness", "rgbw_color"]
  },
  new_rgbw_light_white: {  // Must end with _white
    entity: "light.light_new_rgbw_white",
    type: "dimmer_light",
    capabilities: ["brightness"]
  }
}
```

2. **Use in scenes** (specify only one, the other is auto-added):

```typescript
lights: [
  {
    device: "new_rgbw_light_white",
    state: "on",
    brightness: 255
  }
]
```

3. **Run tests** to verify pairing works:

```bash
cd config-generator
npm test  # Tests automatically verify all _white pairs
```

The pairing is detected automatically based on the `_white` suffix naming convention. See `src/devices.test.ts` and `src/generate.test.ts` for comprehensive test coverage.

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
   - Server should forward to webhook endpoint

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
