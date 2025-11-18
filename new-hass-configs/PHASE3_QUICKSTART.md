# Phase 3 Quick Start - Migrate Next Room

**Current Status:** Office room complete (proof of concept) ✓
**Next:** Migrate remaining rooms from legacy metaconfig.yaml

---

## Quick Reference

### Commands You'll Use
```bash
# View legacy config
cat HomeAssistantConfig/metaconfig.yaml

# Fetch current HA entity IDs
just fetch

# Edit TypeScript files
vim config-generator/src/devices.ts
vim config-generator/src/scenes.ts
vim config-generator/src/automations.ts

# Generate YAML
just generate

# Validate config (dry-run)
just check

# Deploy to HA
just backup "pre-[room]-migration"
just push
```

### Files You'll Edit
- `config-generator/src/devices.ts` - Add room devices
- `config-generator/src/scenes.ts` - Add room scenes
- `config-generator/src/automations.ts` - Add switch automations

---

## Recommended First Room: Bathroom

**Why Bathroom?**
- Simple (4 lights, 1 switch)
- Fewer scenes than bedroom
- Good learning room after office

### Step 1: Find Bathroom Devices in Legacy Config

```bash
cat HomeAssistantConfig/metaconfig.yaml | grep -A 3 "# Bathroom"
```

**Expected devices:**
- bathroom_light_sauna (hue light)
- bathroom_light_shower (hue light)
- bathroom_light_vanityleft (hue light)
- bathroom_light_vanityright (hue light)
- bathroom_light_vanitysconces (dimmer switch, node_id: 22)

### Step 2: Get Current Entity IDs

```bash
just fetch
# Then search for bathroom entities:
grep -i "bathroom" scenes.yaml automations.yaml
```

### Step 3: Map Devices in TypeScript

Edit `config-generator/src/devices.ts`, add to `lights:` section:

```typescript
// Bathroom lights
bathroom_sauna: {
  entity: "light.bathroom_light_sauna",  // Replace with actual entity ID
  type: "color_light",
  capabilities: ["brightness", "color_temp"]
},
bathroom_shower: {
  entity: "light.bathroom_light_shower",
  type: "color_light",
  capabilities: ["brightness", "color_temp"]
},
bathroom_vanityleft: {
  entity: "light.bathroom_light_vanityleft",
  type: "color_light",
  capabilities: ["brightness", "color_temp"]
},
bathroom_vanityright: {
  entity: "light.bathroom_light_vanityright",
  type: "color_light",
  capabilities: ["brightness", "color_temp"]
},
```

Add to `switches:` section (if Z-Wave switch exists):

```typescript
bathroom_vanity_switch: {
  entity: "switch.bathroom_vanitysconces",  // Replace with actual
  type: "zwave_dimmer_46203",
  device_id: "REPLACE_WITH_DEVICE_ID",  // Get from automations.yaml
  events: {
    // Copy event structure from office_wall_switch
  }
},
```

### Step 4: Find Bathroom Scenes in Legacy Config

```bash
# Search for scenes that control bathroom devices
grep -A 10 "scene_bathroom" HomeAssistantConfig/metaconfig.yaml
```

### Step 5: Create Scenes in TypeScript

Edit `config-generator/src/scenes.ts`, add new scenes:

```typescript
// Bathroom scenes
bathroom_high: {
  name: "Bathroom - High",
  lights: [
    {
      device: "bathroom_sauna",
      state: "on",
      brightness: 255
    },
    {
      device: "bathroom_shower",
      state: "on",
      brightness: 255
    },
    {
      device: "bathroom_vanityleft",
      state: "on",
      brightness: 255
    },
    {
      device: "bathroom_vanityright",
      state: "on",
      brightness: 255
    }
  ]
},

bathroom_off: {
  name: "Bathroom - Off",
  lights: [
    {
      device: "bathroom_sauna",
      state: "off"
    },
    {
      device: "bathroom_shower",
      state: "off"
    },
    {
      device: "bathroom_vanityleft",
      state: "off"
    },
    {
      device: "bathroom_vanityright",
      state: "off"
    }
  ]
},
```

### Step 6: Create Automations (if any)

If bathroom has switch automations, edit `config-generator/src/automations.ts`:

```typescript
bathroom_switch_doubleup: {
  alias: "Bathroom Switch - Double Up → High",
  trigger: {
    type: "zwave_js_scene",
    device: "bathroom_vanity_switch",
    event: "doubleUp"
  },
  action: {
    type: "scene",
    scene: "bathroom_high"
  },
  mode: "single"
},
```

### Step 7: Generate and Test

```bash
# Generate YAML
just generate

# Check for TypeScript errors or warnings
# Review generated files:
cat generated/scenes.yaml | grep -A 20 "bathroom"
cat generated/automations.yaml | grep -A 20 "bathroom"

# Validate on HA (dry-run, no changes)
just check
```

### Step 8: Deploy

```bash
# Create safety backup
just backup "pre-bathroom-migration"

# Deploy to Home Assistant
just push
```

### Step 9: Verify

1. **In Home Assistant UI:**
   - Go to Developer Tools > Services
   - Service: `scene.turn_on`
   - Target: `scene.bathroom_high`
   - Call Service
   - Verify lights turn on

2. **Test automations:**
   - Press physical switch (double-tap up)
   - Verify scene activates

3. **Check logs:**
   - Settings > System > Logs
   - Look for errors related to bathroom scenes/automations

---

## After Bathroom is Complete

**Choose next room:**
- Bedroom (3 lights, 2 switches - more complex automations)
- Kitchen/Living (most complex - multiple switches)

**Repeat the process** for each room until all 40+ scenes are migrated.

---

## Reference Files

- **Office devices:** `config-generator/src/devices.ts` (lines 27-119)
- **Office scenes:** `config-generator/src/scenes.ts` (lines 31-96)
- **Office automations:** `config-generator/src/automations.ts` (lines 33-62)
- **Legacy config:** `HomeAssistantConfig/metaconfig.yaml` (entire file)
- **Type definitions:** `config-generator/src/types.ts` (all types)

---

## Common Issues

**"Device not found" error:**
- Check device name matches key in devices.ts
- Verify you added device to correct section (lights/switches/outlets)

**"Scene not found" error:**
- Check scene name matches key in scenes.ts
- Verify scene key is used in automation action

**Generated YAML has wrong entity IDs:**
- Check entity field in device definition
- Run `just fetch` to get latest entity names from HA

**Z-Wave automation not triggering:**
- Verify device_id is correct (get from current automations.yaml)
- Check property_key_name (001=up, 002=down)
- Monitor events in HA: Developer Tools > Events > `zwave_js_value_notification`

---

**Good luck with the migration! The office room serves as a complete working example.**
