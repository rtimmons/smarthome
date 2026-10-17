import { describe, expect, it } from "vitest";
import { automations } from "./automations";
import { devices } from "./devices";
import { buildWikiModel } from "./wiki-export";

describe("wiki model", () => {
  it("reports actual all-off membership instead of the default opt-in flag", () => {
    const diagnostic = buildWikiModel().devices.find((device) => device.key === "office_abovecouch_white")!;
    expect(diagnostic.includeInAllOff).toBe(true);
    expect(diagnostic.effectiveAllOff).toBe(false);
  });

  it("omits excluded loads and protects smart-bulb power", () => {
    const model = buildWikiModel();
    const excluded = model.devices.filter((device) => device.sceneStatus === "temporarily_excluded");
    expect(excluded.length).toBeGreaterThan(0);
    for (const scene of model.scenes) {
      expect(new Set(scene.targets.map((target) => target.entity)).size).toBe(scene.targets.length);
      for (const device of excluded) {
        expect(scene.targets.some((target) => target.entity === device.entity)).toBe(false);
      }
      for (const target of scene.targets) {
        const device = model.devices.find((device) => device.key === target.device)!;
        if (!device.allowSceneTurnOff) expect(target.state.state).not.toBe("off");
      }
    }
  });

  it("keeps intentionally absent inventory visible without inventing a static exclusion", () => {
    const model = buildWikiModel();
    const absent = model.devices.find((device) => device.key === "living_palm")!;
    expect(absent.inventoryStatus).toBe("temporarily_removed");
    expect(model.scenes.some((scene) => scene.targets.some((target) => target.entity === absent.entity))).toBe(true);
  });

  it("documents the effective restart mode and omits webhook and device identifiers", () => {
    const model = buildWikiModel();
    expect(model.controls.find((control) => control.id === "office_webhook_high")?.mode).toBe("restart");
    const serialized = JSON.stringify(model);
    for (const automation of Object.values(automations)) {
      const triggers = Array.isArray(automation.trigger) ? automation.trigger : [automation.trigger];
      for (const trigger of triggers) {
        if (trigger.type === "webhook") expect(serialized).not.toContain(JSON.stringify(trigger.webhook_id));
      }
    }
    for (const device of Object.values(devices.switches)) {
      if (device.device_id) expect(serialized).not.toContain(device.device_id);
    }
  });
});
