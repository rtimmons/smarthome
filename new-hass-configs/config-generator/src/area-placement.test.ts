import { describe, expect, it } from "vitest";
import { loadPlacements, loadRooms, PlacementCatalog, planPlacements, validatePlacements } from "./area-placement";
import { devices } from "./devices";
import { buildWikiModel } from "./wiki-export";

const catalog = (): PlacementCatalog => ({ schema: 1, devices: [
  { entityId: "light.fixture", platform: "fixture", areaId: "office", status: "assigned", note: "Known location", relatedEntityIds: ["light.fixture_white"] },
], entities: [], retired: [] });
const registry = () => ({ devices: [{ id: "fixture-device", area_id: null }], entities: [
  { entity_id: "light.fixture", platform: "fixture", area_id: null, device_id: "fixture-device" },
  { entity_id: "light.fixture_white", platform: "fixture", area_id: null, device_id: "fixture-device", disabled_by: "user" },
] });
const plan = (c = catalog(), r = registry()) => planPlacements(c, ["office"], r.devices, r.entities);

describe("area placement reconciliation", () => {
  it("assigns one physical device, including its disabled endpoints, without entity overrides", () => {
    const result = plan();
    expect(result.updates).toEqual([{ scope: "device", id: "fixture-device", entityId: "light.fixture", from: null, to: "office" }]);
    expect(result.coveredEntities).toBe(2);
    expect(result.uncovered).toEqual([]);
    const r = registry(); (r.devices[0] as any).area_id = "office";
    expect(plan(catalog(), r).updates).toEqual([]);
  });
  it("rejects overrides and changed associations rather than silently clearing or moving them", () => {
    const r = registry(); (r.entities[1] as any).area_id = "office";
    expect(() => plan(catalog(), r)).toThrow("override");
    r.entities[1].area_id = null; r.entities[1].device_id = "different-device";
    expect(() => plan(catalog(), r)).toThrow("Related entity moved");
    r.entities[0].platform = "other";
    expect(() => plan(catalog(), r)).toThrow("Platform changed");
  });
  it("does not assign unidentified loads or confuse temporarily absent hardware with a new device", () => {
    const c = catalog(); c.devices[0].areaId = null; c.devices[0].status = "unconfirmed";
    expect(plan(c).updates).toEqual([]);
    c.devices[0].status = "temporarily_removed"; c.devices[0].areaId = "office";
    expect(plan(c, { devices: [], entities: [] }).absent).toEqual(["light.fixture"]);
    c.devices[0].status = "assigned";
    expect(() => plan(c, { devices: [], entities: [] })).toThrow("Missing catalog entity");
  });
  it("reports newly discovered and retired entities separately without deleting them", () => {
    const c = catalog(); c.retired = [{ entityId: "media_player.retired", platform: "cast", name: "Retired fixture", note: "User retired" }];
    const r = registry(); r.entities.push(...["media_player.retired", "light.new"].map(entity_id => ({ entity_id, device_id: "other", area_id: null, platform: "cast" })));
    expect(plan(c, r).uncovered).toEqual(["light.new"]);
    expect(plan(c, r).retiredPresent).toEqual(["media_player.retired"]);
    expect(plan(c, r).updates).toHaveLength(1);
  });
  it("rejects duplicate anchors, invalid areas, and attaching standalone controls to devices", () => {
    const c = catalog(); c.devices.push({ ...c.devices[0] });
    expect(() => plan(c)).toThrow("duplicate");
    c.devices.pop(); c.devices[0].areaId = "missing";
    expect(() => plan(c)).toThrow("Unknown area");
    c.devices[0].areaId = "office"; c.entities = c.devices; c.devices = [];
    expect(() => plan(c)).toThrow("Unexpected device association");
  });
  it("keeps physical catalog, lighting aliases, fixed speakers and hardware references consistent", () => {
    const c = loadPlacements(), rooms = loadRooms();
    validatePlacements(c, rooms.areas.map(a => a.id));
    const placements = new Map(c.devices.flatMap(d => [d.entityId, ...(d.relatedEntityIds ?? [])].map(id => [id, d])));
    for (const device of Object.values(devices).flatMap(Object.values)) {
      expect(device.areaId, device.entity).toBeTruthy();
      expect(placements.get(device.entity)?.areaId, device.entity).toBe(device.areaId);
    }
    for (const room of rooms.rooms.filter(r => !r.portable)) expect(placements.get(room.sonosEntityId)?.areaId).toBe(room.areaId);
    expect(placements.get("media_player.move")?.status).toBe("assigned");
    expect(placements.get("media_player.move")?.areaId).toBe("outdoor");
    expect(rooms.areas.find(a => a.id === "outdoor")?.name).toBe("Patio");
    for (const product of buildWikiModel().products) for (const ref of product.references) expect(placements.get(ref.entityId)?.areaId).toBe(ref.areaId);
    expect(placements.has("light.light_living_palm")).toBe(false);
  });
});
