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
    alias: "Office Switch - Double Up → High",
    description: "Turn on all office lights on double-tap up",
    trigger: {
      type: "zwave_js_scene",
      device: "office_wall_switch",
      event: "doubleUp"
    },
    action: {
      type: "scene",
      scene: "office_high"
    },
    mode: "single"
  },

  office_switch_doubledown: {
    alias: "Office Switch - Double Down → Off",
    description: "Turn off all office lights on double-tap down",
    trigger: {
      type: "zwave_js_scene",
      device: "office_wall_switch",
      event: "doubleDown"
    },
    action: {
      type: "scene",
      scene: "office_off"
    },
    mode: "single"
  },

  // ============================================================================
  // Office Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  office_webhook_high: {
    alias: "Office Webhook → High",
    description: "Dashboard button: Office High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_office_high"
    },
    action: {
      type: "scene",
      scene: "office_high"
    },
    mode: "single"
  },

  office_webhook_medium: {
    alias: "Office Webhook → Medium",
    description: "Dashboard button: Office Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_office_medium"
    },
    action: {
      type: "scene",
      scene: "office_medium"
    },
    mode: "single"
  },

  office_webhook_off: {
    alias: "Office Webhook → Off",
    description: "Dashboard button: Office Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_office_off"
    },
    action: {
      type: "scene",
      scene: "office_off"
    },
    mode: "single"
  },

  // ============================================================================
  // Bathroom Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  bathroom_webhook_high: {
    alias: "Bathroom Webhook → High",
    description: "Dashboard button: Bathroom High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bathroom_high"
    },
    action: {
      type: "scene",
      scene: "bathroom_high"
    },
    mode: "single"
  },

  bathroom_webhook_medium: {
    alias: "Bathroom Webhook → Medium",
    description: "Dashboard button: Bathroom Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bathroom_medium"
    },
    action: {
      type: "scene",
      scene: "bathroom_medium"
    },
    mode: "single"
  },

  bathroom_webhook_off: {
    alias: "Bathroom Webhook → Off",
    description: "Dashboard button: Bathroom Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bathroom_off"
    },
    action: {
      type: "scene",
      scene: "bathroom_off"
    },
    mode: "single"
  },

  // ============================================================================
  // Living Room Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  living_room_webhook_high: {
    alias: "Living Room Webhook → High",
    description: "Dashboard button: Living Room High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_living_room_high"
    },
    action: {
      type: "scene",
      scene: "living_room_high"
    },
    mode: "single"
  },

  living_room_webhook_medium: {
    alias: "Living Room Webhook → Medium",
    description: "Dashboard button: Living Room Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_living_room_medium"
    },
    action: {
      type: "scene",
      scene: "living_room_medium"
    },
    mode: "single"
  },

  living_room_webhook_off: {
    alias: "Living Room Webhook → Off",
    description: "Dashboard button: Living Room Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_living_room_off"
    },
    action: {
      type: "scene",
      scene: "living_room_off"
    },
    mode: "single"
  },

  // ============================================================================
  // Kitchen Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  kitchen_webhook_high: {
    alias: "Kitchen Webhook → High",
    description: "Dashboard button: Kitchen High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_kitchen_high"
    },
    action: {
      type: "scene",
      scene: "kitchen_high"
    },
    mode: "single"
  },

  kitchen_webhook_medium: {
    alias: "Kitchen Webhook → Medium",
    description: "Dashboard button: Kitchen Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_kitchen_medium"
    },
    action: {
      type: "scene",
      scene: "kitchen_medium"
    },
    mode: "single"
  },

  kitchen_webhook_off: {
    alias: "Kitchen Webhook → Off",
    description: "Dashboard button: Kitchen Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_kitchen_off"
    },
    action: {
      type: "scene",
      scene: "kitchen_off"
    },
    mode: "single"
  },

  // ============================================================================
  // All Off Webhook Automation (Dashboard Moon Button Double-Tap)
  // ============================================================================

  all_off_webhook: {
    alias: "All Off Webhook",
    description: "Dashboard Moon button double-tap: Turn off all lights except bedroom sconces",
    trigger: {
      type: "webhook",
      webhook_id: "scene_all_off"
    },
    action: {
      type: "scene",
      scene: "all_off"
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
