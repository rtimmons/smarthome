/**
 * Home Assistant Scene Definitions
 *
 * This file defines all scenes in the smart home system.
 * Scenes describe desired states for lights and other devices.
 *
 * TODO: Fill out scenes for remaining rooms using devices.ts as the source of truth
 */

import { SceneRegistry, Scene } from "./types";
import { devices } from "./devices";

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
        device: "office_abovecouch_white",
        state: "on",
        brightness: 255
      },
      {
        device: "office_abovetv_white",
        state: "on",
        brightness: 255
      },
      {
        device: "lights_office_abovetv",
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
        device: "office_abovecouch_white",
        state: "on",
        brightness: 180
      },
      {
        device: "office_abovetv_white",
        state: "on",
        brightness: 180
      },
      {
        device: "lights_office_abovetv",
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
        device: "lights_office_abovetv",
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
  // Guest Bathroom Scenes
  // ============================================================================

  guest_bathroom_high: {
    name: "Guest Bathroom - High",
    lights: [
      {
        device: "guestbathroom_overhead",
        state: "on",
        brightness: 255
      },
      {
        device: "guestbathroom_sconce",
        state: "on",
        brightness: 255
      }
    ]
  },

  guest_bathroom_medium: {
    name: "Guest Bathroom - Medium (50%)",
    lights: [
      {
        device: "guestbathroom_overhead",
        state: "on",
        brightness: 128
      },
      {
        device: "guestbathroom_sconce",
        state: "on",
        brightness: 128
      }
    ]
  },

  guest_bathroom_off: {
    name: "Guest Bathroom - Off",
    lights: [
      {
        device: "guestbathroom_overhead",
        state: "off"
      },
      {
        device: "guestbathroom_sconce",
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
        device: "living_curtains_white",
        state: "on",
        brightness: 255
      },
      {
        device: "living_windowsillleft_white",
        state: "on",
        brightness: 180
      },
      {
        device: "living_windowsillright_white",
        state: "on",
        brightness: 180
      },
      {
        device: "living_behindtv_white",
        state: "on",
        brightness: 255
      },
      {
        device: "living_desklamps",
        state: "on",
        brightness: 255
      },
      {
        device: "living_sliderring",
        state: "on",
        brightness: 255
      },
      {
        device: "living_palm",
        state: "on",
        brightness: 255
      },
      {
        device: "living_corner",
        state: "on",
        brightness: 255
      },
      {
        device: "living_abovetv_white",
        state: "on",
        brightness: 255
      },
      {
        device: "living_cornerspot",
        state: "on",
        brightness: 255
      },
      {
        device: "living_hallway",
        state: "on",
        brightness: 255
      }
    ],
    switches: {
      living_ledwall: "on",
      living_sillleftpower: "on"
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
        device: "living_curtains_white",
        state: "on",
        brightness: 180
      },
      {
        device: "living_windowsillleft_white",
        state: "off"
      },
      {
        device: "living_windowsillright_white",
        state: "off"
      },
      {
        device: "living_behindtv_white",
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
        device: "living_corner",
        state: "off"
      },
      {
        device: "living_abovetv_white",
        state: "off"
      },
      {
        device: "living_cornerspot",
        state: "off"
      },
      {
        device: "living_hallway",
        state: "off"
      }
    ],
    switches: {
      living_ledwall: "off",
      living_sillleftpower: "off"
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
      living_ledwall: "off",
      living_sillleftpower: "off"
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
        device: "living_curtains_white",
        state: "off"
      },
      {
        device: "living_windowsillleft_white",
        state: "off"
      },
      {
        device: "living_windowsillright_white",
        state: "off"
      },
      {
        device: "living_behindtv_white",
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
        device: "living_corner",
        state: "off"
      },
      {
        device: "living_abovetv_white",
        state: "off"
      },
      {
        device: "living_cornerspot",
        state: "off"
      },
      {
        device: "living_hallway",
        state: "off"
      }
    ],
    switches: {
      living_ledwall: "off",
      living_sillleftpower: "off"
    }
  },

  // ============================================================================
  // Kitchen Scenes (includes dining area)
  // ============================================================================

  kitchen_high: {
    name: "Kitchen - High",
    lights: [
      {
        device: "kitchen_upper_white",
        state: "on",
        brightness: 255
      },
      {
        device: "kitchen_lower_white",
        state: "on",
        brightness: 255
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
        device: "kitchen_dining_nook_white",
        state: "on",
        brightness: 255
      },
      {
        device: "dining_abovetable",
        state: "on",
        brightness: 255
      }
    ]
  },

  kitchen_medium: {
    name: "Kitchen - Medium",
    lights: [
      {
        device: "kitchen_upper_white",
        state: "on",
        brightness: 180
      },
      {
        device: "kitchen_lower_white",
        state: "on",
        brightness: 180
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
        device: "kitchen_dining_nook_white",
        state: "on",
        brightness: 180
      },
      {
        device: "dining_abovetable",
        state: "on",
        brightness: 180
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
        device: "kitchen_dining_nook_white",
        state: "on",
        brightness: 50
      },
      {
        device: "dining_abovetable",
        state: "on",
        brightness: 50
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
      },
      {
        device: "kitchen_dining_nook_white",
        state: "off"
      },
      {
        device: "dining_abovetable",
        state: "off"
      }
    ]
  },

  // ============================================================================
  // Bedroom Scenes
  // ============================================================================

  bedroom_high: {
    name: "Bedroom - High",
    lights: [
      {
        device: "bedroom_sconces",
        state: "on",
        brightness: 255
      },
      {
        device: "bedroom_dresser",
        state: "on",
        brightness: 255
      },
      {
        device: "bedroom_mikedesk",
        state: "on",
        brightness: 255
      },
      {
        device: "bedroom_flamingo",
        state: "on",
        brightness: 255
      }
    ],
    switches: {
      bedroom_flamingopower: "on"
    }
  },

  bedroom_medium: {
    name: "Bedroom - Medium",
    lights: [
      {
        device: "bedroom_sconces",
        state: "on",
        brightness: 180
      },
      {
        device: "bedroom_dresser",
        state: "on",
        brightness: 180
      },
      {
        device: "bedroom_mikedesk",
        state: "on",
        brightness: 180
      },
      {
        device: "bedroom_flamingo",
        state: "on",
        brightness: 180
      }
    ],
    switches: {
      bedroom_flamingopower: "on"
    }
  },

  bedroom_low: {
    name: "Bedroom - Low",
    lights: [
      {
        device: "bedroom_sconces",
        state: "on",
        brightness: 50
      },
      {
        device: "bedroom_dresser",
        state: "off"
      },
      {
        device: "bedroom_mikedesk",
        state: "off"
      },
      {
        device: "bedroom_flamingo",
        state: "off"
      }
    ],
    switches: {
      bedroom_flamingopower: "off"
    }
  },

  bedroom_off: {
    name: "Bedroom - Off",
    lights: [
      {
        device: "bedroom_sconces",
        state: "off"
      },
      {
        device: "bedroom_dresser",
        state: "off"
      },
      {
        device: "bedroom_mikedesk",
        state: "off"
      },
      {
        device: "bedroom_flamingo",
        state: "off"
      }
    ],
    switches: {
      bedroom_flamingopower: "off"
    }
  },

  // ============================================================================
  // All Off Scene (Generated)
  // ============================================================================
  // This scene automatically includes all lights, switches, and outlets
  // except those in the blocklist
  ...generateAllOffScene(),
};

