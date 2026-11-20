import * as fs from "node:fs";
import * as path from "node:path";
import { devices } from "./devices";
import { scenes } from "./scenes";
import { homeModelRoot, loadPlacements, loadRooms, validatePlacements } from "./area-placement";
import { getFastSceneScriptEntityId } from "./scene-generation";
import { getScenePresetLevel, SCENE_PRESET_LABELS } from "./scene-presets";

export interface HomeKitFixture {
  entityId: string;
  name: string;
  displayAs?: "light";
}
export interface HomeKitControl extends HomeKitFixture {
  areaId: string | null;
}
export interface HomeKitCatalog {
  schema: number;
  bridge: { name: string; port: number };
  fixtures: HomeKitFixture[];
  presetSceneIds: string[];
  presetNames: Record<string, string>;
  excludedEntities: { entityId: string; reason: string }[];
  excludedPatterns: { pattern: string; reason: string }[];
}
export const loadHomeKitCatalog = (): HomeKitCatalog => JSON.parse(
  fs.readFileSync(path.join(homeModelRoot, "homekit-catalog.json"), "utf8")
);
export function homeKitControls(catalog = loadHomeKitCatalog(), placements = loadPlacements()) {
  if (catalog.schema !== 2) throw new Error("Unsupported HomeKit catalog schema");
  const areas = new Map(loadRooms().areas.map(a => [a.id, a.name]));
  validatePlacements(placements, [...areas.keys()]);
  const physical = new Map([...placements.devices, ...placements.entities]
    .flatMap(p => [p.entityId, ...(p.relatedEntityIds ?? [])].map(id => [id, p] as const)));
  const seenIds = new Set<string>();
  for (const entityId of [...catalog.fixtures.map(f => f.entityId), ...catalog.presetSceneIds.map(getFastSceneScriptEntityId)]) {
    if (seenIds.has(entityId)) throw new Error(`Duplicate HomeKit entity: ${entityId}`);
    seenIds.add(entityId);
    const excluded = catalog.excludedEntities.some(e => e.entityId === entityId)
      || catalog.excludedPatterns.some(e => new RegExp(e.pattern).test(entityId));
    if (excluded) throw new Error(`Excluded HomeKit entity: ${entityId}`);
  }
  for (const sceneId of Object.keys(catalog.presetNames)) {
    if (!catalog.presetSceneIds.includes(sceneId)) throw new Error(`Unused HomeKit preset name: ${sceneId}`);
  }
  const logical = [...Object.values(devices.lights), ...Object.values(devices.outlets)];
  const fixtures: HomeKitControl[] = catalog.fixtures.map(fixture => {
    const placement = physical.get(fixture.entityId);
    if (!placement || placement.status !== "assigned" || placement.areaId === null) {
      throw new Error(`HomeKit fixture needs an assigned placement: ${fixture.entityId}`);
    }
    const device = logical.find(d => d.entity === fixture.entityId);
    if (device?.sceneStatus === "temporarily_excluded" || device?.inventoryStatus === "temporarily_removed"
      || device?.allowSceneTurnOff === false) throw new Error(`Protected HomeKit fixture: ${fixture.entityId}`);
    if (!/^(light|switch)\./.test(fixture.entityId)) throw new Error(`Unsupported fixture: ${fixture.entityId}`);
    return { ...fixture, areaId: placement.areaId };
  });
  const presets: HomeKitControl[] = catalog.presetSceneIds.map(sceneId => {
    const entityId = getFastSceneScriptEntityId(sceneId);
    if (!Object.prototype.hasOwnProperty.call(scenes, sceneId)) throw new Error(`Preset is not a scene wrapper: ${entityId}`);
    const placement = physical.get(entityId);
    if (!placement || placement.platform !== "script" || !["assigned", "whole_home"].includes(placement.status)) {
      throw new Error(`HomeKit preset needs a reviewed placement: ${entityId}`);
    }
    const level = getScenePresetLevel(sceneId);
    const name = catalog.presetNames[sceneId]
      ?? (level && placement.areaId !== null ? `${areas.get(placement.areaId)} ${SCENE_PRESET_LABELS[level]}` : undefined);
    if (name === undefined) throw new Error(`Missing HomeKit preset name: ${sceneId}`);
    return { entityId, areaId: placement.areaId, name };
  });
  const spokenNames = new Set<string>();
  for (const control of [...fixtures, ...presets]) {
    if (!control.name.trim()) throw new Error(`Missing HomeKit name: ${control.entityId}`);
    const spoken = (control.entityId.startsWith("script.") ? control.name : `${areas.get(control.areaId!)} ${control.name}`).toLowerCase();
    if (spokenNames.has(spoken)) throw new Error(`Ambiguous HomeKit name: ${spoken}`);
    spokenNames.add(spoken);
  }
  const includeEntities = [...seenIds].sort();
  if (includeEntities.length > 149) throw new Error("HomeKit catalog exceeds one bridge's accessory capacity");
  return { fixtures,
    presets: presets.map(preset => ({ ...preset, triggerName: `Apply ${preset.name}` })),
    includeEntities };
}

export function explicitHomeKitFilter(includeEntities: string[]) {
  return { include_domains: [], include_entities: [...includeEntities].sort(), exclude_domains: [], exclude_entities: [] };
}

/** Match HA's stable AID keys; raw entity IDs are only the fallback. */
export function allocatedHomeKitAid(entity: { entity_id: string; platform: string; unique_id: string; previous_unique_id?: string | null }, allocations: Record<string, number>) {
  const prefix = `${entity.platform}.${entity.entity_id.split(".")[0]}.`;
  const keys = [`${prefix}${entity.unique_id}`,
    ...(entity.previous_unique_id ? [`${prefix}${entity.previous_unique_id}`] : []), entity.entity_id];
  return keys.map(key => allocations[key]).find(aid => aid !== undefined);
}
