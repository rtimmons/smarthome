import {
  buildEntityAuditFindings,
  buildSceneParallelismFindings,
  ConfiguredDeviceSummary,
  determineTargetValue,
  entityMatchesTarget,
  flattenConfiguredDevices,
} from "./zwave-scenes";
import { generateSceneTargets } from "../scene-generation";
import { scenes } from "../scenes";

function configuredDevice(
  inventoryStatus: ConfiguredDeviceSummary["inventoryStatus"]
): ConfiguredDeviceSummary {
  return {
    category: "lights",
    name: "test_light",
    entityId: "light.test_light",
    type: "zwave_switch_light",
    includeInAllOff: true,
    inventoryStatus,
    sceneStatus: "active",
  };
}

describe("Z-Wave inventory audit", () => {
  it("uses the supported minimum dimming duration instead of a slower factory default", () => {
    expect(determineTargetValue({ label: "Dimming Rate (Manual Dimming / Z-Wave)", min: 1, default: 4 }, 4))
      .toMatchObject({ targetValue: 1 });
    expect(determineTargetValue({ label: "Ramp Rate (Z-Wave)", min: 0, default: 3 }, 3))
      .toMatchObject({ targetValue: 0 });
    expect(determineTargetValue({ label: "Duration of Alarm Signalization", min: 0, default: 600 }, 600))
      .toBeNull();
  });

  it("verifies wall output zero independently of playback, and checks Medium's animation", () => {
    const wallTarget = (sceneId: string) => generateSceneTargets(scenes[sceneId])
      .find(target => target.entityId === "light.led_grid_wall")!;
    const state = { state: "on", attributes: { brightness: 0 } };
    const observed = new Map<string, any>([
      ["sensor.led_grid_wall_observation", { state: "fresh", attributes: { brightness: 0 } }],
      ["select.led_grid_wall_animation", { state: "Synthetic animation", attributes: { content_id: "animation:python:lava_lamp:v1" } }],
    ]);
    expect(entityMatchesTarget(wallTarget("all_off"), state, observed)).toBe(true);
    expect(entityMatchesTarget(wallTarget("living_room_off"), state, observed)).toBe(true);
    observed.get("sensor.led_grid_wall_observation").attributes.brightness = 1;
    expect(entityMatchesTarget(wallTarget("all_off"), state, observed)).toBe(false);
    observed.get("sensor.led_grid_wall_observation").attributes.brightness = 255;
    expect(entityMatchesTarget(wallTarget("living_room_medium"), state, observed)).toBe(true);
    observed.get("select.led_grid_wall_animation").attributes.content_id = "animation:python:gradient:v1";
    expect(entityMatchesTarget(wallTarget("living_room_medium"), state, observed)).toBe(false);
    expect(entityMatchesTarget(wallTarget("living_room_high"), state, observed)).toBe(true);
  });

  it("does not flag live-verified multicast groups as accidental parallelism", () => {
    expect(buildSceneParallelismFindings([])).toEqual([]);
  });

  it("accepts one-step Z-Wave brightness rounding and ignores transition controls", () => {
    const target = {
      entityState: { state: "on", brightness: 128, transition: 0 },
    } as any;

    expect(
      entityMatchesTarget(target, {
        state: "on",
        attributes: { brightness: 129 },
      })
    ).toBe(true);
    expect(
      entityMatchesTarget(target, {
        state: "on",
        attributes: { brightness: 130 },
      })
    ).toBe(false);
  });

  it("keeps the desired identities for temporarily removed nodes 2 and 16", () => {
    const configured = flattenConfiguredDevices();

    expect(configured).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "living_palm",
          entityId: "light.light_living_palm",
          inventoryStatus: "temporarily_removed",
        }),
        expect.objectContaining({
          name: "outdoor_cafe",
          entityId: "light.light_outdoor_cafe",
          inventoryStatus: "temporarily_removed",
        }),
      ])
    );
  });

  it("does not treat an intentionally absent entity as registry drift", () => {
    expect(
      buildEntityAuditFindings(
        [configuredDevice("temporarily_removed")],
        { data: { entities: [] } }
      )
    ).toEqual([]);
  });

  it("still reports a missing active entity", () => {
    expect(
      buildEntityAuditFindings(
        [configuredDevice("active")],
        { data: { entities: [] } }
      )
    ).toEqual([
      expect.objectContaining({
        entityId: "light.test_light",
        issue: "configured entity missing from live entity registry",
      }),
    ]);
  });
});
