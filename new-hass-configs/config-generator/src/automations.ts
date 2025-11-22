/**
 * Home Assistant Automation Definitions
 *
 * This file defines all automations in the smart home system.
 * Automations connect triggers (events) to actions (what to do).
 *
 * TODO: Add remaining automations using logical device/scene names from devices.ts and scenes.ts
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
  // Bedroom Switch Automations
  // ============================================================================

  bedroom_switch_doubleup: {
    alias: "Bedroom Switch - Double Up → High",
    description: "Turn on all bedroom lights on double-tap up",
    trigger: {
      type: "zwave_js_scene",
      device: "bedroom_switch_sconces",
      event: "doubleUp"
    },
    action: {
      type: "scene",
      scene: "bedroom_high"
    },
    mode: "single"
  },

  bedroom_switch_doubledown: {
    alias: "Bedroom Switch - Double Down → Off",
    description: "Turn off all bedroom lights on double-tap down",
    trigger: {
      type: "zwave_js_scene",
      device: "bedroom_switch_sconces",
      event: "doubleDown"
    },
    action: {
      type: "scene",
      scene: "bedroom_off"
    },
    mode: "single"
  },

  // ============================================================================
  // Guest Bathroom Switch Automations
  // ============================================================================

  guest_bathroom_switch_doubleup: {
    alias: "Guest Bathroom Switch - Double Up → High",
    description: "Turn on both guest bathroom lights to full on double-tap up",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_switch",
      event: "doubleUp"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_high"
    },
    mode: "single"
  },

  guest_bathroom_switch_singleup: {
    alias: "Guest Bathroom Switch - Single Up → 50%",
    description: "Set both guest bathroom lights to 50% on single tap up",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_switch",
      event: "singleUp"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_medium"
    },
    mode: "single"
  },

  guest_bathroom_switch_doubledown: {
    alias: "Guest Bathroom Switch - Double Down → Off",
    description: "Turn off both guest bathroom lights on double-tap down",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_switch",
      event: "doubleDown"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_off"
    },
    mode: "single"
  },

  guest_bathroom_switch_singledown: {
    alias: "Guest Bathroom Switch - Single Down → Off",
    description: "Turn off both guest bathroom lights on single tap down",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_switch",
      event: "singleDown"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_off"
    },
    mode: "single"
  },

  guest_bathroom_sconce_switch_doubleup: {
    alias: "Guest Bathroom Sconce Switch - Double Up → High",
    description: "Turn on both guest bathroom lights to full on double-tap up (sconce switch)",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_sconce_switch",
      event: "doubleUp"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_high"
    },
    mode: "single"
  },

  guest_bathroom_sconce_switch_singleup: {
    alias: "Guest Bathroom Sconce Switch - Single Up → 50%",
    description: "Set both guest bathroom lights to 50% on single tap up (sconce switch)",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_sconce_switch",
      event: "singleUp"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_medium"
    },
    mode: "single"
  },

  guest_bathroom_sconce_switch_doubledown: {
    alias: "Guest Bathroom Sconce Switch - Double Down → Off",
    description: "Turn off both guest bathroom lights on double-tap down (sconce switch)",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_sconce_switch",
      event: "doubleDown"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_off"
    },
    mode: "single"
  },

  guest_bathroom_sconce_switch_singledown: {
    alias: "Guest Bathroom Sconce Switch - Single Down → Off",
    description: "Turn off both guest bathroom lights on single tap down (sconce switch)",
    trigger: {
      type: "zwave_js_scene",
      device: "guestbathroom_sconce_switch",
      event: "singleDown"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_off"
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
  // Guest Bathroom Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  guest_bathroom_webhook_high: {
    alias: "Guest Bathroom Webhook → High",
    description: "Dashboard button: Guest Bathroom High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_guest_bathroom_high"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_high"
    },
    mode: "single"
  },

  guest_bathroom_webhook_medium: {
    alias: "Guest Bathroom Webhook → Medium",
    description: "Dashboard button: Guest Bathroom Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_guest_bathroom_medium"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_medium"
    },
    mode: "single"
  },

  guest_bathroom_webhook_off: {
    alias: "Guest Bathroom Webhook → Off",
    description: "Dashboard button: Guest Bathroom Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_guest_bathroom_off"
    },
    action: {
      type: "scene",
      scene: "guest_bathroom_off"
    },
    mode: "single"
  },

  // ============================================================================
  // Bedroom Webhook Automations (Dashboard Scene Buttons)
  // ============================================================================

  bedroom_webhook_high: {
    alias: "Bedroom Webhook → High",
    description: "Dashboard button: Bedroom High scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_high"
    },
    action: {
      type: "scene",
      scene: "bedroom_high"
    },
    mode: "single"
  },

  bedroom_webhook_medium: {
    alias: "Bedroom Webhook → Medium",
    description: "Dashboard button: Bedroom Medium scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_medium"
    },
    action: {
      type: "scene",
      scene: "bedroom_medium"
    },
    mode: "single"
  },

  bedroom_webhook_low: {
    alias: "Bedroom Webhook → Low",
    description: "Dashboard button: Bedroom Low scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_low"
    },
    action: {
      type: "scene",
      scene: "bedroom_low"
    },
    mode: "single"
  },

  bedroom_webhook_off: {
    alias: "Bedroom Webhook → Off",
    description: "Dashboard button: Bedroom Off scene",
    trigger: {
      type: "webhook",
      webhook_id: "scene_bedroom_off"
    },
    action: {
      type: "scene",
      scene: "bedroom_off"
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
