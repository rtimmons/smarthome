#!/usr/bin/env node
/**
 * Home Assistant Configuration Generator
 *
 * This script generates Home Assistant YAML configuration files from TypeScript definitions.
 * It converts type-safe TypeScript objects into the YAML format Home Assistant expects.
 */

import * as fs from "fs";
import * as path from "path";
import * as yaml from "yaml";

import { devices, getDevice } from "./devices";
import { scenes } from "./scenes";
import { automations } from "./automations";
import {
  Scene,
  Automation,
  Trigger,
  Action,
  Condition,
  ZWaveJsSceneTrigger,
} from "./types";

// ============================================================================
// Configuration
// ============================================================================

const OUTPUT_DIR = path.join(__dirname, "../../generated");
const SCENES_OUTPUT = path.join(OUTPUT_DIR, "scenes.yaml");
const AUTOMATIONS_OUTPUT = path.join(OUTPUT_DIR, "automations.yaml");

// ============================================================================
// Scene Generation
// ============================================================================

interface HAScene {
  id: string;
  name: string;
  icon?: string;
  entities: Record<string, any>;
}

function generateScenes(): HAScene[] {
  const output: HAScene[] = [];

  for (const [id, scene] of Object.entries(scenes)) {
    const entities: Record<string, any> = {};

    // Process lights
    for (const light of scene.lights) {
      try {
        const device = getDevice("lights", light.device);
        const entityState: any = {
          state: light.state || "on",
        };

        // Add brightness if specified
        if (light.brightness !== undefined) {
          entityState.brightness = light.brightness;
        }

        // Add RGB color if specified
        if (light.rgb_color) {
          entityState.rgb_color = light.rgb_color;
        }

        // Add RGBW color if specified
        if (light.rgbw_color) {
          entityState.rgbw_color = light.rgbw_color;
        }

        // Add color temperature if specified
        if (light.color_temp) {
          entityState.color_temp = light.color_temp;
        }

        // Add white value if specified
        if (light.white_value !== undefined) {
          entityState.white_value = light.white_value;
        }

        // Add transition if specified
        if (light.transition !== undefined) {
          entityState.transition = light.transition;
        }

        entities[device.entity] = entityState;
      } catch (error) {
        console.error(`Error processing light ${light.device} in scene ${id}:`, error);
        throw error;
      }
    }

    // Process switches/outlets if specified
    if (scene.switches) {
      for (const [switchName, state] of Object.entries(scene.switches)) {
        try {
          let device;
          // Try switches first, then outlets
          try {
            device = getDevice("switches", switchName);
          } catch {
            device = getDevice("outlets", switchName);
          }
          entities[device.entity] = { state };
        } catch (error) {
          console.error(`Error processing switch ${switchName} in scene ${id}:`, error);
          throw error;
        }
      }
    }

    output.push({
      id,
      name: scene.name,
      ...(scene.icon && { icon: scene.icon }),
      entities,
    });
  }

  return output;
}

// ============================================================================
// Automation Generation
// ============================================================================

interface HATrigger {
  platform: string;
  [key: string]: any;
}

interface HAAction {
  [key: string]: any;
}

interface HACondition {
  condition: string;
  [key: string]: any;
}

interface HAAutomation {
  alias: string;
  description?: string;
  trigger: HATrigger | HATrigger[];
  condition?: HACondition | HACondition[];
  action: HAAction | HAAction[];
  mode?: string;
  max?: number;
}

function convertTrigger(trigger: Trigger): HATrigger {
  switch (trigger.type) {
    case "zwave_js_scene": {
      const zwaveTrigger = trigger as ZWaveJsSceneTrigger;
      const device = getDevice("switches", zwaveTrigger.device);
      const eventData = device.events?.[zwaveTrigger.event];

      if (!eventData) {
        throw new Error(
          `No event data found for ${zwaveTrigger.device}.${zwaveTrigger.event}`
        );
      }

      if (!device.device_id) {
        throw new Error(
          `Device ID not set for ${zwaveTrigger.device}. Please add device_id to the device definition.`
        );
      }

      return {
        platform: "event",
        event_type: "zwave_js_value_notification",
        event_data: {
          device_id: device.device_id,
          command_class_name: eventData.command_class_name || "Central Scene",
          property_key_name: eventData.property_key_name || "001",
          value: eventData.value || "KeyPressed",
        },
      };
    }

    case "webhook":
      return {
        platform: "webhook",
        webhook_id: trigger.webhook_id,
      };

    case "time":
      return {
        platform: "time",
        at: trigger.at,
      };

    case "state":
      return {
        platform: "state",
        entity_id: trigger.entity_id,
        ...(trigger.to && { to: trigger.to }),
        ...(trigger.from && { from: trigger.from }),
        ...(trigger.for && { for: trigger.for }),
      };

    case "numeric_state":
      return {
        platform: "numeric_state",
        entity_id: trigger.entity_id,
        ...(trigger.above !== undefined && { above: trigger.above }),
        ...(trigger.below !== undefined && { below: trigger.below }),
        ...(trigger.for && { for: trigger.for }),
      };

    case "template":
      return {
        platform: "template",
        value_template: trigger.value_template,
      };

    case "event":
      return {
        platform: "event",
        event_type: trigger.event_type,
        ...(trigger.event_data && { event_data: trigger.event_data }),
      };

    default:
      throw new Error(`Unsupported trigger type: ${(trigger as any).type}`);
  }
}

