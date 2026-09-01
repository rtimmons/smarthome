import { getDevice } from "./devices";
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
  mode: "single" | "restart" | "queued" | "parallel";
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
export const FAST_SCENE_ZWAVE_GATE_ID = "fast_scene_zwave_gate";
export const FAST_SCENE_RF_QUIET_ID = "fast_scene_rf_quiet";
export const FAST_SCENE_INTENT_HELPER_PREFIX = "fast_scene_intent_";
export const DEFAULT_MAX_ZWAVE_CALLS_PER_STEP = 1;
export const DEFAULT_ZWAVE_BATCH_DELAY_MS = 250;
export const FAST_SCENE_CONVERGENCE_DELAY_MS = 2000;
export const FAST_SCENE_RF_QUIET_MS = 900;
export const FAST_SCENE_SKIPPED_EVENT = "fast_scene_targets_skipped";
const FAST_SCENE_MAX_PARALLEL_INTENTS = 16;
const FAST_SCENE_GATE_MAX_QUEUED_CALLS = 32;

export interface HAInputText {
  name: string;
  initial: string;
  max: number;
}

interface FastSceneIntentRegistry {
  scopeByEntityId: Map<string, string>;
  helperIdByScope: Map<string, string>;
  scopesBySceneId: Map<string, string[]>;
}

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

function getSceneFamilyId(sceneId: string): string {
  const match = sceneId.match(/^(.*)_(?:high|medium|low|off)$/);
  return match?.[1] || sceneId;
}

function sanitizeEntityObjectId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function getIntentHelperId(scope: string): string {
  const scopeSlug = scope
    .split("__")
    .map(sanitizeEntityObjectId)
    .join("_and_");
  return `${FAST_SCENE_INTENT_HELPER_PREFIX}${scopeSlug}`;
}

function getFamilyDispatcherId(familyId: string): string {
  return `${FAST_SCENE_DISPATCHER_ID}_${sanitizeEntityObjectId(familyId)}`;
}

function getFamilyWorkerId(familyId: string): string {
  return `${FAST_SCENE_DISPATCH_WORKER_ID}_${sanitizeEntityObjectId(familyId)}`;
}

function buildFastSceneIntentRegistry(
  sceneRegistry: Record<string, Scene>
): FastSceneIntentRegistry {
  const familiesByEntityId = new Map<string, Set<string>>();

  for (const [sceneId, scene] of Object.entries(sceneRegistry)) {
    if (sceneId === "all_off") {
      continue;
    }
    const familyId = getSceneFamilyId(sceneId);
    for (const target of generateSceneTargets(scene)) {
      if (!familiesByEntityId.has(target.entityId)) {
        familiesByEntityId.set(target.entityId, new Set());
      }
      familiesByEntityId.get(target.entityId)!.add(familyId);
    }
  }

  const allEntityIds = new Set(
    Object.values(sceneRegistry).flatMap((scene) =>
      generateSceneTargets(scene).map((target) => target.entityId)
    )
  );
  const scopeByEntityId = new Map<string, string>();
  const helperIdByScope = new Map<string, string>();

  for (const entityId of [...allEntityIds].sort()) {
    const families = [...(familiesByEntityId.get(entityId) ?? [])].sort();
    const scope = families.length > 0 ? families.join("__") : "global";
    scopeByEntityId.set(entityId, scope);
    helperIdByScope.set(scope, getIntentHelperId(scope));
  }

  const scopesBySceneId = new Map<string, string[]>();
  for (const [sceneId, scene] of Object.entries(sceneRegistry)) {
    const scopes = new Set(
      generateSceneTargets(scene).map(
        (target) => scopeByEntityId.get(target.entityId) ?? "global"
      )
    );
    scopesBySceneId.set(sceneId, [...scopes].sort());
  }

  return { scopeByEntityId, helperIdByScope, scopesBySceneId };
}

