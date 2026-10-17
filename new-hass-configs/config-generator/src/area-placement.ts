import * as fs from "node:fs";
import * as path from "node:path";

export interface Placement {
  entityId: string;
  name?: string;
  platform: string;
  model?: string;
  areaId: string | null;
  status: "assigned" | "portable" | "whole_home" | "unconfirmed" | "temporarily_removed";
  note: string;
  relatedEntityIds?: string[];
}
export interface PlacementCatalog {
  schema: number;
  devices: Placement[];
  entities: Placement[];
  retired: { entityId: string; platform: string; name: string; note: string }[];
}
export interface RegistryEntity {
  entity_id: string;
  device_id: string | null;
  area_id: string | null;
  platform: string;
  disabled_by?: string | null;
}
export interface RegistryDevice { id: string; area_id: string | null }
export interface AreaUpdate {
  scope: "device" | "entity";
  id: string;
  entityId: string;
  from: string | null;
  to: string | null;
}
export const homeModelRoot = path.resolve(__dirname, "../../../home-model");
export function loadPlacements(): PlacementCatalog {
  return JSON.parse(fs.readFileSync(path.join(homeModelRoot, "device-catalog.json"), "utf8"));
}
export function loadRooms(): { areas: { id: string; name: string }[]; rooms: any[] } {
  return JSON.parse(fs.readFileSync(path.join(homeModelRoot, "rooms.json"), "utf8"));
}

export function validatePlacements(catalog: PlacementCatalog, areas: string[]) {
  if (catalog.schema !== 1) throw new Error("Unsupported placement catalog schema");
  const seen = new Set<string>();
  for (const record of [...catalog.devices, ...catalog.entities]) {
    if (!["assigned", "portable", "whole_home", "unconfirmed", "temporarily_removed"].includes(record.status)) throw new Error(`Unknown placement status: ${record.entityId}`);
    if (!record.note || !record.platform) throw new Error(`Missing rationale/platform: ${record.entityId}`);
    if (record.areaId !== null && !areas.includes(record.areaId)) throw new Error(`Unknown area: ${record.areaId}`);
    if (["assigned", "temporarily_removed"].includes(record.status) !== (record.areaId !== null)) {
      throw new Error(`Invalid placement status/area: ${record.entityId}`);
    }
    for (const id of [record.entityId, ...(record.relatedEntityIds ?? [])]) {
      if (!/^[a-z_]+\.[a-z0-9_]+$/.test(id) || seen.has(id)) throw new Error(`Invalid or duplicate entity: ${id}`);
      seen.add(id);
    }
  }
  for (const record of catalog.retired) {
    if (seen.has(record.entityId)) throw new Error(`Retired entity is still placed: ${record.entityId}`);
    seen.add(record.entityId);
  }
}

/** Plan explicit placements only. Names, scene targets and prefixes never infer location. */
export function planPlacements(catalog: PlacementCatalog, areas: string[], devices: RegistryDevice[], entities: RegistryEntity[]) {
  validatePlacements(catalog, areas);
  const byEntity = new Map(entities.map(e => [e.entity_id, e]));
  const byDevice = new Map(devices.map(d => [d.id, d]));
  const covered = new Set<string>();
  const assignedDevices = new Set<string>();
  const updates: AreaUpdate[] = [];
  const absent: string[] = [];
  for (const [scope, records] of [["device", catalog.devices], ["entity", catalog.entities]] as const) {
    for (const record of records) {
      const entity = byEntity.get(record.entityId);
      if (!entity) {
        if (record.status === "temporarily_removed") { absent.push(record.entityId); continue; }
        throw new Error(`Missing catalog entity: ${record.entityId}`);
      }
      if (entity.platform !== record.platform) throw new Error(`Platform changed: ${record.entityId}`);
      const target = scope === "device" ? byDevice.get(entity.device_id ?? "") : entity;
      if (!target || (scope === "entity" && entity.device_id)) throw new Error(`Unexpected device association: ${record.entityId}`);
      if (scope === "device") {
        if (assignedDevices.has(entity.device_id!)) throw new Error(`Two anchors address the same device: ${record.entityId}`);
        assignedDevices.add(entity.device_id!);
        for (const related of record.relatedEntityIds ?? []) {
          if (byEntity.get(related)?.device_id !== entity.device_id) throw new Error(`Related entity moved: ${related}`);
        }
      }
      const members = scope === "device" ? entities.filter(e => e.device_id === entity.device_id) : [entity];
      for (const member of members) {
        covered.add(member.entity_id);
        // Explicit overrides need their own reviewed policy; never silently clear one.
        if (scope === "device" && member.area_id != null) throw new Error(`Review entity area override: ${member.entity_id}`);
      }
      if (record.status === "unconfirmed") continue;
      if ((target.area_id ?? null) !== record.areaId) {
        updates.push({ scope, id: scope === "device" ? entity.device_id! : entity.entity_id,
          entityId: record.entityId, from: target.area_id ?? null, to: record.areaId });
      }
    }
  }
  return {
    updates, absent,
    retiredPresent: catalog.retired.filter(r => byEntity.has(r.entityId)).map(r => r.entityId),
    uncovered: entities.filter(e => !covered.has(e.entity_id) && !catalog.retired.some(r => r.entityId === e.entity_id)).map(e => e.entity_id),
    coveredEntities: covered.size,
    coveredDevices: assignedDevices.size,
    devicesWithoutEntities: devices.filter(d => !entities.some(e => e.device_id === d.id)).length,
  };
}
