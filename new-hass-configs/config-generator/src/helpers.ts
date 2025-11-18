/**
 * Helper utilities for creating standard room scenes and webhook automations
 *
 * These functions reduce boilerplate when adding new rooms by generating
 * the standard pattern of scenes (high, medium, low, off) and webhook
 * automations (high, medium, off).
 */

import { Scene, Automation, LightState } from "./types";

// ============================================================================
// Scene Helpers
// ============================================================================

export interface RoomSceneConfig {
  /** Room name for display (e.g., "Bedroom") */
  roomDisplayName: string;
  /** Room name for IDs (e.g., "bedroom") - lowercase, underscores for spaces */
  roomId: string;
  /** List of device IDs to include in scenes */
  devices: string[];
  /** Optional: Devices to include only in certain scenes */
  partialDevices?: {
    /** Devices only on in high/medium (not low) */
    mainOnly?: string[];
    /** Devices only on in low */
    lowOnly?: string[];
  };
  /** Optional: Switches to control */
  switches?: {
    [deviceId: string]: "on" | "off";
  };
}

/**
 * Generate standard brightness levels for a scene type
 */
export function getStandardBrightness(
  level: "high" | "medium" | "low" | "off"
): number | undefined {
  switch (level) {
    case "high":
      return 255; // 100%
    case "medium":
      return 180; // 70%
    case "low":
      return 50; // 20%
    case "off":
      return undefined; // State will be "off"
  }
}

/**
 * Create a standard scene for a room
 *
 * @example
 * const bedroomHigh = createRoomScene({
 *   roomDisplayName: "Bedroom",
 *   roomId: "bedroom",
 *   level: "high",
 *   devices: ["bedroom_ceiling", "bedroom_nightstand"]
 * });
 */
export function createRoomScene(config: {
  roomDisplayName: string;
  roomId: string;
  level: "high" | "medium" | "low" | "off";
  devices: string[];
  partialDevices?: {
    mainOnly?: string[];
    lowOnly?: string[];
  };
  switches?: { [deviceId: string]: "on" | "off" };
  /** Optional custom brightness overrides */
  customBrightness?: { [deviceId: string]: number };
}): Scene {
  const {
    roomDisplayName,
    level,
    devices,
    partialDevices = {},
    switches,
    customBrightness = {},
  } = config;

  const brightness = getStandardBrightness(level);
  const state = level === "off" ? "off" : "on";

  const lights: LightState[] = [];

  // Main devices (on in all non-off scenes, or just high/medium)
  const mainDevices =
    level === "low"
      ? devices.filter((d) => !(partialDevices.mainOnly || []).includes(d))
      : devices;

  for (const device of mainDevices) {
    const customBright = customBrightness[device];
    lights.push({
      device,
      state,
      ...(brightness !== undefined && {
        brightness: customBright !== undefined ? customBright : brightness,
      }),
    });
  }

  // Low-only devices (only on in low mode)
  if (level === "low" && partialDevices.lowOnly) {
    for (const device of partialDevices.lowOnly) {
      lights.push({
        device,
        state: "on",
        brightness: 50,
      });
    }
  }

  // Main-only devices in off mode should be explicitly off
  if (level === "off" && partialDevices.mainOnly) {
    for (const device of partialDevices.mainOnly) {
      lights.push({
        device,
        state: "off",
      });
    }
  }

  const scene: Scene = {
    name: `${roomDisplayName} - ${level.charAt(0).toUpperCase() + level.slice(1)}`,
    lights,
  };

  if (switches) {
    scene.switches = switches;
  }

  return scene;
}

/**
 * Create all four standard scenes for a room (high, medium, low, off)
 *
 * Returns an object with keys: {room}_high, {room}_medium, {room}_low, {room}_off
 *
 * @example
 * const bedroomScenes = createStandardRoomScenes({
 *   roomDisplayName: "Bedroom",
 *   roomId: "bedroom",
 *   devices: ["bedroom_ceiling", "bedroom_nightstand"],
 *   partialDevices: {
 *     mainOnly: ["bedroom_ceiling"], // Only on in high/medium
 *     lowOnly: []                    // None
 *   }
 * });
 * // Returns:
 * // {
 * //   bedroom_high: { ... },
 * //   bedroom_medium: { ... },
 * //   bedroom_low: { ... },
 * //   bedroom_off: { ... }
 * // }
 */
export function createStandardRoomScenes(
  config: RoomSceneConfig
): Record<string, Scene> {
  const { roomDisplayName, roomId, devices, partialDevices, switches } = config;

  return {
    [`${roomId}_high`]: createRoomScene({
      roomDisplayName,
      roomId,
      level: "high",
      devices,
      partialDevices,
      switches: switches
        ? Object.fromEntries(
            Object.entries(switches).map(([k, _]) => [k, "on"])
          )
        : undefined,
    }),

    [`${roomId}_medium`]: createRoomScene({
      roomDisplayName,
      roomId,
      level: "medium",
      devices,
      partialDevices,
      switches: switches
        ? Object.fromEntries(
            Object.entries(switches).map(([k, _]) => [k, "on"])
          )
        : undefined,
    }),

    [`${roomId}_low`]: createRoomScene({
      roomDisplayName,
      roomId,
      level: "low",
      devices,
      partialDevices,
      switches: switches
        ? Object.fromEntries(
            Object.entries(switches).map(([k, _]) => [k, "off"])
          )
        : undefined,
    }),

    [`${roomId}_off`]: createRoomScene({
      roomDisplayName,
      roomId,
      level: "off",
      devices,
      partialDevices,
      switches: switches
        ? Object.fromEntries(
            Object.entries(switches).map(([k, _]) => [k, "off"])
          )
        : undefined,
    }),
  };
}

