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

  it("keeps the Nest automation target lists complete and symmetric", () => {
    const automation = automations.find(
      (candidate: Record<string, unknown>) => candidate.id === AUTOMATION_ID
    );
    expect(automation).toBeDefined();

    const fanGuard = automation.triggers.find(
      (trigger: Record<string, unknown>) => Array.isArray(trigger.entity_id)
    );
    const activeTarget = automation.actions[0].choose[0].sequence[0].target;
    const inactiveTarget = automation.actions[0].default[0].target;

    expect(sorted(fanGuard.entity_id)).toEqual(sorted(FAN_ENTITIES));
    expect(sorted(activeTarget.entity_id)).toEqual(sorted(FAN_ENTITIES));
    expect(sorted(inactiveTarget.entity_id)).toEqual(sorted(FAN_ENTITIES));

    const serializedAutomation = JSON.stringify(automation);
    expect(serializedAutomation).toContain(CLIMATE_ENTITY_ID);
    expect(serializedAutomation).toContain("heating");
    expect(serializedAutomation).toContain("cooling");
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
