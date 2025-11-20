/**
 * Home Assistant Device Registry
 *
 * This file defines all physical devices in the smart home system.
 * It maps logical device names to their Home Assistant entity IDs and capabilities.
 *
 * TODO: Populate this registry with actual devices from the legacy metaconfig.yaml
 *       after running `just fetch` to get current entity names from Z-Wave JS.
 */

import { DeviceRegistry } from "./types";

/**
 * Device Registry
 *
 * Maps logical device names to Home Assistant entities and their capabilities.
 * This registry serves as the single source of truth for all devices.
 *
 * Example usage:
 *   devices.lights.bedroom_main -> { entity: "light.bedroom_ceiling_rgbw", ... }
 */
export const devices: DeviceRegistry = {
  // ============================================================================
  // Lights
  // ============================================================================
  lights: {
    // Office lights - RGBW Zooz Zen31 devices (have both RGBW and separate white channels)
    office_abovecouch: {
      entity: "light.light_office_abovecouch",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    office_abovecouch_white: {
      entity: "light.light_office_abovecouch_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    office_abovetv: {
      entity: "light.light_office_abovetv",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    office_abovetv_white: {
      entity: "light.light_office_abovetv_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    office_sidetable: {
      entity: "light.office_light_sidetable",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },

    // Bathroom lights - Z-Wave dimmers with non-dimmable fixtures (on/off only)
    bathroom_sauna: {
      entity: "light.bathroom_light_sauna",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    bathroom_shower: {
      entity: "light.bathroom_light_shower",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    bathroom_vanityleft: {
      entity: "light.bathroom_light_vanityleft",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    bathroom_vanityright: {
      entity: "light.bathroom_light_vanityright",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    bathroom_vanitysconces: {
      entity: "light.bathroom_light_vanitysconces",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },

    // Living room lights - mix of Hue and Z-Wave
    living_floor: {
      entity: "light.living_light_floor",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    living_nook: {
      entity: "light.living_light_nook",
      type: "color_light",
      capabilities: ["brightness", "color_temp"]
    },
    entry_nook: {
      entity: "light.entry_light_nook",
      type: "color_light",
      capabilities: ["brightness", "color_temp"]
    },
    living_corner: {
      entity: "light.living_light_corner",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    living_curtains: {
      entity: "light.light_living_curtains",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_curtains_white: {
      entity: "light.light_living_curtains_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_windowsillleft: {
      entity: "light.light_living_windowsillleft",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_windowsillleft_white: {
      entity: "light.light_living_windowsillleft_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_windowsillright: {
      entity: "light.light_living_windowsillright",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_windowsillright_white: {
      entity: "light.light_living_windowsillright_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_behindtv: {
      entity: "light.light_living_behindtv",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_behindtv_white: {
      entity: "light.light_living_behindtv_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_desklamps: {
      entity: "light.light_living_desklamps",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_sliderring: {
      entity: "light.light_living_sliderring",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_palm: {
      entity: "light.light_living_palm",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_abovetv: {
      entity: "light.light_living_abovetv",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_abovetv_white: {
      entity: "light.light_living_abovetv_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_cornerspot: {
      entity: "light.light_living_cornerspot",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_hallway: {
      entity: "light.light_living_hallway",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },

    // Kitchen lights (including dining area)
    kitchen_upper: {
      entity: "light.light_kitchen_upper",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    kitchen_upper_white: {
      entity: "light.light_kitchen_upper_white",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    kitchen_lower: {
      entity: "light.light_kitchen_lower",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    kitchen_lower_white: {
      entity: "light.light_kitchen_lower_white",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    kitchen_ring: {
      entity: "light.light_kitchen_ring",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    kitchen_hanging: {
      entity: "light.light_kitchen_hanging",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    kitchen_dining_nook: {
      entity: "light.light_dining_nook",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    kitchen_dining_nook_white: {
      entity: "light.light_dining_nook_white",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    dining_abovetable: {
      entity: "light.light_dining_abovetable",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },

    // Bedroom lights - Hue
    bedroom_dresser: {
      entity: "light.bedroom_light_dresser",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bedroom_mikedesk: {
      entity: "light.bedroom_light_mikedesk",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bedroom_flamingo: {
      entity: "light.bedroom_light_flamingo",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
  },

  // ============================================================================
  // Switches (Z-Wave switches that control lights)
  // ============================================================================
  switches: {
    // Office wall switch - Z-Wave Central Scene device
    office_wall_switch: {
      entity: "switch.office_wall_switch",  // TODO: Find actual entity ID
      type: "zwave_dimmer_46203",
      device_id: "44ca863fc3d89c94bdfb7471c370a932",
      events: {
        singleUp: {
          command_class_name: "Central Scene",
          property_key_name: "001",
          value: "KeyPressed"
        },
        singleDown: {
          command_class_name: "Central Scene",
          property_key_name: "002",
          value: "KeyPressed"
        },
        doubleUp: {
          command_class_name: "Central Scene",
          property_key_name: "001",
          value: "KeyPressed2x"
        },
        doubleDown: {
          command_class_name: "Central Scene",
          property_key_name: "002",
          value: "KeyPressed2x"
        },
        tripleUp: {
          command_class_name: "Central Scene",
          property_key_name: "001",
          value: "KeyPressed3x"
        },
        tripleDown: {
          command_class_name: "Central Scene",
          property_key_name: "002",
          value: "KeyPressed3x"
        },
        holdStart: {
          command_class_name: "Central Scene",
          property_key_name: "001",
          value: "KeyHeldDown"
        },
        holdEnd: {
          command_class_name: "Central Scene",
          property_key_name: "001",
          value: "KeyReleased"
        }
      }
    },

    // Bedroom bedside switch - Z-Wave Central Scene device
    bedroom_switch_bedside: {
      entity: "switch.bedroom_switch_bedside",
      type: "zwave_dimmer_46203",
      device_id: "TODO_DEVICE_ID",  // TODO: Get actual device_id from Home Assistant
      events: {
        singleUp: {
          command_class_name: "Central Scene",
          property_key_name: "001",
          value: "KeyPressed"
        },
        singleDown: {
          command_class_name: "Central Scene",
          property_key_name: "002",
          value: "KeyPressed"
        },
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
    },
  },

  // ============================================================================
  // Outlets (Smart outlets/plugs)
  // ============================================================================
  outlets: {
    // Office piano light (controlled as a switch)
    office_pianolight: {
      entity: "switch.light_office_pianolight",
      type: "outlet",
      capabilities: ["on_off"]
    },

    // Living room LED wall
    living_ledwall: {
      entity: "switch.light_living_ledwall",
      type: "outlet",
      capabilities: ["on_off"]
    },
  },

  // ============================================================================
  // Sensors (Optional - for automations based on sensor states)
  // ============================================================================
  sensors: {
    // Example sensor
    // bedroom_motion: {
    //   entity: "binary_sensor.bedroom_motion",
    //   type: "motion_sensor",
    // },
  },
};

/**
 * Helper function to get a device by logical name
 */
export function getDevice(category: keyof DeviceRegistry, name: string) {
  const device = devices[category]?.[name];
  if (!device) {
    throw new Error(`Device not found: ${category}.${name}`);
  }
  return device;
}

/**
 * Helper function to get a light entity ID
 */
export function getLightEntity(name: string): string {
  return getDevice("lights", name).entity;
}

/**
 * Helper function to get a switch entity ID
 */
export function getSwitchEntity(name: string): string {
  return getDevice("switches", name).entity;
}

/**
 * Helper function to get an outlet entity ID
 */
export function getOutletEntity(name: string): string {
  return getDevice("outlets", name).entity;
}

/**
 * Helper function to get the paired device name (if it exists)
 *
 * For RGBW devices with separate white channels:
 * - "office_abovetv" returns "office_abovetv_white"
 * - "office_abovetv_white" returns "office_abovetv"
 *
 * Returns null if no paired device exists.
 */
export function getPairedDeviceName(deviceName: string): string | null {
  // Check if this is a _white device
  if (deviceName.endsWith("_white")) {
    const baseName = deviceName.replace(/_white$/, "");
    // Check if the non-white version exists
    if (devices.lights[baseName]) {
      return baseName;
    }
  } else {
    // Check if a _white version exists
    const whiteName = `${deviceName}_white`;
    if (devices.lights[whiteName]) {
      return whiteName;
    }
  }

  return null;
}

/**
 * Helper function to check if a device has a paired device
 */
export function hasPairedDevice(deviceName: string): boolean {
  return getPairedDeviceName(deviceName) !== null;
}

/**
 * Helper function to get both a device and its pair (if it exists)
 * Returns an array of device names [original, paired] or just [original] if no pair exists
 */
export function getDeviceWithPair(deviceName: string): string[] {
  const pairedName = getPairedDeviceName(deviceName);
  return pairedName ? [deviceName, pairedName] : [deviceName];
}