// ============================================================================
// Webhook Automation Helpers
// ============================================================================

/**
 * Create a webhook automation for a scene
 *
 * @example
 * const bedroomHighWebhook = createSceneWebhook({
 *   roomDisplayName: "Bedroom",
 *   roomId: "bedroom",
 *   level: "high"
 * });
 */
export function createSceneWebhook(config: {
  roomDisplayName: string;
  roomId: string;
  level: "high" | "medium" | "off";
}): Automation {
  const { roomDisplayName, roomId, level } = config;
  const levelCapitalized = level.charAt(0).toUpperCase() + level.slice(1);

  return {
    alias: `${roomDisplayName} Webhook → ${levelCapitalized}`,
    description: `Dashboard button: ${roomDisplayName} ${levelCapitalized} scene`,
    trigger: {
      type: "webhook",
      webhook_id: `scene_${roomId}_${level}`,
    },
    action: {
      type: "scene",
      scene: `${roomId}_${level}`,
    },
    mode: "single",
  };
}

/**
 * Create all three webhook automations for a room (high, medium, off)
 *
 * Returns an object with keys: {room}_webhook_high, {room}_webhook_medium, {room}_webhook_off
 *
 * Note: No webhook for "low" since it's not accessible from the dashboard
 *
 * @example
 * const bedroomWebhooks = createStandardWebhooks({
 *   roomDisplayName: "Bedroom",
 *   roomId: "bedroom"
 * });
 * // Returns:
 * // {
 * //   bedroom_webhook_high: { ... },
 * //   bedroom_webhook_medium: { ... },
 * //   bedroom_webhook_off: { ... }
 * // }
 */
export function createStandardWebhooks(config: {
  roomDisplayName: string;
  roomId: string;
}): Record<string, Automation> {
  const { roomDisplayName, roomId } = config;

  return {
    [`${roomId}_webhook_high`]: createSceneWebhook({
      roomDisplayName,
      roomId,
      level: "high",
    }),

    [`${roomId}_webhook_medium`]: createSceneWebhook({
      roomDisplayName,
      roomId,
      level: "medium",
    }),

    [`${roomId}_webhook_off`]: createSceneWebhook({
      roomDisplayName,
      roomId,
      level: "off",
    }),
  };
}

// ============================================================================
// Room Name Utilities
// ============================================================================

/**
 * Convert a dashboard room name to a scene ID prefix
 *
 * @example
 * roomNameToId("Living Room") // => "living_room"
 * roomNameToId("Office") // => "office"
 * roomNameToId("Guest Bathroom") // => "guest_bathroom"
 */
export function roomNameToId(roomName: string): string {
  return roomName.toLowerCase().replace(/\s+/g, "_");
}

/**
 * Validate that a room ID follows the naming convention
 *
 * @throws Error if room ID is invalid
 */
export function validateRoomId(roomId: string): void {
  if (roomId !== roomId.toLowerCase()) {
    throw new Error(`Room ID must be lowercase: "${roomId}"`);
  }
  if (roomId.includes(" ")) {
    throw new Error(`Room ID must use underscores, not spaces: "${roomId}"`);
  }
  if (!/^[a-z0-9_]+$/.test(roomId)) {
    throw new Error(
      `Room ID must contain only lowercase letters, numbers, and underscores: "${roomId}"`
    );
  }
}

// ============================================================================
// Example Usage
// ============================================================================

/*
// Example 1: Simple room with two lights

import { createStandardRoomScenes, createStandardWebhooks } from "./helpers";

const bedroomScenes = createStandardRoomScenes({
  roomDisplayName: "Bedroom",
  roomId: "bedroom",
  devices: ["bedroom_ceiling", "bedroom_nightstand"]
});

const bedroomWebhooks = createStandardWebhooks({
  roomDisplayName: "Bedroom",
  roomId: "bedroom"
});

export const scenes = {
  ...bedroomScenes,
  // Add other rooms...
};

export const automations = {
  ...bedroomWebhooks,
  // Add other automations...
};


// Example 2: Room with partial devices (main lights only on in high/medium)

const kitchenScenes = createStandardRoomScenes({
  roomDisplayName: "Kitchen",
  roomId: "kitchen",
  devices: ["kitchen_ceiling", "kitchen_undercabinet"],
  partialDevices: {
    mainOnly: ["kitchen_ceiling"],  // Only on in high/medium, off in low
    lowOnly: []                      // None
  }
});


// Example 3: Room with switches

const officeScenes = createStandardRoomScenes({
  roomDisplayName: "Office",
  roomId: "office",
  devices: ["office_ceiling", "office_desk"],
  switches: {
    office_pianolight: "on"  // Will be on in high/medium, off in low/off
  }
});


// Example 4: Multi-room spaces

const livingRoomScenes = createStandardRoomScenes({
  roomDisplayName: "Living Room",
  roomId: "living_room",
  devices: [
    "living_floor",
    "living_nook",
    "living_curtains"
  ]
});

*/
