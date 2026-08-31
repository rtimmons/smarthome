import { getDevice, getPairedDeviceName } from "./devices";
import { Device, LightState, Scene } from "./types";

export interface HAScene {
  id: string;
  name: string;
  icon?: string;
  entities: Record<string, any>;
}

export interface HAServiceCall {
  action: string;
  continue_on_error?: boolean;
  target: {
    entity_id: string[];
  };
  data?: Record<string, any>;
}

export interface HAScript {
  alias: string;
  mode: "single" | "restart" | "queued";
  max?: number;
  fields?: Record<string, any>;
  sequence: any[];
}

export interface SceneEntityTarget {
  entityId: string;
  entityState: Record<string, any>;
  sourceDevice: string;
  device: Device;
  domain: string;
  zwaveBacked: boolean;
}

export const FAST_SCENE_SCRIPT_PREFIX = "fast_scene_";
export const FAST_SCENE_DISPATCHER_ID = "fast_scene_dispatch";
export const FAST_SCENE_DISPATCH_WORKER_ID = "fast_scene_dispatch_worker";
export const DEFAULT_MAX_ZWAVE_CALLS_PER_STEP = 1;
export const DEFAULT_ZWAVE_BATCH_DELAY_MS = 250;
export const FAST_SCENE_CONVERGENCE_DELAY_MS = 2000;
export const FAST_SCENE_SKIPPED_EVENT = "fast_scene_targets_skipped";

interface HAConditionalAction {
  if: Array<{
    condition: "template";
    value_template: string;
  }>;
  then: any[];
}

export interface FastSceneGenerationOptions {
  maxZwaveCallsPerStep?: number;
  zwaveBatchDelayMs?: number;
}

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

function isZWaveBackedDevice(device: Device): boolean {
  if (device.protocol) {
    return device.protocol === "zwave";
  }

  return (
    device.type.startsWith("zwave_") ||
    (device.type === "dimmer_light" && device.entity.startsWith("light.light_"))
  );
}

