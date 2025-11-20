/**
 * Test helper to expose scene generation function for testing
 */

import { getDevice, getPairedDeviceName } from "./devices";
import { Scene, LightState } from "./types";

interface HAScene {
  id: string;
  name: string;
  icon?: string;
  entities: Record<string, any>;
}

/**
 * Expand scene lights to include paired devices
 * (Duplicate of the function in generate.ts for testing)
 */
function expandLightsWithPairs(lights: LightState[]): LightState[] {
  const result: LightState[] = [...lights];
  const definedDevices = new Set(lights.map((l) => l.device));

  for (const light of lights) {
    const pairedDeviceName = getPairedDeviceName(light.device);

    if (pairedDeviceName && !definedDevices.has(pairedDeviceName)) {
      const pairedLight: LightState = {
        device: pairedDeviceName,
        state: light.state || "on",
      };

      if (light.state === "on" && light.brightness !== undefined) {
        pairedLight.brightness = light.brightness;
      }

      result.push(pairedLight);
      definedDevices.add(pairedDeviceName);
    }
  }

  return result;
}

/**
 * Exposed version of generateScenes for testing
 */
export function generateScenes(scenes: Record<string, Scene>): HAScene[] {
  const output: HAScene[] = [];

  for (const [id, scene] of Object.entries(scenes)) {
    const entities: Record<string, any> = {};

    const expandedLights = expandLightsWithPairs(scene.lights);

    for (const light of expandedLights) {
      try {
        const device = getDevice("lights", light.device);
        const entityState: any = {
          state: light.state || "on",
        };

        if (device.type !== "zwave_switch_light") {
          if (light.brightness !== undefined) {
            entityState.brightness = light.brightness;
          }
          if (light.rgb_color) {
            entityState.rgb_color = light.rgb_color;
          }
          if (light.rgbw_color) {
            entityState.rgbw_color = light.rgbw_color;
          }
          if (light.color_temp) {
            entityState.color_temp = light.color_temp;
          }
          if (light.white_value !== undefined) {
            entityState.white_value = light.white_value;
          }
          if (light.transition !== undefined) {
            entityState.transition = light.transition;
          }
        }

        entities[device.entity] = entityState;
      } catch (error) {
        console.error(`Error processing light ${light.device} in scene ${id}:`, error);
        throw error;
      }
    }

    if (scene.switches) {
      for (const [switchName, state] of Object.entries(scene.switches)) {
        try {
          let device;
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