function convertAction(action: Action): HAAction {
  switch (action.type) {
    case "scene":
      return {
        service: "scene.turn_on",
        target: {
          entity_id: `scene.${action.scene}`,
        },
      };

    case "service":
      return {
        service: action.service,
        ...(action.target && { target: action.target }),
        ...(action.data && { data: action.data }),
      };

    case "delay":
      return {
        delay: action.duration,
      };

    case "wait_template":
      return {
        wait_template: action.template,
        ...(action.timeout && { timeout: action.timeout }),
      };

    case "choose":
      return {
        choose: action.choices.map((choice) => ({
          conditions: choice.conditions.map(convertCondition),
          sequence: choice.sequence.map(convertAction),
        })),
        ...(action.default && { default: action.default.map(convertAction) }),
      };

    case "repeat":
      return {
        repeat: {
          ...(action.count && { count: action.count }),
          ...(action.while && { while: action.while.map(convertCondition) }),
          ...(action.until && { until: action.until.map(convertCondition) }),
          sequence: action.sequence.map(convertAction),
        },
      };

    default:
      throw new Error(`Unsupported action type: ${(action as any).type}`);
  }
}

function convertCondition(condition: Condition): HACondition {
  switch (condition.type) {
    case "state":
      return {
        condition: "state",
        entity_id: condition.entity_id,
        state: condition.state,
      };

    case "numeric_state":
      return {
        condition: "numeric_state",
        entity_id: condition.entity_id,
        ...(condition.above !== undefined && { above: condition.above }),
        ...(condition.below !== undefined && { below: condition.below }),
      };

    case "template":
      return {
        condition: "template",
        value_template: condition.value_template,
      };

    case "time":
      return {
        condition: "time",
        ...(condition.after && { after: condition.after }),
        ...(condition.before && { before: condition.before }),
        ...(condition.weekday && { weekday: condition.weekday }),
      };

    case "zone":
      return {
        condition: "zone",
        entity_id: condition.entity_id,
        zone: condition.zone,
      };

    case "and":
      return {
        condition: "and",
        conditions: condition.conditions.map(convertCondition),
      };

    case "or":
      return {
        condition: "or",
        conditions: condition.conditions.map(convertCondition),
      };

    case "not":
      return {
        condition: "not",
        conditions: condition.conditions.map(convertCondition),
      };

    default:
      throw new Error(`Unsupported condition type: ${(condition as any).type}`);
  }
}

function generateAutomations(): HAAutomation[] {
  const output: HAAutomation[] = [];

  for (const [id, automation] of Object.entries(automations)) {
    try {
      const haAutomation: HAAutomation = {
        alias: automation.alias,
        ...(automation.description && { description: automation.description }),
        trigger: Array.isArray(automation.trigger)
          ? automation.trigger.map(convertTrigger)
          : convertTrigger(automation.trigger),
        ...(automation.condition && {
          condition: Array.isArray(automation.condition)
            ? automation.condition.map(convertCondition)
            : convertCondition(automation.condition),
        }),
        action: Array.isArray(automation.action)
          ? automation.action.map(convertAction)
          : convertAction(automation.action),
        ...(automation.mode && { mode: automation.mode }),
        ...(automation.max && { max: automation.max }),
      };

      output.push(haAutomation);
    } catch (error) {
      console.error(`Error generating automation ${id}:`, error);
      throw error;
    }
  }

  return output;
}

// ============================================================================
// Main Generator
// ============================================================================

function main() {
  console.log("Home Assistant Configuration Generator");
  console.log("======================================\n");

  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  // Generate scenes
  console.log("Generating scenes...");
  const haScenes = generateScenes();
  const scenesYaml = yaml.stringify(haScenes);
  fs.writeFileSync(SCENES_OUTPUT, scenesYaml, "utf8");
  console.log(`  ✓ Generated ${haScenes.length} scenes -> ${SCENES_OUTPUT}`);

  // Generate automations
  console.log("Generating automations...");
  const haAutomations = generateAutomations();
  const automationsYaml = yaml.stringify(haAutomations);
  fs.writeFileSync(AUTOMATIONS_OUTPUT, automationsYaml, "utf8");
  console.log(`  ✓ Generated ${haAutomations.length} automations -> ${AUTOMATIONS_OUTPUT}`);

  console.log("\nGeneration complete!");
  console.log("\nNext steps:");
  console.log("  1. Review generated files in generated/");
  console.log("  2. Run 'just check' to validate configuration");
  console.log("  3. Run 'just push' to deploy to Home Assistant");
}

// Run generator
if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error("\nError during generation:");
    console.error(error);
    process.exit(1);
  }
}