function buildLightEntityState(light: LightState): Record<string, any> {
  const device = getDevice("lights", light.device);
  const desiredState = light.state || "on";
  const transition =
    light.transition ??
    (isZWaveBackedDevice(device) && device.capabilities?.includes("brightness")
      ? 0
      : undefined);
  const entityState: Record<string, any> = {
    state: desiredState,
  };

  if (device.type === "zwave_switch_light") {
    return entityState;
  }

  if (desiredState === "off") {
    if (transition !== undefined) {
      entityState.transition = transition;
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

  if (transition !== undefined) {
    entityState.transition = transition;
  }

  return entityState;
}

export function generateSceneEntities(scene: Scene): Record<string, any> {
  const entities: Record<string, any> = {};

  for (const target of generateSceneTargets(scene)) {
    entities[target.entityId] = target.entityState;
  }

  return entities;
}

export function generateSceneTargets(scene: Scene): SceneEntityTarget[] {
  const targetsByEntityId = new Map<string, SceneEntityTarget>();
  const expandedLights = expandLightsWithPairs(scene.lights);

  for (const light of expandedLights) {
    const device = getDevice("lights", light.device);
    targetsByEntityId.set(device.entity, {
      entityId: device.entity,
      entityState: buildLightEntityState(light),
      sourceDevice: light.device,
      device,
      domain: "light",
      zwaveBacked: isZWaveBackedDevice(device),
    });
  }

  if (scene.switches) {
    for (const [switchName, state] of Object.entries(scene.switches)) {
      let device;
      try {
        device = getDevice("switches", switchName);
      } catch {
        device = getDevice("outlets", switchName);
      }
      if (state === "off" && device.allowSceneTurnOff === false) {
        throw new Error(
          `Scene cannot turn off protected power device ${switchName} (${device.entity})`
        );
      }
      const [domain] = device.entity.split(".");
      targetsByEntityId.set(device.entity, {
        entityId: device.entity,
        entityState: { state },
        sourceDevice: switchName,
        device,
        domain,
        zwaveBacked: isZWaveBackedDevice(device),
      });
    }
  }

  return [...targetsByEntityId.values()];
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

function shouldIsolateTarget(target: SceneEntityTarget): boolean {
  // Keep Z-Wave-backed loads in their own parallel service call so a slow or
  // unreachable node does not serialize other loads that happen to share the
  // same payload.
  return target.zwaveBacked;
}

interface ZWaveValueDescriptor {
  action: "zwave_js.set_value";
  data: Record<string, any>;
}

function brightnessToZWaveLevel(brightness: number): number {
  return Math.round((Math.max(0, Math.min(255, brightness)) * 99) / 255);
}

function buildZWaveValueDescriptor(
  target: SceneEntityTarget
): ZWaveValueDescriptor | undefined {
  if (!target.zwaveBacked) {
    return undefined;
  }

  const desiredState = target.entityState.state;
  const transitionDuration = `${target.entityState.transition ?? 0}s`;
  if (target.device.type === "zwave_dimmer_46203") {
    if (desiredState === "on" && target.entityState.brightness === undefined) {
      // A normal light.turn_on restores the previous level. A raw 99 would not,
      // so retain the entity service for scenes without an explicit brightness.
      return undefined;
    }

    return {
      action: "zwave_js.set_value",
      data: {
        command_class: 38,
        property: "targetValue",
        value:
          desiredState === "off"
            ? 0
            : brightnessToZWaveLevel(target.entityState.brightness),
        options: { transitionDuration },
        wait_for_result: false,
      },
    };
  }

  if (target.device.type === "zwave_switch_light") {
    return {
      action: "zwave_js.set_value",
      data: {
        // These are on/off-only fixtures attached to dimmer hardware (GE 46203
        // and Minoston MP22ZD), not Binary Switch devices. Their live value
        // inventories expose Switch Multilevel CC 38 only.
        command_class: 38,
        property: "targetValue",
        value: desiredState === "on" ? 99 : 0,
        options: { transitionDuration },
        wait_for_result: false,
      },
    };
  }

  return undefined;
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

  for (const target of generateSceneTargets(scene)) {
    const { entityId, entityState, domain } = target;
    const desiredState = entityState.state;

    if (desiredState !== "on" && desiredState !== "off") {
      throw new Error(`Unsupported entity state for ${entityId}: ${desiredState}`);
    }

    const service = `${domain}.turn_${desiredState}`;
    const data = buildServiceData(domain, desiredState, entityState);
    const zwaveValue = buildZWaveValueDescriptor(target);
    const multicastGroup = zwaveValue && target.device.fastSceneMulticastGroup;
    const groupedService = multicastGroup
      ? "zwave_js.multicast_set_value"
      : zwaveValue?.action ?? service;
    const groupedData = zwaveValue?.data ? { ...zwaveValue.data } : data;
    if (multicastGroup && groupedData) {
      // multicast_set_value waits for its one group transmission and does not
      // accept the unicast-only wait_for_result option.
      delete groupedData.wait_for_result;
    }
    const signature = multicastGroup
      ? `${groupedService}|${stableStringify(groupedData ?? {})}|multicast:${multicastGroup}`
      : zwaveValue || shouldIsolateTarget(target)
      ? `${groupedService}|${stableStringify(groupedData ?? {})}|${entityId}`
      : `${service}|${stableStringify(data ?? {})}`;

    if (!groupedCalls.has(signature)) {
      groupedCalls.set(signature, {
        service: groupedService,
        entityIds: [],
        ...(groupedData && { data: groupedData }),
      });
    }

    groupedCalls.get(signature)!.entityIds.push(entityId);
  }

  return Array.from(groupedCalls.values())
    .map((call) => ({
      action: call.service,
      target: {
        entity_id: [...call.entityIds].sort(),
      },
      ...(call.data && { data: call.data }),
    }))
    .sort((left, right) => {
      const leftSignature = `${left.action}|${stableStringify(left.data ?? {})}`;
      const rightSignature = `${right.action}|${stableStringify(right.data ?? {})}`;
      return leftSignature.localeCompare(rightSignature);
    });
}

function entityIdsForCall(call: HAServiceCall): string[] {
  return call.target.entity_id;
}

function buildEligibleEntitiesTemplate(
  call: HAServiceCall,
  minimumCount?: number
): string {
  const entityIds = entityIdsForCall(call);
  const filtered = `fast_scene_eligible_entities | select('in', ${JSON.stringify(
    entityIds
  )}) | list`;
  return minimumCount === undefined
    ? `{{ ${filtered} }}`
    : `{{ ${filtered} | count >= ${minimumCount} }}`;
}

function buildSkippedEntitiesTemplate(targets: SceneEntityTarget[]): string {
  const entityIds = targets.map((target) => target.entityId).sort();
  const zwaveEntityIds = targets
    .filter((target) => target.zwaveBacked)
    .map((target) => target.entityId)
    .sort();

  return [
    "{%- set skipped = namespace(entities=[]) -%}",
    `{%- for entity_id in ${JSON.stringify(entityIds)} -%}`,
    "{%- set entity_state = states(entity_id) -%}",
    "{%- set health = namespace(blocked=false) -%}",
    `{%- if entity_id in ${JSON.stringify(zwaveEntityIds)} -%}`,
    "{%- set target_device = device_id(entity_id) -%}",
    "{%- if target_device -%}",
    "{%- for status_entity in device_entities(target_device) -%}",
    "{%- if status_entity.endswith('_node_status') and states(status_entity) in ['dead', 'unavailable', 'unknown'] -%}",
    "{%- set health.blocked = true -%}",
    "{%- endif -%}",
    "{%- endfor -%}",
    "{%- endif -%}",
    "{%- endif -%}",
    "{%- if entity_state in ['unavailable', 'unknown'] or health.blocked -%}",
    "{%- set skipped.entities = skipped.entities + [entity_id] -%}",
    "{%- endif -%}",
    "{%- endfor -%}",
    "{{ skipped.entities }}",
  ].join("\n");
}

function buildSceneEligibleEntitiesTemplate(targets: SceneEntityTarget[]): string {
  const entityIds = targets.map((target) => target.entityId).sort();
  const offEntityIds = targets
    .filter((target) => target.entityState.state === "off")
    .map((target) => target.entityId)
    .sort();

  return [
    "{%- set eligible = namespace(entities=[]) -%}",
    `{%- for entity_id in ${JSON.stringify(entityIds)} -%}`,
    `{%- if entity_id not in fast_scene_skipped_entities and (entity_id not in ${JSON.stringify(
      offEntityIds
    )} or states(entity_id) != 'off') -%}`,
    "{%- set eligible.entities = eligible.entities + [entity_id] -%}",
    "{%- endif -%}",
    "{%- endfor -%}",
    "{{ eligible.entities }}",
  ].join("\n");
}

function buildSceneMismatchedEntitiesTemplate(
  targets: SceneEntityTarget[]
): string {
  const entityIds = targets.map((target) => target.entityId).sort();
  const expectedStates = Object.fromEntries(
    targets.map((target) => [target.entityId, target.entityState.state])
  );
  const expectedBrightness = Object.fromEntries(
    targets
      .filter(
        (target) =>
          target.entityState.state === "on" &&
          typeof target.entityState.brightness === "number"
      )
      .map((target) => [target.entityId, target.entityState.brightness])
  );

  return [
    "{%- set mismatched = namespace(entities=[]) -%}",
    `{%- set expected_states = ${JSON.stringify(expectedStates)} -%}`,
    `{%- set expected_brightness = ${JSON.stringify(expectedBrightness)} -%}`,
    `{%- for entity_id in ${JSON.stringify(entityIds)} -%}`,
    "{%- if entity_id not in fast_scene_skipped_entities -%}",
    "{%- set brightness = state_attr(entity_id, 'brightness') -%}",
    "{%- if states(entity_id) != expected_states[entity_id] -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- elif entity_id in expected_brightness and (brightness is none or brightness | int < expected_brightness[entity_id] - 1 or brightness | int > expected_brightness[entity_id] + 1) -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- endif -%}",
    "{%- endif -%}",
    "{%- endfor -%}",
    "{{ mismatched.entities }}",
  ].join("\n");
}

function buildRunnableCall(
  call: Pick<HAServiceCall, "action" | "data">,
  eligibleEntities: string
): Record<string, any> {
  return {
    action: call.action,
    continue_on_error: true,
    target: {
      entity_id: eligibleEntities,
    },
    ...(call.data && { data: call.data }),
  };
}

function buildHealthAwareCall(call: HAServiceCall): HAConditionalAction {
  const eligibleEntities = buildEligibleEntitiesTemplate(call);

  if (call.action === "zwave_js.multicast_set_value") {
    return {
      if: [
        {
          condition: "template",
          value_template: buildEligibleEntitiesTemplate(call, 1),
        },
      ],
      then: [
        {
          choose: [
            {
              conditions: buildEligibleEntitiesTemplate(call, 2),
              sequence: [buildRunnableCall(call, eligibleEntities)],
            },
          ],
          default: [
            buildRunnableCall(
              {
                action: "zwave_js.set_value",
                data: { ...call.data, wait_for_result: false },
              },
              eligibleEntities
            ),
          ],
        },
      ],
    };
  }

  return {
    if: [
      {
        condition: "template",
        value_template: buildEligibleEntitiesTemplate(call, 1),
      },
    ],
    then: [
      buildRunnableCall(call, eligibleEntities),
    ],
  };
}

function buildBatchHasWorkTemplate(calls: HAServiceCall[]): string {
  const entityIds = calls.flatMap(entityIdsForCall);
  return `{{ fast_scene_eligible_entities | select('in', ${JSON.stringify(
    entityIds
  )}) | list | count > 0 }}`;
}

function generateFastSceneSequence(
  scene: Scene,
  options: FastSceneGenerationOptions = {}
): any[] {
  const maxZwaveCallsPerStep =
    options.maxZwaveCallsPerStep ?? DEFAULT_MAX_ZWAVE_CALLS_PER_STEP;
  const zwaveBatchDelayMs =
    options.zwaveBatchDelayMs ?? DEFAULT_ZWAVE_BATCH_DELAY_MS;
  if (!Number.isInteger(maxZwaveCallsPerStep) || maxZwaveCallsPerStep < 1) {
    throw new Error("maxZwaveCallsPerStep must be a positive integer");
  }
  if (!Number.isInteger(zwaveBatchDelayMs) || zwaveBatchDelayMs < 0) {
    throw new Error("zwaveBatchDelayMs must be a non-negative integer");
  }
  const targets = generateSceneTargets(scene);
  const calls = generateFastSceneCalls(scene);
  const targetsByEntityId = new Map(
    targets.map((target) => [target.entityId, target])
  );
  const zwaveCalls: HAServiceCall[] = [];
  const nonZwaveCalls: HAServiceCall[] = [];

  for (const call of calls) {
    const hasZwaveTarget = call.target.entity_id.some(
      (entityId) => targetsByEntityId.get(entityId)?.zwaveBacked
    );

    if (hasZwaveTarget) {
      zwaveCalls.push(call);
    } else {
      nonZwaveCalls.push(call);
    }
  }

  zwaveCalls.sort((left, right) => {
    const priority = (call: HAServiceCall) =>
      entityIdsForCall(call).some(
        (entityId) =>
          targetsByEntityId.get(entityId)?.device.fastScenePriority === "last"
      )
        ? 1
        : 0;
    const desiredStateOrder = (call: HAServiceCall) => {
      if (call.action.endsWith("turn_on")) {
        return 0;
      }
      if (call.action === "zwave_js.set_value") {
        return call.data?.value === 0 || call.data?.value === false ? 1 : 0;
      }
      return 1;
    };
    const transmissionOrder = (call: HAServiceCall) =>
      call.action === "zwave_js.multicast_set_value" ? 0 : 1;
    return (
      priority(left) - priority(right) ||
      desiredStateOrder(left) - desiredStateOrder(right) ||
      transmissionOrder(left) - transmissionOrder(right)
    );
  });

  const sequence: any[] = [
    {
      variables: {
        fast_scene_skipped_entities: buildSkippedEntitiesTemplate(targets),
        fast_scene_zwave_batch_sent: false,
      },
    },
    {
      variables: {
        fast_scene_initial_eligible_entities:
          buildSceneEligibleEntitiesTemplate(targets),
        fast_scene_mismatched_entities:
          buildSceneMismatchedEntitiesTemplate(targets),
      },
    },
    {
      variables: {
        fast_scene_eligible_entities:
          "{{ fast_scene_mismatched_entities if retry_mismatches | default(false) else fast_scene_initial_eligible_entities }}",
      },
    },
    {
      if: [
        {
          condition: "template",
          value_template:
            "{{ not (retry_mismatches | default(false)) and fast_scene_skipped_entities | count > 0 }}",
        },
      ],
      then: [
        {
          event: FAST_SCENE_SKIPPED_EVENT,
          event_data: {
            scene_id: "{{ scene_id }}",
            entity_ids: "{{ fast_scene_skipped_entities }}",
          },
        },
      ],
    },
  ];

  const nonZwaveSequence: any[] = [];
  if (nonZwaveCalls.length > 0) {
    nonZwaveSequence.push({
      parallel: nonZwaveCalls.map((call) => buildHealthAwareCall(call)),
    });
  }

  const zwaveSequence: any[] = [];
  for (let index = 0; index < zwaveCalls.length; index += maxZwaveCallsPerStep) {
    const batch = zwaveCalls.slice(index, index + maxZwaveCallsPerStep);
    const then: any[] = [];
    if (zwaveBatchDelayMs > 0) {
      then.push({
        if: [
          {
            condition: "template",
            value_template: "{{ fast_scene_zwave_batch_sent }}",
          },
        ],
        then: [{ delay: { milliseconds: zwaveBatchDelayMs } }],
      });
    }
    then.push(
      {
        parallel: batch.map((call) => buildHealthAwareCall(call)),
      },
      { variables: { fast_scene_zwave_batch_sent: true } }
    );
    zwaveSequence.push({
      if: [
        {
          condition: "template",
          value_template: buildBatchHasWorkTemplate(batch),
        },
      ],
      then,
    });
  }

  let dispatchAction: any;
  if (nonZwaveSequence.length > 0 && zwaveSequence.length > 0) {
    // Independent integrations must begin together. Waiting for a slow Hue,
    // ZHA, or switch service call before the first Z-Wave submission adds a
    // visible startup pause without protecting the Z-Wave controller.
    dispatchAction = {
      parallel: [
        { sequence: nonZwaveSequence },
        { sequence: zwaveSequence },
      ],
    };
  } else {
    dispatchAction = {
      parallel: [
        { sequence: [...nonZwaveSequence, ...zwaveSequence] },
      ],
    };
  }

  sequence.push(dispatchAction);

  return sequence;
}

export function generateFastScriptsFromRegistry(
  sceneRegistry: Record<string, Scene>,
  options: FastSceneGenerationOptions = {}
): Record<string, HAScript> {
  const sceneScripts = Object.fromEntries(
    Object.entries(sceneRegistry).map(([sceneId, scene]) => [
      getFastSceneScriptId(sceneId),
      {
        alias: `Fast Scene - ${scene.name}`,
        mode: "restart",
        sequence: [
          {
            // A blocking call lets a restarted wrapper cancel stale dispatcher
            // work before submitting the newest lighting intent.
            action: `script.${FAST_SCENE_DISPATCHER_ID}`,
            data: { scene_id: sceneId },
          },
        ],
      },
    ])
  );

  const dispatcherFields = {
    scene_id: {
      description: "Generated scene identifier to execute",
      required: true,
    },
  };

  return {
    [FAST_SCENE_DISPATCHER_ID]: {
      alias: "Fast Scene Dispatcher",
      // Lighting is interactive: a newer room/preset request supersedes any
      // unsent batches from an older one instead of waiting behind stale work.
      mode: "restart",
      fields: dispatcherFields,
      sequence: [
        {
          action: `script.${FAST_SCENE_DISPATCH_WORKER_ID}`,
          data: { scene_id: "{{ scene_id }}", retry_mismatches: false },
        },
        { delay: { milliseconds: FAST_SCENE_CONVERGENCE_DELAY_MS } },
        {
          // This direct call and its delay are canceled when newer lighting
          // intent restarts the dispatcher. Only live mismatches are retried.
          action: `script.${FAST_SCENE_DISPATCH_WORKER_ID}`,
          data: { scene_id: "{{ scene_id }}", retry_mismatches: true },
        },
      ],
    },
    [FAST_SCENE_DISPATCH_WORKER_ID]: {
      alias: "Fast Scene Dispatch Worker",
      mode: "restart",
      fields: {
        ...dispatcherFields,
        retry_mismatches: {
          description: "Dispatch only targets that still differ from the scene",
          required: true,
        },
      },
      sequence: [
        {
          choose: Object.entries(sceneRegistry).map(([sceneId, scene]) => ({
            conditions: `{{ scene_id == '${sceneId}' }}`,
            sequence: generateFastSceneSequence(scene, options),
          })),
          default: [
            {
              stop: "Unknown fast scene identifier",
              error: true,
            },
          ],
        },
      ],
    },
    ...sceneScripts,
  };
}
