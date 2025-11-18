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

  office_toggle_doubleup: {
    name: "office_toggle_doubleup",
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

  office_toggle_doubledown: {
    name: "office_toggle_doubledown",
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
