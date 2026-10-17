/**
 * Home Assistant Device Registry
 *
 * This file defines logical lighting targets and wall-switch controls.
 * It maps logical device names to their Home Assistant entity IDs and capabilities.
 *
 * Physical placements and non-lighting devices are cataloged in
 * home-model/device-catalog.json. Area metadata never expands scene targets.
 */

import { DeviceRegistry } from "./types";

/**
 * Device Registry
 *
 * Maps logical device names to Home Assistant entities and their capabilities.
 * Area declarations are checked against the shared physical device catalog.
 *
 * Example usage:
 *   devices.lights.bedroom_main -> { entity: "light.bedroom_ceiling_rgbw", ... }
 */
export const devices: DeviceRegistry = {
  // ============================================================================
  // Lights
  // ============================================================================
  lights: {
    // Software output control; scene off means zero brightness, never mains off.
    led_grid_wall: {
      entity: "light.led_grid_wall",
      areaId: "living_room",
      type: "dimmer_light",
      capabilities: ["brightness"],
      sceneControl: "led_grid_wall"
    },
    // Office lights - RGBW Zooz Zen31 devices (have both RGBW and separate white channels)
    office_abovecouch: {
      entity: "light.light_office_abovecouch",
      areaId: "office",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    office_abovecouch_white: {
      entity: "light.light_office_abovecouch_white",
      areaId: "office",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    office_abovetv: {
      entity: "light.light_office_abovetv",
      areaId: "office",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    lights_office_abovetv: {
      entity: "light.light_office_abovetv",
      areaId: "office",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    office_abovetv_white: {
      entity: "light.light_office_abovetv_white",
      areaId: "office",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    office_sidetable: {
      entity: "light.office_light_sidetable",
      areaId: "office",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    office_toggle: {
      entity: "light.light_office_toggle",
      areaId: "office",
      type: "zwave_dimmer_46203",
      capabilities: ["brightness"]
    },

    // Bathroom lights - Zigbee lights
    bathroom_vanity_left: {
      entity: "light.light_bathroom_vanity_left",
      areaId: "bathroom",
      type: "color_light",
      protocol: "zigbee",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bathroom_vanity_right: {
      entity: "light.light_bathroom_vanity_right",
      areaId: "bathroom",
      type: "color_light",
      protocol: "zigbee",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bathroom_abovesauna: {
      entity: "light.light_bathroom_abovesauna",
      areaId: "bathroom",
      type: "color_light",
      protocol: "zigbee",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bathroom_edison_top: {
      entity: "light.light_bathroom_edison_top",
      areaId: "bathroom",
      type: "dimmer_light",
      protocol: "zigbee",
      capabilities: ["brightness"]
    },
    bathroom_edison_bottom: {
      entity: "light.light_bathroom_edison_bottom",
      areaId: "bathroom",
      type: "dimmer_light",
      protocol: "zigbee",
      capabilities: ["brightness"]
    },

    // Living room lights - mix of Hue and Z-Wave
    living_floor: {
      entity: "light.living_light_floor",
      areaId: "living_room",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    entry_nook: {
      entity: "light.entry_light_nook",
      areaId: "living_room",
      type: "color_light",
      capabilities: ["brightness", "color_temp"]
    },
    living_curtains: {
      entity: "light.light_living_curtains",
      areaId: "living_room",
      type: "zwave_zen31_rgbw",
      fastSceneForceOnDispatch: true,
      capabilities: ["brightness", "rgbw_color"]
    },
    living_curtains_white: {
      entity: "light.light_living_curtains_white",
      areaId: "living_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_windowsillleft: {
      entity: "light.light_living_windowsillleft",
      areaId: "living_room",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_windowsillleft_white: {
      entity: "light.light_living_windowsillleft_white",
      areaId: "living_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_windowsillright: {
      entity: "light.light_living_windowsillright",
      areaId: "living_room",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_windowsillright_white: {
      entity: "light.light_living_windowsillright_white",
      areaId: "living_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_behindtv: {
      entity: "light.light_living_behindtv",
      areaId: "living_room",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_behindtv_white: {
      entity: "light.light_living_behindtv_white",
      areaId: "living_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_desklamps: {
      entity: "light.light_living_desklamps",
      areaId: "living_room",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_sliderring: {
      entity: "light.light_living_sliderring",
      areaId: "living_room",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_abovetv: {
      entity: "light.light_living_abovetv",
      areaId: "living_room",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    living_abovetv_white: {
      entity: "light.light_living_abovetv_white",
      areaId: "living_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    living_cornerspot: {
      entity: "light.light_living_cornerspot",
      areaId: "living_room",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    living_hallway: {
      entity: "light.light_living_hallway",
      areaId: "living_room",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    outdoor_cafe: {
      entity: "light.light_outdoor_cafe",
      areaId: "outdoor",
      type: "zwave_switch_light",
      inventoryStatus: "temporarily_removed",
      capabilities: ["on_off"]
    },
    outdoor_sconces: {
      entity: "light.light_outdoor_sconces",
      areaId: "outdoor",
      type: "zwave_dimmer_46203",
      capabilities: ["brightness"]
    },
    makerroom_main: {
      entity: "light.light_makerroom_main",
      areaId: "maker_room",
      type: "zwave_dimmer_46203",
      capabilities: ["brightness"]
    },
    makerroom_undershelf: {
      entity: "light.light_makerroom_undershelf",
      areaId: "maker_room",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    makerroom_undershelf_white: {
      entity: "light.light_makerroom_undershelf_white",
      areaId: "maker_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },

    // Kitchen lights (including dining area)
    kitchen_upper: {
      entity: "light.light_kitchen_upper",
      areaId: "kitchen",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    kitchen_upper_white: {
      entity: "light.light_kitchen_upper_white",
      areaId: "kitchen",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    kitchen_lower: {
      entity: "light.light_kitchen_lower",
      areaId: "kitchen",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    kitchen_lower_white: {
      entity: "light.light_kitchen_lower_white",
      areaId: "kitchen",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    kitchen_ring: {
      entity: "light.light_kitchen_ring",
      areaId: "kitchen",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    kitchen_hanging: {
      entity: "light.light_kitchen_hanging",
      areaId: "kitchen",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    kitchen_dining_nook: {
      entity: "light.light_dining_nook",
      areaId: "dining_room",
      type: "zwave_zen31_rgbw",
      capabilities: ["brightness", "rgbw_color"]
    },
    kitchen_dining_nook_white: {
      entity: "light.light_dining_nook_white",
      areaId: "dining_room",
      type: "dimmer_light",
      capabilities: ["brightness"]
    },
    dining_abovetable: {
      entity: "light.light_dining_abovetable",
      areaId: "dining_room",
      type: "zwave_switch_light",
      capabilities: ["on_off"]
    },
    guestbathroom_overhead: {
      entity: "light.light_guestbathroom_overhead",
      areaId: "guest_bathroom",
      type: "zwave_dimmer_46203",
      // Node 23 changes its load locally but repeatedly times out acknowledging
      // commands. The physical paddle remains an automation trigger; scenes
      // temporarily control only the healthy guest-bathroom sconce.
      sceneStatus: "temporarily_excluded",
      capabilities: ["brightness"]
    },
    guestbathroom_sconce: {
      entity: "light.light_guestbathroom_sconce",
      areaId: "guest_bathroom",
      type: "zwave_dimmer_46203",
      capabilities: ["brightness"]
    },
    closet_main: {
      entity: "light.light_closet_main",
      areaId: "closet",
      type: "zwave_dimmer_46203",
      capabilities: ["brightness"]
    },

    // Bedroom lights - Hue
    bedroom_dresser: {
      entity: "light.bedroom_light_dresser",
      areaId: "bedroom",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bedroom_flamingo: {
      entity: "light.bedroom_light_flamingo",
      areaId: "bedroom",
      type: "color_light",
      capabilities: ["brightness", "color_temp", "rgb_color"]
    },
    bedroom_sconces: {
      entity: "light.light_bedroom_sconces",
      areaId: "bedroom",
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
      entity: "light.light_office_toggle",
      areaId: "office",
      type: "zwave_dimmer_46203",
      includeInAllOff: false,
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

    // Bedroom sconces switch - Z-Wave Central Scene device (GE/Enbrighten 46203)
    bedroom_switch_sconces: {
      entity: "light.light_bedroom_sconces",
      areaId: "bedroom",
      type: "zwave_dimmer_46203",
      device_id: "a5b63da64e115065d5b0ed424de805d5",
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

    // Guest bathroom overhead switch - controls both guest bathroom lights via scenes
    guestbathroom_switch: {
      entity: "light.light_guestbathroom_overhead",
      areaId: "guest_bathroom",
      type: "zwave_dimmer_46203",
      // Same node-23 load as lights.guestbathroom_overhead. Keep its Central
      // Scene events active while suppressing generated commands to the load.
      sceneStatus: "temporarily_excluded",
      device_id: "df50c0c6853f8878742f1917f44f3060",
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

    // Guest bathroom sconce switch - also triggers shared scenes
    guestbathroom_sconce_switch: {
      entity: "light.light_guestbathroom_sconce",
      areaId: "guest_bathroom",
      type: "zwave_dimmer_46203",
      device_id: "59fbd1c8d089fc4b6cab59f7bd20b085",
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

    // Living hallway wall dimmer - used as a scene controller for whole-home off
    living_hallway_switch: {
      entity: "light.light_living_hallway",
      areaId: "living_room",
      type: "zwave_dimmer_46203",
      includeInAllOff: false,
      device_id: "c136100e5d6664e5b6fa256eaeb6c9b3",
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
      areaId: "office",
      type: "outlet",
      capabilities: ["on_off"]
    },
    living_sillleftpower: {
      entity: "switch.light_living_sillleftpower",
      areaId: "living_room",
      type: "zwave_outlet",
      // Node 28 is dead. Preserve it in inventory, but send it no scene traffic.
      sceneStatus: "temporarily_excluded",
      capabilities: ["on_off"]
    },
    dining_weenie: {
      entity: "switch.light_dining_weenie",
      areaId: "dining_room",
      type: "outlet",
      capabilities: ["on_off"]
    },

    // Living room LED wall
    living_ledwall: {
      entity: "switch.light_living_ledwall",
      areaId: "living_room",
      type: "outlet",
      includeInAllOff: false,
      allowSceneTurnOff: false,
      capabilities: ["on_off"]
    },

    // Bedroom flamingo power - Controls the flamingo Hue light
    bedroom_flamingopower: {
      entity: "switch.light_bedroom_flamingopower",
      areaId: "bedroom",
      type: "outlet",
      includeInAllOff: false,
      allowSceneTurnOff: false,
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
