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
      },
      {
        device: "bathroom_vanitysconces",
        state: "on",
        brightness: 255
      }
    ]
  },

  bathroom_medium: {
    name: "Bathroom - Medium",
    lights: [
      {
        device: "bathroom_sauna",
        state: "on",
        brightness: 155
      },
      {
        device: "bathroom_shower",
        state: "on",
        brightness: 155
      },
      {
        device: "bathroom_vanityleft",
        state: "on",
        brightness: 155
      },
      {
        device: "bathroom_vanityright",
        state: "on",
        brightness: 155
      },
      {
        device: "bathroom_vanitysconces",
        state: "on",
        brightness: 155
      }
    ]
  },

  bathroom_low: {
    name: "Bathroom - Low",
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
      },
      {
        device: "bathroom_vanitysconces",
        state: "on",
        brightness: 50
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
      },
      {
        device: "bathroom_vanitysconces",
        state: "off"
      }
    ]
  },

  // ============================================================================
  // Living Room Scenes
  // ============================================================================

  living_room_high: {
    name: "Living Room - High",
    lights: [
      {
        device: "living_floor",
        state: "on",
        brightness: 255
      },
      {
        device: "living_nook",
        state: "on",
        brightness: 255
      },
      {
        device: "entry_nook",
        state: "on",
        brightness: 255
      },
      {
        device: "living_curtains",
        state: "on",
        brightness: 255
      },
      {
        device: "living_windowsillleft",
        state: "on",
        brightness: 180  // medium per legacy config
      },
      {
        device: "living_windowsillright",
        state: "on",
        brightness: 180  // medium per legacy config
      },
      {
        device: "living_behindtv",
        state: "on",
        brightness: 255
      },
      {
        device: "living_desklamps",
        state: "on",
        brightness: 255
      },
      {
        device: "living_palm",
        state: "on",
        brightness: 255
      },
      {
        device: "living_abovetv",
        state: "on",
        brightness: 255
      },
      {
        device: "living_cornerspot",
        state: "on",
        brightness: 255
      }
    ],
    switches: {
      living_ledwall: "on"
    }
  },

  living_room_medium: {
    name: "Living Room - Medium",
    lights: [
      {
        device: "living_floor",
        state: "on",
        brightness: 180
      },
      {
        device: "living_nook",
        state: "on",
        brightness: 180
      },
      {
        device: "entry_nook",
        state: "on",
        brightness: 180
      },
      {
        device: "living_curtains",
        state: "on",
        brightness: 180
      },
      {
        device: "living_windowsillleft",
        state: "off"
      },
      {
        device: "living_windowsillright",
        state: "off"
      },
      {
        device: "living_behindtv",
        state: "off"
      },
      {
        device: "living_palm",
        state: "off"
      },
      {
        device: "living_abovetv",
        state: "off"
      },
      {
        device: "living_cornerspot",
        state: "off"
      }
    ],
    switches: {
      living_ledwall: "off"
    }
  },

  living_room_low: {
    name: "Living Room - Low",
    lights: [
      {
        device: "living_floor",
        state: "on",
        brightness: 50
      },
      {
        device: "living_nook",
        state: "on",
        brightness: 50
      }
    ],
    switches: {
      living_ledwall: "off"
    }
  },

  living_room_off: {
    name: "Living Room - Off",
    lights: [
      {
        device: "living_floor",
        state: "off"
      },
      {
        device: "living_nook",
        state: "off"
      },
      {
        device: "entry_nook",
        state: "off"
      },
      {
        device: "living_curtains",
        state: "off"
      },
      {
        device: "living_windowsillleft",
        state: "off"
      },
      {
        device: "living_windowsillright",
        state: "off"
      },
      {
        device: "living_behindtv",
        state: "off"
      },
      {
        device: "living_desklamps",
        state: "off"
      },
      {
        device: "living_sliderring",
        state: "off"
      },
      {
        device: "living_palm",
        state: "off"
      },
      {
        device: "living_abovetv",
        state: "off"
      },
      {
        device: "living_cornerspot",
        state: "off"
      }
    ],
    switches: {
      living_ledwall: "off"
    }
  },

  // ============================================================================
  // Kitchen Scenes (includes dining area)
  // ============================================================================

  kitchen_high: {
    name: "Kitchen - High",
    lights: [
      {
        device: "kitchen_upper",
        state: "on",
        brightness: 255,
        rgbw_color: [5, 4, 0, 255]  // Warm white
      },
      {
        device: "kitchen_upper_white",
        state: "on"
      },
      {
        device: "kitchen_lower",
        state: "on",
        brightness: 255,
        rgbw_color: [5, 4, 0, 255]  // Warm white
      },
      {
        device: "kitchen_lower_white",
        state: "on"
      },
      {
        device: "kitchen_ring",
        state: "on"
      },
      {
        device: "kitchen_hanging",
        state: "on"
      },
      {
        device: "kitchen_dining_nook",
        state: "on",
        brightness: 255,
        rgbw_color: [5, 4, 0, 255]  // Warm white
      }
    ]
  },

  kitchen_medium: {
    name: "Kitchen - Medium",
    lights: [
      {
        device: "kitchen_upper",
        state: "on",
        brightness: 180,
        rgbw_color: [5, 4, 0, 180]  // Warm white
      },
      {
        device: "kitchen_upper_white",
        state: "on"
      },
      {
        device: "kitchen_lower",
        state: "on",
        brightness: 180,
        rgbw_color: [5, 4, 0, 180]  // Warm white
      },
      {
        device: "kitchen_lower_white",
        state: "on"
      },
      {
        device: "kitchen_ring",
        state: "on"
      },
      {
        device: "kitchen_hanging",
        state: "on"
      },
      {
        device: "kitchen_dining_nook",
        state: "on",
        brightness: 180,
        rgbw_color: [5, 4, 0, 180]  // Warm white
      }
    ]
  },

  kitchen_low: {
    name: "Kitchen - Low",
    lights: [
      {
        device: "kitchen_upper",
        state: "off"
      },
      {
        device: "kitchen_upper_white",
        state: "off"
      },
      {
        device: "kitchen_lower",
        state: "off"
      },
      {
        device: "kitchen_lower_white",
        state: "off"
      },
      {
        device: "kitchen_ring",
        state: "off"
      },
      {
        device: "kitchen_hanging",
        state: "on"
      },
      {
        device: "kitchen_dining_nook",
        state: "on",
        brightness: 50,
        rgbw_color: [5, 4, 0, 50]  // Warm white dim
      }
    ]
  },

  kitchen_off: {
    name: "Kitchen - Off",
    lights: [
      {
        device: "kitchen_upper",
        state: "off"
      },
      {
        device: "kitchen_upper_white",
        state: "off"
      },
      {
        device: "kitchen_lower",
        state: "off"
      },
      {
        device: "kitchen_lower_white",
        state: "off"
      },
      {
        device: "kitchen_ring",
        state: "off"
      },
      {
        device: "kitchen_hanging",
        state: "off"
      },
      {
        device: "kitchen_dining_nook",
        state: "off"
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
