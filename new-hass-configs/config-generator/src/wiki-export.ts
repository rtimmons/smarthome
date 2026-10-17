/** Documentation export: desired configuration only, no HA clients or generated secrets. */
import { devices } from "./devices";
import { scenes } from "./scenes";
import { automations } from "./automations";
import { getEffectiveAutomationMode } from "./automation-generation";
import { generateSceneTargets, getFastSceneScriptEntityId } from "./scene-generation";
import { Action, Device, Trigger } from "./types";
import { homeModelRoot, loadPlacements, loadRooms, validatePlacements } from "./area-placement";
import * as fs from "node:fs";
import * as path from "node:path";
import { createHash } from "node:crypto";

export function buildWikiModel() {
  const placements = loadPlacements();
  const rooms = loadRooms();
  validatePlacements(placements, rooms.areas.map(area => area.id));
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
      areaId: device.areaId,
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
  const verificationPath = path.join(homeModelRoot, "area-verification.json");
  const verification = fs.existsSync(verificationPath) ? JSON.parse(fs.readFileSync(verificationPath, "utf8")) : null;
  if (verification) verification.catalogMatches = verification.catalogSha256 === createHash("sha256")
    .update(fs.readFileSync(path.join(homeModelRoot, "device-catalog.json"))).digest("hex");
  const speakerVerificationPath = path.join(homeModelRoot, "speaker-name-verification.json");
  const speakerVerification = fs.existsSync(speakerVerificationPath) ? JSON.parse(fs.readFileSync(speakerVerificationPath, "utf8")) : null;
  if (speakerVerification) speakerVerification.catalogMatches =
    speakerVerification.catalogSha256 === createHash("sha256").update(fs.readFileSync(path.join(homeModelRoot, "device-catalog.json"))).digest("hex") &&
    speakerVerification.roomsSha256 === createHash("sha256").update(fs.readFileSync(path.join(homeModelRoot, "rooms.json"))).digest("hex");
  // Publish only product identity and area references, never host/MAC/config data.
  const products = JSON.parse(fs.readFileSync(path.join(homeModelRoot, "../docs/operations/zwave-product-catalog.json"), "utf8"))
    .products.map((p: any) => ({ id: p.id, label: p.label, manufacturer: p.manufacturer,
      references: p.knownRepoReferences.map((r: any) => ({ entityId: r.entityId, areaId: r.area })) }));
  return { devices: inventory, scenes: definitions, controls, placements, rooms, verification, speakerVerification, products };
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
