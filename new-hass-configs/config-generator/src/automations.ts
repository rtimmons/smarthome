/**
 * Home Assistant Automation Definitions
 *
 * This file defines all automations in the smart home system.
 * Automations connect triggers (events) to actions (what to do).
 *
 * TODO: Migrate automations from legacy metaconfig.yaml
 *       Reference devices and scenes using logical names from devices.ts and scenes.ts
 */

import { AutomationRegistry } from "./types";

/**
 * Automation Registry
 *
 * Defines all automations in the system.
 * Each automation consists of:
 *   - trigger: What event starts the automation
 *   - condition: Optional conditions that must be met
 *   - action: What to do when triggered
 *
 * Example usage:
 *   automations.bedroom_switch_doubleup -> { alias: "...", trigger: {...}, action: {...} }
 *
 * Naming convention:
 *   <room>_<device>_<event> - e.g., bedroom_switch_doubleup, office_webhook_high
 */
export const automations: AutomationRegistry = {
  // ============================================================================
  // Office Switch Automations
  // ============================================================================

  office_switch_doubleup: {
    alias: "office_toggle_doubledown",
    description: "Turn on all office lights on double-tap up",
    trigger: {
      type: "zwave_js_scene",
      device: "office_wall_switch",
      event: "doubleUp"
    },
    action: {
      type: "scene",
      scene: "office_toggle_doubleup"
    },
    mode: "single"
  },

  office_switch_doubledown: {
    alias: "office_toggle_doubledown",
    description: "Turn off all office lights on double-tap down",
    trigger: {
      type: "zwave_js_scene",
      device: "office_wall_switch",
      event: "doubleDown"
    },
    action: {
      type: "scene",
      scene: "office_toggle_doubledown"
    },
    mode: "single"
  },
};

/**
 * Helper function to get an automation by key
 */
export function getAutomation(key: string) {
  const automation = automations[key];
  if (!automation) {
    throw new Error(`Automation not found: ${key}`);
  }
  return automation;
}
