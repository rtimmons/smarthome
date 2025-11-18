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

    // Bathroom lights - Z-Wave dimmers (brightness only)
    bathroom_abovesauna: {
      entity: "light.light_bathroom_abovesauna",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    bathroom_vanityleft: {
      entity: "light.light_bathroom_vanityleft",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    bathroom_vanityright: {
      entity: "light.light_bathroom_vanityright",
      type: "dimmer_light",
      capabilities: ["brightness"]
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
