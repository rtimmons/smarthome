import {
  buildEntityAuditFindings,
  buildSceneParallelismFindings,
  ConfiguredDeviceSummary,
  entityMatchesTarget,
  flattenConfiguredDevices,
} from "./zwave-scenes";

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
