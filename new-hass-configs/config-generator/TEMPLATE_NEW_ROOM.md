# Template: Adding a New Room

This template provides copy-paste examples for adding a new room with scenes and webhooks.

## Quick Start Template

Replace `{ROOM_NAME}`, `{room_id}`, and device names with your actual values.

### Step 1: Add to scenes.ts

```typescript
// At the top of scenes.ts, import the helper
import { createStandardRoomScenes } from "./helpers";

// In the scenes export, add:
export const scenes: SceneRegistry = {
  // ... existing scenes ...

  // ============================================================================
  // {ROOM_NAME} Scenes
  // ============================================================================

  ...createStandardRoomScenes({
    roomDisplayName: "{ROOM_NAME}",     // e.g., "Bedroom"
    roomId: "{room_id}",                // e.g., "bedroom" (lowercase, underscores)
    devices: [
      "{room_id}_light1",               // e.g., "bedroom_ceiling"
      "{room_id}_light2",               // e.g., "bedroom_nightstand"
    ]
  }),
};
```

### Step 2: Add to automations.ts

```typescript
// At the top of automations.ts, import the helper
import { createStandardWebhooks } from "./helpers";

// In the automations export, add:
export const automations: AutomationRegistry = {
  // ... existing automations ...

  // ============================================================================
  // {ROOM_NAME} Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  ...createStandardWebhooks({
    roomDisplayName: "{ROOM_NAME}",     // e.g., "Bedroom"
    roomId: "{room_id}"                 // e.g., "bedroom"
  }),
};
```

### Step 3: Generate and Deploy

```bash
cd new-hass-configs
just generate
just deploy
```

---

## Common Patterns

### Pattern 1: Simple Room (All Lights Behave the Same)

**Example: Bedroom with two lights that all dim together**

```typescript
// scenes.ts
...createStandardRoomScenes({
  roomDisplayName: "Bedroom",
  roomId: "bedroom",
  devices: [
    "bedroom_ceiling",
    "bedroom_nightstand"
  ]
}),

// automations.ts
...createStandardWebhooks({
  roomDisplayName: "Bedroom",
  roomId: "bedroom"
}),
```

**Result:**
- **High**: Both lights at 255
- **Medium**: Both lights at 180
- **Low**: Both lights at 50
- **Off**: Both lights off

---

### Pattern 2: Room with Main + Accent Lights

**Example: Some lights only on in high/medium, not in low**

```typescript
// scenes.ts
...createStandardRoomScenes({
  roomDisplayName: "Kitchen",
  roomId: "kitchen",
  devices: [
    "kitchen_ceiling",        // Main light
    "kitchen_undercabinet"    // Accent light
  ],
  partialDevices: {
    mainOnly: ["kitchen_ceiling"],  // Only on in high/medium, off in low
    lowOnly: []
  }
}),
```

**Result:**
- **High**: ceiling=255, undercabinet=255
- **Medium**: ceiling=180, undercabinet=180
- **Low**: undercabinet=50 (ceiling off)
- **Off**: Both off

---

### Pattern 3: Room with Switches (Non-Dimmable Devices)

**Example: Office with dimmable lights + non-dimmable piano light switch**

```typescript
// scenes.ts
...createStandardRoomScenes({
  roomDisplayName: "Office",
  roomId: "office",
  devices: [
    "office_ceiling",
    "office_desk"
  ],
  switches: {
    office_pianolight: "on"  // Will be "on" in high/medium, "off" in low/off
  }
}),
```

**Result:**
- **High**: lights=255, pianolight=on
- **Medium**: lights=180, pianolight=on
- **Low**: lights=50, pianolight=off
- **Off**: lights=off, pianolight=off

---

### Pattern 4: Complex Multi-Zone Room (Manual Definition)

**Example: Living room with different zones at different brightnesses**

For complex scenes with custom brightness per device, define manually:

```typescript
// scenes.ts
export const scenes: SceneRegistry = {
  // ... other scenes ...

  living_room_high: {
    name: "Living Room - High",
    lights: [
      // Main lights - full brightness
      { device: "living_floor", state: "on", brightness: 255 },
      { device: "living_nook", state: "on", brightness: 255 },

      // Accent lights - medium even in high mode
      { device: "living_windowsillleft", state: "on", brightness: 180 },
      { device: "living_windowsillright", state: "on", brightness: 180 },

      // Decorative lights - on but dim
      { device: "living_palm", state: "on", brightness: 150 },
    ],
    switches: {
      living_ledwall: "on"
    }
  },

  living_room_medium: {
    name: "Living Room - Medium",
    lights: [
      { device: "living_floor", state: "on", brightness: 180 },
      { device: "living_nook", state: "on", brightness: 180 },
      // Accent lights off in medium mode
      { device: "living_windowsillleft", state: "off" },
      { device: "living_windowsillright", state: "off" },
      { device: "living_palm", state: "off" },
    ],
    switches: {
      living_ledwall: "off"
    }
  },

  living_room_low: {
    name: "Living Room - Low",
    lights: [
      { device: "living_floor", state: "on", brightness: 50 },
      { device: "living_nook", state: "on", brightness: 50 },
    ],
    switches: {
      living_ledwall: "off"
    }
  },

  living_room_off: {
    name: "Living Room - Off",
    lights: [
      { device: "living_floor", state: "off" },
      { device: "living_nook", state: "off" },
      { device: "living_windowsillleft", state: "off" },
      { device: "living_windowsillright", state: "off" },
      { device: "living_palm", state: "off" },
    ],
    switches: {
      living_ledwall: "off"
    }
  },
};

// Still use helper for webhooks
export const automations: AutomationRegistry = {
  ...createStandardWebhooks({
    roomDisplayName: "Living Room",
    roomId: "living_room"
  }),
};
```

