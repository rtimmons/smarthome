/**
 * Home Assistant Scene Definitions
 *
 * This file defines all scenes in the smart home system.
 * Scenes describe desired states for lights and other devices.
 *
 * TODO: Migrate scenes from legacy metaconfig.yaml
 *       Reference devices using logical names from devices.ts
 */

import { SceneRegistry } from "./types";

/**
 * Scene Registry
 *
 * Defines all scenes in the system.
 * Each scene specifies the desired state for lights and other devices.
 *
 * Example usage:
 *   scenes.bedroom_high -> { name: "Bedroom - High", lights: [...] }
 *
 * Naming convention:
 *   <room>_<brightness_level> - e.g., bedroom_high, office_medium, kitchen_off
 *   <room>_<activity> - e.g., living_room_movie, bedroom_reading
 */
export const scenes: SceneRegistry = {
  // ============================================================================
  // Office Scenes
  // ============================================================================

  office_high: {
    name: "Office - High",
    lights: [
      {
        device: "office_abovecouch",
        state: "on",
        brightness: 255,
        rgbw_color: [5, 4, 0, 255]  // Warm white
      },
      {
        device: "office_abovecouch_white",
        state: "on",
        brightness: 255
      },
      {
        device: "office_abovetv",
        state: "on",
        brightness: 255,
        rgbw_color: [5, 4, 0, 255]  // Warm white
      },
      {
        device: "office_abovetv_white",
        state: "on",
        brightness: 255
      },
      {
        device: "office_sidetable",
        state: "on",
        brightness: 255,
        color_temp: 2732  // Warm white (366 mireds)
      }
    ],
    switches: {
      office_pianolight: "on"
    }
  },

  office_medium: {
    name: "Office - Medium",
    lights: [
      {
        device: "office_abovecouch",
        state: "on",
        brightness: 180,
        rgbw_color: [5, 4, 0, 180]  // Warm white
      },
      {
        device: "office_abovecouch_white",
        state: "on",
        brightness: 180
      },
      {
        device: "office_abovetv",
        state: "on",
        brightness: 180,
        rgbw_color: [5, 4, 0, 180]  // Warm white
      },
      {
        device: "office_abovetv_white",
        state: "on",
        brightness: 180
      },
      {
        device: "office_sidetable",
        state: "on",
        brightness: 180,
        color_temp: 2732  // Warm white
      }
    ],
    switches: {
      office_pianolight: "on"
    }
  },

  office_low: {
    name: "Office - Low",
    lights: [
      {
        device: "office_sidetable",
        state: "on",
        brightness: 50,
        color_temp: 2732  // Warm white
      }
    ],
    switches: {
      office_pianolight: "off"
    }
  },

  office_off: {
    name: "Office - Off",
    lights: [
      {
        device: "office_abovecouch",
        state: "off"
      },
      {
        device: "office_abovecouch_white",
        state: "off"
      },
      {
        device: "office_abovetv",
        state: "off"
      },
      {
        device: "office_abovetv_white",
        state: "off"
      },
      {
        device: "office_sidetable",
        state: "off"
      }
    ],
    switches: {
      office_pianolight: "off"
    }
  },

  // ============================================================================
  // Bathroom Scenes
  // ============================================================================

  bathroom_high: {
    name: "Bathroom - High",
    lights: [
      {
        device: "bathroom_abovesauna",
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

  bathroom_medium: {
    name: "Bathroom - Medium",
    lights: [
      {
        device: "bathroom_abovesauna",
        state: "on",
        brightness: 180
      },
      {
        device: "bathroom_vanityleft",
        state: "on",
        brightness: 180
      },
      {
        device: "bathroom_vanityright",
        state: "on",
        brightness: 180
      }
    ]
  },

  bathroom_off: {
    name: "Bathroom - Off",
    lights: [
      {
        device: "bathroom_abovesauna",
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

  bathroom_low: {
    name: "Bathroom - Low",
    lights: [
      {
        device: "bathroom_vanityleft",
        state: "on",
        brightness: 50
      },
      {
        device: "bathroom_vanityright",
        state: "on",
        brightness: 50
      }
    ]
  },
};

/**
 * Helper function to get a scene by key
 */
export function getScene(key: string) {
  const scene = scenes[key];
  if (!scene) {
    throw new Error(`Scene not found: ${key}`);
  }
  return scene;
}
