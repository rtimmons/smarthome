/** Documentation export: desired configuration only, no HA clients or generated secrets. */
import { devices } from "./devices";
import { scenes } from "./scenes";
import { automations } from "./automations";
import { getEffectiveAutomationMode } from "./automation-generation";
import { generateSceneTargets, getFastSceneScriptEntityId } from "./scene-generation";
import { Action, Device, Trigger } from "./types";

export function buildWikiModel() {
  const definitions = Object.entries(scenes).map(([id, scene]) => {
    const targets = generateSceneTargets(scene);
    const declared = [...scene.lights.map((target) => target.device), ...Object.keys(scene.switches ?? {})];
    return {
      id, name: scene.name, script: getFastSceneScriptEntityId(id),
      targets: targets.map((target) => ({
        device: target.sourceDevice, entity: target.entityId, state: target.entityState,
      })),
      omitted: declared.filter((key) => !targets.some((target) => target.sourceDevice === key)),
    };
  });
  const allOff = new Set(definitions.find((scene) => scene.id === "all_off")?.targets.map((target) => target.entity));
  const inventory = Object.entries(devices).flatMap(([category, entries]) =>
    Object.entries(entries as Record<string, Device>).map(([key, device]) => ({
      category, key, entity: device.entity, type: device.type,
      inventoryStatus: device.inventoryStatus ?? "active",
      sceneStatus: device.sceneStatus ?? "active",
      includeInAllOff: device.includeInAllOff !== false,
      allowSceneTurnOff: device.allowSceneTurnOff !== false,
      effectiveAllOff: allOff.has(device.entity),
    }))
  );
  const controls = Object.entries(automations).map(([id, automation]) => ({
    id, name: automation.alias,
    triggers: (Array.isArray(automation.trigger) ? automation.trigger : [automation.trigger]).map(describeTrigger),
    actions: (Array.isArray(automation.action) ? automation.action : [automation.action]).map(describeAction),
    conditional: Boolean(automation.condition),
    mode: getEffectiveAutomationMode(automation) ?? "single",
  }));
  return { devices: inventory, scenes: definitions, controls };
}

// Summarize only reviewed fields. Never export webhook IDs, service payloads,
// template bodies, device IDs or arbitrary automation data into the static site.
function describeTrigger(trigger: Trigger): string {
  switch (trigger.type) {
    case "zwave_js_scene": return `${trigger.device}: ${trigger.event}`;
    case "webhook": return "Dashboard / webhook";
    case "time": return `Time: ${trigger.at}`;
    case "state": case "numeric_state": return `${trigger.type}: ${trigger.entity_id}`;
    default: return `${trigger.type} (see source)`;
  }
}

function describeAction(action: Action): string {
  switch (action.type) {
    case "scene": return getFastSceneScriptEntityId(action.scene);
    case "service": return action.service;
    default: return `${action.type} (see source)`;
  }
}

if (require.main === module) {
  process.stdout.write(JSON.stringify(buildWikiModel(), null, 2) + "\n");
}