---

## Room Name Conversion Examples

| Dashboard Room Name | room_id          | Scene IDs                 | Webhook IDs                      |
|---------------------|------------------|---------------------------|----------------------------------|
| "Bedroom"           | `bedroom`        | `bedroom_high`, etc.      | `scene_bedroom_high`, etc.       |
| "Living Room"       | `living_room`    | `living_room_high`, etc.  | `scene_living_room_high`, etc.   |
| "Guest Bathroom"    | `guest_bathroom` | `guest_bathroom_high`, etc.| `scene_guest_bathroom_high`, etc.|
| "Office"            | `office`         | `office_high`, etc.       | `scene_office_high`, etc.        |

**Rule:** Dashboard room name → lowercase → spaces to underscores = room_id

---

## Full Example: Adding "Guest Bedroom"

### 1. Ensure devices exist in devices.ts

```typescript
// devices.ts
export const devices = {
  lights: {
    guest_bedroom_ceiling: {
      entity: "light.guest_bedroom_ceiling",
      name: "Guest Bedroom Ceiling"
    },
    guest_bedroom_nightstand: {
      entity: "light.guest_bedroom_nightstand",
      name: "Guest Bedroom Nightstand"
    },
    guest_bedroom_closet: {
      entity: "light.guest_bedroom_closet",
      name: "Guest Bedroom Closet"
    }
  }
};
```

### 2. Add scenes to scenes.ts

```typescript
// At top of file
import { createStandardRoomScenes } from "./helpers";

// In scenes export
export const scenes: SceneRegistry = {
  // ... existing scenes ...

  // ============================================================================
  // Guest Bedroom Scenes
  // ============================================================================

  ...createStandardRoomScenes({
    roomDisplayName: "Guest Bedroom",
    roomId: "guest_bedroom",
    devices: [
      "guest_bedroom_ceiling",
      "guest_bedroom_nightstand",
      "guest_bedroom_closet"
    ],
    partialDevices: {
      mainOnly: ["guest_bedroom_closet"],  // Closet only on in high/medium
      lowOnly: []
    }
  }),
};
```

### 3. Add webhooks to automations.ts

```typescript
// At top of file
import { createStandardWebhooks } from "./helpers";

// In automations export
export const automations: AutomationRegistry = {
  // ... existing automations ...

  // ============================================================================
  // Guest Bedroom Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  ...createStandardWebhooks({
    roomDisplayName: "Guest Bedroom",
    roomId: "guest_bedroom"
  }),
};
```

### 4. Verify dashboard has the room

```javascript
// grid-dashboard/ExpressServer/src/public/js/config.js
rooms: [
  'Living Room',
  'Bedroom',
  'Guest Bedroom',  // ← Add here with exact name
  // ...
],
```

### 5. Generate and deploy

```bash
cd new-hass-configs
just generate
just deploy
```

### 6. Test in dashboard

1. Open grid-dashboard
2. Click "Guest Bedroom" room icon
3. Press Sun button (should trigger guest_bedroom_high)
4. Press Dim button (should trigger guest_bedroom_medium)
5. Press Moon button (should trigger guest_bedroom_off)

---

## Checklist

When adding a new room, verify:

- [ ] Room name in dashboard matches exactly (case-sensitive!)
- [ ] All devices exist in `devices.ts`
- [ ] Scene IDs follow pattern: `{room_id}_{level}`
- [ ] Webhook IDs follow pattern: `scene_{room_id}_{level}`
- [ ] Four scenes created: high, medium, low, off
- [ ] Three webhooks created: high, medium, off (NOT low)
- [ ] Ran `just generate` successfully
- [ ] Ran `just deploy` successfully
- [ ] Tested all three dashboard buttons

---

## Troubleshooting

### Helpers not found during compilation

Make sure to import the helpers at the top of your file:

```typescript
import { createStandardRoomScenes, createStandardWebhooks } from "./helpers";
```

### Spread operator not working

Make sure you're spreading into the object correctly:

```typescript
// CORRECT
export const scenes: SceneRegistry = {
  ...createStandardRoomScenes({ ... }),  // ← Spread operator
  // other scenes
};

// INCORRECT
export const scenes: SceneRegistry = {
  createStandardRoomScenes({ ... }),  // ← Missing spread operator!
};
```

### Scene not appearing in Home Assistant

1. Check generated YAML: `cat new-hass-configs/generated/scenes.yaml | grep {room_id}`
2. Check merged YAML: `cat new-hass-configs/scenes.yaml | grep {room_id}`
3. Regenerate: `cd new-hass-configs && just generate && just deploy`

### Dashboard button not working

1. Verify room name matches exactly (case-sensitive)
2. Check webhook automation exists: `cat new-hass-configs/automations.yaml | grep {room_id}`
3. Test webhook manually: `curl -X POST http://homeassistant.local:8123/api/webhook/scene_{room_id}_high`
4. Check Home Assistant automation is enabled

---

## Next Steps

After adding your room:

1. Test all scene buttons in the dashboard
2. Adjust brightness levels if needed in `scenes.ts`
3. Consider adding Z-Wave switch automations if applicable
4. Document any special scene requirements