export function generateFastSceneIntentHelpersFromRegistry(
  sceneRegistry: Record<string, Scene>
): Record<string, HAInputText> {
  const registry = buildFastSceneIntentRegistry(sceneRegistry);
  return Object.fromEntries(
    [...registry.helperIdByScope.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([scope, helperId]) => [
        helperId,
        {
          name: `Fast Scene Intent - ${scope.replace(/__/g, " + ").replace(/_/g, " ")}`,
          initial: "idle",
          max: 64,
        },
      ])
  );
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

  if (light.color_temp_kelvin) {
    entityState.color_temp_kelvin = light.color_temp_kelvin;
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

  for (const light of scene.lights) {
    const device = getDevice("lights", light.device);
    if (device.sceneStatus === "temporarily_excluded") {
      continue;
    }
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
      if (device.sceneStatus === "temporarily_excluded") {
        continue;
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
  const expectedRgb = Object.fromEntries(
    targets
      .filter((target) => Array.isArray(target.entityState.rgb_color))
      .map((target) => [target.entityId, target.entityState.rgb_color])
  );
  const expectedRgbw = Object.fromEntries(
    targets
      .filter((target) => Array.isArray(target.entityState.rgbw_color))
      .map((target) => [target.entityId, target.entityState.rgbw_color])
  );
  const expectedColorTemperature = Object.fromEntries(
    targets
      .filter(
        (target) => typeof target.entityState.color_temp_kelvin === "number"
      )
      .map((target) => [target.entityId, target.entityState.color_temp_kelvin])
  );
  const expectedWhiteValue = Object.fromEntries(
    targets
      .filter((target) => typeof target.entityState.white_value === "number")
      .map((target) => [target.entityId, target.entityState.white_value])
  );

  return [
    "{%- set mismatched = namespace(entities=[]) -%}",
    `{%- set expected_states = ${JSON.stringify(expectedStates)} -%}`,
    `{%- set expected_brightness = ${JSON.stringify(expectedBrightness)} -%}`,
    `{%- set expected_rgb = ${JSON.stringify(expectedRgb)} -%}`,
    `{%- set expected_rgbw = ${JSON.stringify(expectedRgbw)} -%}`,
    `{%- set expected_color_temp_kelvin = ${JSON.stringify(
      expectedColorTemperature
    )} -%}`,
    `{%- set expected_white_value = ${JSON.stringify(expectedWhiteValue)} -%}`,
    `{%- for entity_id in ${JSON.stringify(entityIds)} -%}`,
    "{%- if entity_id not in fast_scene_skipped_entities -%}",
    "{%- set brightness = state_attr(entity_id, 'brightness') -%}",
    "{%- if states(entity_id) != expected_states[entity_id] -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- elif entity_id in expected_brightness and (brightness is none or brightness | int < expected_brightness[entity_id] - 1 or brightness | int > expected_brightness[entity_id] + 1) -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- elif entity_id in expected_rgb and (state_attr(entity_id, 'rgb_color') is none or state_attr(entity_id, 'rgb_color') | list != expected_rgb[entity_id]) -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- elif entity_id in expected_rgbw and (state_attr(entity_id, 'rgbw_color') is none or state_attr(entity_id, 'rgbw_color') | list != expected_rgbw[entity_id]) -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- elif entity_id in expected_color_temp_kelvin and state_attr(entity_id, 'color_temp_kelvin') | int(0) != expected_color_temp_kelvin[entity_id] -%}",
    "{%- set mismatched.entities = mismatched.entities + [entity_id] -%}",
    "{%- elif entity_id in expected_white_value and state_attr(entity_id, 'white_value') | int(-1) != expected_white_value[entity_id] -%}",
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

function buildIntentAwareCall(
  call: HAServiceCall,
  intentHelperEntityId: string
): HAConditionalAction {
  const eligibleEntities = buildEligibleEntitiesTemplate(call);
  const conditions = [
    {
      condition: "template" as const,
      value_template: `{{ states('${intentHelperEntityId}') == intent_token }}`,
    },
    {
      condition: "template" as const,
      value_template: buildEligibleEntitiesTemplate(call, 1),
    },
  ];

  if (call.action === "zwave_js.multicast_set_value") {
    return {
      if: conditions,
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
    if: conditions,
    then: [
      buildRunnableCall(call, eligibleEntities),
    ],
  };
}

function splitCallByIntentScope(
  call: HAServiceCall,
  intentRegistry: FastSceneIntentRegistry
): Array<{ call: HAServiceCall; scope: string; helperEntityId: string }> {
  const entityIdsByScope = new Map<string, string[]>();
  for (const entityId of call.target.entity_id) {
    const scope = intentRegistry.scopeByEntityId.get(entityId) ?? "global";
    if (!entityIdsByScope.has(scope)) {
      entityIdsByScope.set(scope, []);
    }
    entityIdsByScope.get(scope)!.push(entityId);
  }

  return [...entityIdsByScope.entries()].map(([scope, entityIds]) => ({
    scope,
    helperEntityId: `input_text.${
      intentRegistry.helperIdByScope.get(scope) ?? getIntentHelperId(scope)
    }`,
    call: {
      ...call,
      target: { entity_id: [...entityIds].sort() },
    },
  }));
}

function buildZWaveGateCall(
  call: HAServiceCall,
  intentHelperEntityId: string
): Record<string, any> {
  const fallbackData =
    call.action === "zwave_js.multicast_set_value"
      ? { ...call.data, wait_for_result: false }
      : {};

  return {
    action: `script.${FAST_SCENE_ZWAVE_GATE_ID}`,
    continue_on_error: true,
    data: {
      intent_helper_entity_id: intentHelperEntityId,
      intent_token: "{{ intent_token }}",
      service_action: call.action,
      entity_ids: buildEligibleEntitiesTemplate(call),
      service_data: call.data ?? {},
      fallback_service_action:
        call.action === "zwave_js.multicast_set_value"
          ? "zwave_js.set_value"
          : "",
      fallback_service_data: fallbackData,
    },
  };
}

function buildBatchHasWorkTemplate(calls: HAServiceCall[]): string {
  const entityIds = calls.flatMap(entityIdsForCall);
  return `{{ fast_scene_eligible_entities | select('in', ${JSON.stringify(
    entityIds
  )}) | list | count > 0 }}`;
}

function buildOriginFilteredEligibleEntitiesTemplate(): string {
  return [
    "{%- set eligible = namespace(entities=[]) -%}",
    "{%- for entity_id in fast_scene_mismatched_entities -%}",
    "{%- if retry_mismatches | default(false) or entity_id != (origin_entity_id | default('')) -%}",
    "{%- set eligible.entities = eligible.entities + [entity_id] -%}",
    "{%- endif -%}",
    "{%- endfor -%}",
    "{{ eligible.entities }}",
  ].join("\n");
}

function generateFastSceneSequence(
  scene: Scene,
  intentRegistry: FastSceneIntentRegistry,
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
      },
    },
    {
      variables: {
        fast_scene_mismatched_entities:
          buildSceneMismatchedEntitiesTemplate(targets),
      },
    },
    {
      variables: {
        // Initial activation and convergence both send only live mismatches.
        // The physical switch that emitted a Central Scene notification is
        // omitted from the first pass and can be corrected by convergence.
        fast_scene_eligible_entities:
          buildOriginFilteredEligibleEntitiesTemplate(),
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
    const intentAwareCalls = nonZwaveCalls.flatMap((call) =>
      splitCallByIntentScope(call, intentRegistry).map((partition) =>
        buildIntentAwareCall(partition.call, partition.helperEntityId)
      )
    );
    nonZwaveSequence.push({
      parallel: intentAwareCalls,
    });
  }

  const zwaveSequence: any[] = [];
  const scopedZwaveCalls = zwaveCalls.flatMap((call) =>
    splitCallByIntentScope(call, intentRegistry)
  );
  for (
    let index = 0;
    index < scopedZwaveCalls.length;
    index += maxZwaveCallsPerStep
  ) {
    const batch = scopedZwaveCalls.slice(index, index + maxZwaveCallsPerStep);
    zwaveSequence.push({
      if: [
        {
          condition: "template",
          value_template: buildBatchHasWorkTemplate(
            batch.map((partition) => partition.call)
          ),
        },
      ],
      then: [
        {
          parallel: batch.map((partition) =>
            buildZWaveGateCall(partition.call, partition.helperEntityId)
          ),
        },
      ],
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
  const zwaveBatchDelayMs =
    options.zwaveBatchDelayMs ?? DEFAULT_ZWAVE_BATCH_DELAY_MS;
  if (!Number.isInteger(zwaveBatchDelayMs) || zwaveBatchDelayMs < 0) {
    throw new Error("zwaveBatchDelayMs must be a non-negative integer");
  }
  const intentRegistry = buildFastSceneIntentRegistry(sceneRegistry);
  const sceneEntriesByFamily = new Map<string, Array<[string, Scene]>>();
  for (const entry of Object.entries(sceneRegistry)) {
    const familyId = getSceneFamilyId(entry[0]);
    if (!sceneEntriesByFamily.has(familyId)) {
      sceneEntriesByFamily.set(familyId, []);
    }
    sceneEntriesByFamily.get(familyId)!.push(entry);
  }

  const wrapperFields = {
    origin_entity_id: {
      description:
        "Physical entity that emitted the scene event; omitted from the initial RF pass",
      required: false,
    },
  };
  const sceneScripts = Object.fromEntries(
    Object.entries(sceneRegistry).map(([sceneId, scene]) => [
      getFastSceneScriptId(sceneId),
      {
        alias: `Fast Scene - ${scene.name}`,
        mode: "restart",
        fields: wrapperFields,
        sequence: [
          {
            variables: {
              intent_token:
                "scene-{{ now().strftime('%Y%m%d%H%M%S%f') }}",
              origin_entity_id: "{{ origin_entity_id | default('') }}",
            },
          },
          {
            action: "input_text.set_value",
            target: {
              entity_id: (intentRegistry.scopesBySceneId.get(sceneId) ?? []).map(
                (scope) =>
                  `input_text.${
                    intentRegistry.helperIdByScope.get(scope) ??
                    getIntentHelperId(scope)
                  }`
              ),
            },
            data: { value: "{{ intent_token }}" },
          },
          {
            // This restartable, non-blocking quiet timer prevents immediate RF
            // replies from colliding with Central Scene reports. Dashboard and
            // webhook calls omit the physical origin and start immediately.
            if: [
              {
                condition: "template",
                value_template: "{{ origin_entity_id != '' }}",
              },
            ],
            then: [
              {
                action: "script.turn_on",
                target: { entity_id: `script.${FAST_SCENE_RF_QUIET_ID}` },
              },
            ],
          },
          {
            action: `script.${FAST_SCENE_DISPATCHER_ID}`,
            data: {
              scene_id: sceneId,
              intent_token: "{{ intent_token }}",
              origin_entity_id: "{{ origin_entity_id }}",
            },
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
    intent_token: {
      description: "Unique token for the latest affected entity scopes",
      required: true,
    },
    origin_entity_id: wrapperFields.origin_entity_id,
  };

  const workerFields = {
    ...dispatcherFields,
    retry_mismatches: {
      description: "Dispatch only targets that still differ from the scene",
      required: true,
    },
  };

  const familyScripts: Record<string, HAScript> = {};
  for (const [familyId, entries] of sceneEntriesByFamily) {
    const familyDispatcherId = getFamilyDispatcherId(familyId);
    const familyWorkerId = getFamilyWorkerId(familyId);
    familyScripts[familyDispatcherId] = {
      alias: `Fast Scene Dispatcher - ${familyId.replace(/_/g, " ")}`,
      mode: "restart",
      fields: dispatcherFields,
      sequence: [
        {
          action: `script.${familyWorkerId}`,
          data: {
            scene_id: "{{ scene_id }}",
            intent_token: "{{ intent_token }}",
            origin_entity_id: "{{ origin_entity_id | default('') }}",
            retry_mismatches: false,
          },
        },
        { delay: { milliseconds: FAST_SCENE_CONVERGENCE_DELAY_MS } },
        {
          action: `script.${familyWorkerId}`,
          data: {
            scene_id: "{{ scene_id }}",
            intent_token: "{{ intent_token }}",
            origin_entity_id: "{{ origin_entity_id | default('') }}",
            retry_mismatches: true,
          },
        },
      ],
    };
    familyScripts[familyWorkerId] = {
      alias: `Fast Scene Dispatch Worker - ${familyId.replace(/_/g, " ")}`,
      mode: "restart",
      fields: workerFields,
      sequence: [
        {
          choose: entries.map(([sceneId, scene]) => ({
            conditions: `{{ scene_id == '${sceneId}' }}`,
            sequence: generateFastSceneSequence(scene, intentRegistry, options),
          })),
          default: [
            {
              stop: "Unknown fast scene identifier for intent family",
              error: true,
            },
          ],
        },
      ],
    };
  }

  return {
    [FAST_SCENE_RF_QUIET_ID]: {
      alias: "Fast Scene RF Quiet Window",
      mode: "restart",
      sequence: [{ delay: { milliseconds: FAST_SCENE_RF_QUIET_MS } }],
    },
    [FAST_SCENE_ZWAVE_GATE_ID]: {
      alias: "Fast Scene Z-Wave Gate",
      mode: "queued",
      max: FAST_SCENE_GATE_MAX_QUEUED_CALLS,
      fields: {
        intent_helper_entity_id: {
          description: "Input-text helper holding the current target-scope token",
          required: true,
        },
        intent_token: dispatcherFields.intent_token,
        service_action: {
          description: "Z-Wave service action to execute",
          required: true,
        },
        entity_ids: {
          description: "Eligible entity IDs for this isolated call",
          required: true,
        },
        service_data: {
          description: "Service data for the Z-Wave action",
          required: true,
        },
        fallback_service_action: {
          description: "Unicast fallback action for undersized multicast calls",
          required: false,
        },
        fallback_service_data: {
          description: "Service data for the unicast fallback",
          required: false,
        },
      },
      sequence: [
        {
          wait_template: `{{ is_state('script.${FAST_SCENE_RF_QUIET_ID}', 'off') }}`,
          timeout: { seconds: 5 },
          continue_on_timeout: true,
        },
        {
          if: [
            {
              condition: "template",
              value_template:
                "{{ states(intent_helper_entity_id) == intent_token and entity_ids | count > 0 }}",
            },
          ],
          then: [
            {
              choose: [
                {
                  conditions:
                    "{{ fallback_service_action | default('') != '' and entity_ids | count < 2 }}",
                  sequence: [
                    {
                      action: "{{ fallback_service_action }}",
                      continue_on_error: true,
                      target: { entity_id: "{{ entity_ids }}" },
                      data: "{{ fallback_service_data }}",
                    },
                  ],
                },
              ],
              default: [
                {
                  action: "{{ service_action }}",
                  continue_on_error: true,
                  target: { entity_id: "{{ entity_ids }}" },
                  data: "{{ service_data }}",
                },
              ],
            },
            ...(zwaveBatchDelayMs > 0
              ? [{ delay: { milliseconds: zwaveBatchDelayMs } }]
              : []),
          ],
        },
      ],
    },
    [FAST_SCENE_DISPATCHER_ID]: {
      alias: "Fast Scene Dispatcher",
      // Multiple disjoint scene intents may run together. Family dispatchers
      // below retain restart/latest-intent semantics for overlapping targets.
      mode: "parallel",
      max: FAST_SCENE_MAX_PARALLEL_INTENTS,
      fields: dispatcherFields,
      sequence: [
        {
          action: `script.${FAST_SCENE_DISPATCH_WORKER_ID}`,
          data: {
            scene_id: "{{ scene_id }}",
            intent_token: "{{ intent_token }}",
            origin_entity_id: "{{ origin_entity_id | default('') }}",
          },
        },
      ],
    },
    [FAST_SCENE_DISPATCH_WORKER_ID]: {
      alias: "Fast Scene Dispatch Worker",
      mode: "parallel",
      max: FAST_SCENE_MAX_PARALLEL_INTENTS,
      fields: dispatcherFields,
      sequence: [
        {
          choose: [...sceneEntriesByFamily.entries()].map(
            ([familyId, entries]) => ({
              conditions: `{{ scene_id in ${JSON.stringify(
                entries.map(([sceneId]) => sceneId)
              )} }}`,
              sequence: [
                {
                  action: `script.${getFamilyDispatcherId(familyId)}`,
                  data: {
                    scene_id: "{{ scene_id }}",
                    intent_token: "{{ intent_token }}",
                    origin_entity_id:
                      "{{ origin_entity_id | default('') }}",
                  },
                },
              ],
            })
          ),
          default: [
            {
              stop: "Unknown fast scene identifier",
              error: true,
            },
          ],
        },
      ],
    },
    ...familyScripts,
    ...sceneScripts,
  };
}
