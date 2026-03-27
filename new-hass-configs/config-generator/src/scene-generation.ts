import { getDevice, getPairedDeviceName } from "./devices";
import { LightState, Scene } from "./types";

export interface HAScene {
  id: string;
  name: string;
  icon?: string;
  entities: Record<string, any>;
}

export interface HAServiceCall {
  service: string;
  target: {
    entity_id: string[];
  };
  data?: Record<string, any>;
}

export interface HAScript {
  alias: string;
  mode: "restart";
  sequence: Array<{
    parallel: HAServiceCall[];
  }>;
}

export const FAST_SCENE_SCRIPT_PREFIX = "fast_scene_";

function stableStringify(value: any): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }

  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }

  return JSON.stringify(value);
}

export function getFastSceneScriptId(sceneId: string): string {
  return `${FAST_SCENE_SCRIPT_PREFIX}${sceneId}`;
}

export function getFastSceneScriptEntityId(sceneId: string): string {
  return `script.${getFastSceneScriptId(sceneId)}`;
}

export function expandLightsWithPairs(lights: LightState[]): LightState[] {
  const result: LightState[] = [...lights];
  const definedDevices = new Set(lights.map((light) => light.device));

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

      if (light.state === "on" && light.device.endsWith("_white")) {
        const pairedDevice = getDevice("lights", pairedDeviceName);
        if (pairedDevice.type === "zwave_zen31_rgbw") {
          const whiteValue = light.brightness ?? 255;
          pairedLight.rgbw_color = [0, 0, 0, whiteValue];
        }
      }

      result.push(pairedLight);
      definedDevices.add(pairedDeviceName);
    }
  }

  return result;
}

function buildLightEntityState(light: LightState): Record<string, any> {
  const device = getDevice("lights", light.device);
  const desiredState = light.state || "on";
  const entityState: Record<string, any> = {
    state: desiredState,
  };

  if (device.type === "zwave_switch_light") {
    return entityState;
  }

  if (desiredState === "off") {
    if (light.transition !== undefined) {
      entityState.transition = light.transition;
    }
    return entityState;
  }

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

  return entityState;
}

export function generateSceneEntities(scene: Scene): Record<string, any> {
  const entities: Record<string, any> = {};
  const expandedLights = expandLightsWithPairs(scene.lights);

  for (const light of expandedLights) {
    const device = getDevice("lights", light.device);
    entities[device.entity] = buildLightEntityState(light);
  }

  if (scene.switches) {
    for (const [switchName, state] of Object.entries(scene.switches)) {
      let device;
      try {
        device = getDevice("switches", switchName);
      } catch {
        device = getDevice("outlets", switchName);
      }
      entities[device.entity] = { state };
    }
  }

  return entities;
}

export function generateScenesFromRegistry(
  sceneRegistry: Record<string, Scene>
): HAScene[] {
  return Object.entries(sceneRegistry).map(([id, scene]) => ({
    id,
    name: scene.name,
    ...(scene.icon && { icon: scene.icon }),
    entities: generateSceneEntities(scene),
  }));
}

function buildServiceData(
  domain: string,
  desiredState: "on" | "off",
  entityState: Record<string, any>
): Record<string, any> | undefined {
  const data = { ...entityState };
  delete data.state;

  if (desiredState === "off") {
    if (domain === "light" && data.transition !== undefined) {
      return { transition: data.transition };
    }
    return undefined;
  }

  return Object.keys(data).length > 0 ? data : undefined;
}

function shouldIsolateEntity(domain: string, entityId: string): boolean {
  // Z-Wave light entities under this config use the light.light_* naming pattern.
  // Sending them as individual parallel calls avoids a slow or failed node
  // blocking unrelated lights that happen to share the same service payload.
  return domain === "light" && entityId.startsWith("light.light_");
}

export function generateFastSceneCalls(scene: Scene): HAServiceCall[] {
  const groupedCalls = new Map<
    string,
    {
      service: string;
      entityIds: string[];
      data?: Record<string, any>;
    }
  >();

  for (const [entityId, entityState] of Object.entries(generateSceneEntities(scene))) {
    const [domain] = entityId.split(".");
    const desiredState = entityState.state;

    if (desiredState !== "on" && desiredState !== "off") {
      throw new Error(`Unsupported entity state for ${entityId}: ${desiredState}`);
    }

    const service = `${domain}.turn_${desiredState}`;
    const data = buildServiceData(domain, desiredState, entityState);
    const signature = shouldIsolateEntity(domain, entityId)
      ? `${service}|${stableStringify(data ?? {})}|${entityId}`
      : `${service}|${stableStringify(data ?? {})}`;

    if (!groupedCalls.has(signature)) {
      groupedCalls.set(signature, {
        service,
        entityIds: [],
        ...(data && { data }),
      });
    }

    groupedCalls.get(signature)!.entityIds.push(entityId);
  }

  return Array.from(groupedCalls.values())
    .map((call) => ({
      service: call.service,
      target: {
        entity_id: [...call.entityIds].sort(),
      },
      ...(call.data && { data: call.data }),
    }))
    .sort((left, right) => {
      const leftSignature = `${left.service}|${stableStringify(left.data ?? {})}`;
      const rightSignature = `${right.service}|${stableStringify(right.data ?? {})}`;
      return leftSignature.localeCompare(rightSignature);
    });
}

export function generateFastScriptsFromRegistry(
  sceneRegistry: Record<string, Scene>
): Record<string, HAScript> {
  return Object.fromEntries(
    Object.entries(sceneRegistry).map(([sceneId, scene]) => [
      getFastSceneScriptId(sceneId),
      {
        alias: `Fast Scene - ${scene.name}`,
        mode: "restart",
        sequence: [
          {
            parallel: generateFastSceneCalls(scene),
          },
        ],
      },
    ])
  );
}