/**
 * Generate the "All Off" scene
 *
 * Automatically creates a scene that turns off all lights, switches, and outlets
 * except those in the blocklist.
 *
 * Blocklist: Devices that should NOT be turned off by the all_off scene
 */
function generateAllOffScene(): { all_off: Scene } {
  const blocklist = [
    "bedroom_switch_bedside",  // Bedroom sconces - user requested to exclude
  ];

  const lights: Array<{ device: string; state: "off" }> = [];
  const switches: Record<string, "on" | "off"> = {};

  // Collect all lights (except blocklisted ones)
  for (const [deviceName, _device] of Object.entries(devices.lights)) {
    if (!blocklist.includes(deviceName)) {
      lights.push({
        device: deviceName,
        state: "off"
      });
    }
  }

  // Collect all switches (except blocklisted ones)
  for (const [deviceName, _device] of Object.entries(devices.switches)) {
    if (!blocklist.includes(deviceName)) {
      switches[deviceName] = "off";
    }
  }

  // Collect all outlets (except blocklisted ones)
  for (const [deviceName, _device] of Object.entries(devices.outlets)) {
    if (!blocklist.includes(deviceName)) {
      switches[deviceName] = "off";
    }
  }

  return {
    all_off: {
      name: "All Off",
      lights,
      switches,
    }
  };
}

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
