import { describe, expect, it } from "vitest";
import { allocatedHomeKitAid, explicitHomeKitFilter, homeKitControls, loadHomeKitCatalog } from "./homekit";
import { loadPlacements } from "./area-placement";

describe("HomeKit exposure contract", () => {
  it("exports reviewed fixtures and only public scene wrappers", () => {
    const controls = homeKitControls();
    expect(controls.fixtures).toHaveLength(38);
    expect(controls.presets).toHaveLength(36);
    expect(controls.presets.every(p => p.entityId.startsWith("script.fast_scene_"))).toBe(true);
    expect(controls.includeEntities).not.toContain("script.fast_scene_dispatch");
    expect(controls.includeEntities).not.toContain("scene.office_high");
    expect(controls.includeEntities).not.toContain("script.fast_scene_closet_medium");
    expect(controls.includeEntities).not.toContain("script.fast_scene_closet_low");
    expect(controls.presets.filter(p => p.areaId === "closet").map(p => p.name)).toEqual(["Closet On", "Closet Off"]);
    expect(controls.presets.find(p => p.entityId === "script.fast_scene_outdoor_high")?.name).toBe("Patio Bright");
    expect(controls.presets.every(p => p.triggerName === `Apply ${p.name}`)).toBe(true);
  });
  it("derives physical and preset rooms from reviewed placements without guessing from scene scope or IDs", () => {
    const controls = homeKitControls();
    expect(controls.fixtures.find(f => f.entityId === "light.light_dining_nook")?.areaId).toBe("dining_room");
    expect(controls.presets.find(p => p.entityId === "script.fast_scene_makerroom_high")).toMatchObject({ areaId: "maker_room", name: "Maker Room Bright" });
    expect(controls.presets.find(p => p.entityId === "script.fast_scene_outdoor_low")).toMatchObject({ areaId: "outdoor", name: "Patio Dim" });
    expect(controls.presets.find(p => p.entityId === "script.fast_scene_guest_bathroom_low")).toMatchObject({ areaId: "guest_bathroom", name: "Guest Bathroom Dim" });
    expect(controls.presets.find(p => p.entityId === "script.fast_scene_all_off")).toMatchObject({ areaId: null, name: "House Lights Out" });

    const placements = loadPlacements();
    placements.entities.find(p => p.entityId === "script.fast_scene_office_high")!.areaId = "dining_room";
    expect(homeKitControls(loadHomeKitCatalog(), placements).presets.find(p => p.entityId === "script.fast_scene_office_high"))
      .toMatchObject({ areaId: "dining_room", name: "Dining Room Bright" });
  });
  it("refuses missing or unconfirmed placements rather than falling back to a name or a default room", () => {
    const placements = loadPlacements();
    placements.entities = placements.entities.filter(p => p.entityId !== "script.fast_scene_outdoor_low");
    expect(() => homeKitControls(loadHomeKitCatalog(), placements)).toThrow(/preset needs a reviewed placement/);

    const fixtures = loadPlacements();
    const fixture = fixtures.devices.find(p => p.entityId === "light.light_dining_nook")!;
    fixture.areaId = null;
    fixture.status = "unconfirmed";
    expect(() => homeKitControls(loadHomeKitCatalog(), fixtures)).toThrow(/fixture needs an assigned placement/);
  });
  it("requires explicit names for special presets and rejects the old duplicated catalog schema", () => {
    const catalog = loadHomeKitCatalog();
    delete catalog.presetNames.all_off;
    expect(() => homeKitControls(catalog)).toThrow(/Missing HomeKit preset name/);
    catalog.schema = 1;
    expect(() => homeKitControls(catalog)).toThrow(/Unsupported HomeKit catalog schema/);
  });
  it("keeps future discoveries private by using no domain includes", () => {
    expect(explicitHomeKitFilter(["light.test"])).toEqual({ include_domains: [], include_entities: ["light.test"], exclude_domains: [], exclude_entities: [] });
  });
  it("verifies retained accessory IDs using platform/domain/unique ID, including migration fallbacks", () => {
    const entity = { entity_id: "light.fixture", platform: "fixture", unique_id: "current", previous_unique_id: "previous" };
    expect(allocatedHomeKitAid(entity, { "fixture.light.current": 42, "light.fixture": 9 })).toBe(42);
    expect(allocatedHomeKitAid(entity, { "fixture.light.previous": 41 })).toBe(41);
    expect(allocatedHomeKitAid(entity, { "light.fixture": 9 })).toBe(9);
    expect(allocatedHomeKitAid(entity, {})).toBeUndefined();
  });
  it.each(["light.light_kitchen_upper_white", "light.hue_room_office", "light.fancontroller_1_neopixel_light", "light.light_guestbathroom_overhead", "switch.light_bedroom_flamingopower"])("rejects diagnostic, overlapping, or protected export %s", entityId => {
    const catalog = loadHomeKitCatalog();
    catalog.fixtures.push({ entityId, name: "Unsafe" });
    expect(() => homeKitControls(catalog)).toThrow(/Excluded/);
  });
  it("rejects duplicate IDs, room-qualified names, and internal scripts", () => {
    const catalog = loadHomeKitCatalog();
    catalog.fixtures.push(catalog.fixtures[0]);
    expect(() => homeKitControls(catalog)).toThrow(/Duplicate/);
    const names = loadHomeKitCatalog();
    names.fixtures[1].name = names.fixtures[0].name;
    expect(() => homeKitControls(names)).toThrow(/Ambiguous/);
    const internal = loadHomeKitCatalog();
    internal.presetSceneIds.push("dispatch");
    expect(() => homeKitControls(internal)).toThrow(/not a scene wrapper/);
    const presets = loadHomeKitCatalog();
    presets.presetSceneIds.push(presets.presetSceneIds[0]);
    expect(() => homeKitControls(presets)).toThrow(/Duplicate/);
  });
});
