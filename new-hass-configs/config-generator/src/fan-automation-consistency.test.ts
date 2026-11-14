import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as yaml from "yaml";

const AUTOMATION_ID = "living_room_heat_pump_fans_follow_nest";
const CLIMATE_ENTITY_ID = "climate.living_room";
const FAN_ENTITIES = [
  "fan.fancontroller_1_fan_1",
  "fan.fancontroller_1_fan_2",
  "fan.fancontroller_1_fan_3",
  "fan.fancontroller_1_fan_4",
  "fan.fancontroller_2_fan_1",
  "fan.fancontroller_2_fan_2",
  "fan.fancontroller_2_fan_3",
  "fan.fancontroller_2_fan_4",
];

function sorted(values: string[]): string[] {
  return [...values].sort();
}

describe("living-room heat-pump fan inventory", () => {
  const configGeneratorDir = process.cwd();
  const automations = yaml.parse(
    readFileSync(
      resolve(configGeneratorDir, "../manual/automations.yaml"),
      "utf8"
    )
  );
  const catalog = JSON.parse(
    readFileSync(
      resolve(configGeneratorDir, "../../docs/operations/zwave-product-catalog.json"),
      "utf8"
    )
  );
  const documentation = readFileSync(
    resolve(configGeneratorDir, "../../docs/operations/esphome-fancontrollers.md"),
    "utf8"
  );
  const fanPackage = yaml.parse(
    readFileSync(resolve(configGeneratorDir, "../packages/living_room_heat_pump_fans.yaml"), "utf8")
  );

  it("keeps the Nest automation target list complete across both cabinets", () => {
    const automation = automations.find(
      (candidate: Record<string, unknown>) => candidate.id === AUTOMATION_ID
    );
    expect(automation).toBeDefined();

    const fanGuard = automation.triggers.find(
      (trigger: Record<string, unknown>) => trigger.to === "on"
    );
    expect(sorted(fanGuard.entity_id)).toEqual(sorted(FAN_ENTITIES));
    expect(sorted(automation.variables.fan_entities)).toEqual(sorted(FAN_ENTITIES));
    expect(automation.actions[0].repeat.for_each).toEqual([1, 2]);

    const serializedAutomation = JSON.stringify(automation);
    expect(serializedAutomation).toContain(CLIMATE_ENTITY_ID);
    expect(serializedAutomation).toContain("heating");
    expect(serializedAutomation).toContain("cooling");
  });

  it("reconciles fan outputs when either cabinet's residual heat changes", () => {
    const automation = automations.find(
      (candidate: Record<string, unknown>) => candidate.id === AUTOMATION_ID
    );
    const sensors = fanPackage.template[0].binary_sensor.map(
      (sensor: { default_entity_id: string }) => sensor.default_entity_id
    );
    expect(sensors).toEqual([
      "binary_sensor.living_room_fancontroller_1_heat",
      "binary_sensor.living_room_fancontroller_2_heat",
    ]);
    expect(automation.triggers).toContainEqual({
      trigger: "state",
      entity_id: sensors,
      to: null,
    });
  });

  it("checks the Nest when any fan output returns online, including when it restores to off", () => {
    const automation = automations.find(
      (candidate: Record<string, unknown>) => candidate.id === AUTOMATION_ID
    );
    const reconnect = automation.triggers.find(
      (trigger: Record<string, unknown>) => trigger.id === "fan_reconnected_off"
    );

    expect(reconnect).toMatchObject({ trigger: "state", to: "off" });
    expect(sorted(reconnect.from)).toEqual(["unavailable", "unknown"]);
    expect(sorted(reconnect.entity_id)).toEqual(sorted(FAN_ENTITIES));
  });

  it("keeps the stable hardware catalog and operations guide in sync", () => {
    const product = catalog.products.find(
      (candidate: Record<string, unknown>) =>
        candidate.id === "espressif-esp32-s2-saola-1-fancontroller-r3-1"
    );
    const livingRoomReferences = product.knownRepoReferences.filter(
      (reference: Record<string, unknown>) => reference.area === "living_room"
    );
    const catalogFanEntities = livingRoomReferences.flatMap(
      (reference: Record<string, unknown>) => reference.fanEntityIds
    );

    expect(sorted(catalogFanEntities)).toEqual(sorted(FAN_ENTITIES));
    for (const reference of livingRoomReferences) {
      expect(reference.controlledByAutomation).toBe(AUTOMATION_ID);
    }
    expect(documentation).toContain(AUTOMATION_ID);
    expect(documentation).toContain(CLIMATE_ENTITY_ID);
    for (const entityId of FAN_ENTITIES) {
      expect(documentation).toContain(entityId);
    }
  });
});
