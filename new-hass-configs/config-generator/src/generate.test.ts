/**
 * Tests for explicit-endpoint scene generation and fast-scene reliability.
 */

import * as yaml from "yaml";
import { getEffectiveAutomationMode } from "./automation-generation";
import { automations } from "./automations";
import { devices, getPairedDeviceName } from "./devices";
import { generateFastCalls, generateFastScripts, generateScenes } from "./generate-test-helper";
import { generateSceneTargets } from "./scene-generation";
import { scenes } from "./scenes";
import type { Scene } from "./types";

function collectObjects(
  value: unknown,
  predicate: (candidate: Record<string, any>) => boolean
): Record<string, any>[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectObjects(item, predicate));
  }
  if (!value || typeof value !== "object") {
    return [];
  }

  const candidate = value as Record<string, any>;
  return [
    ...(predicate(candidate) ? [candidate] : []),
    ...Object.values(candidate).flatMap((item) =>
      collectObjects(item, predicate)
    ),
  ];
}

function getSceneWorkerSequence(
  scripts: Record<string, any>,
  familyId: string,
  sceneId: string
): any[] {
  const worker = scripts[`fast_scene_dispatch_worker_${familyId}`];
  const choice = worker.sequence[0].choose.find((candidate: any) =>
    String(candidate.conditions).includes(`'${sceneId}'`)
  );
  return choice.sequence;
}

describe("Scene Generation", () => {
  describe("Outdoor dashboard scenes", () => {
    it("should control both outdoor light entities", () => {
      const high = generateScenes({ outdoor_high: scenes.outdoor_high })[0];
      const medium = generateScenes({ outdoor_medium: scenes.outdoor_medium })[0];
      const off = generateScenes({ outdoor_off: scenes.outdoor_off })[0];

      expect(high.entities["light.light_outdoor_cafe"]).toMatchObject({ state: "on" });
      expect(high.entities["light.light_outdoor_sconces"]).toMatchObject({
        state: "on",
        brightness: 255,
      });
      expect(medium.entities["light.light_outdoor_cafe"]).toMatchObject({ state: "on" });
      expect(medium.entities["light.light_outdoor_sconces"]).toMatchObject({
        state: "on",
        brightness: 180,
      });
      expect(off.entities["light.light_outdoor_cafe"]).toMatchObject({ state: "off" });
      expect(off.entities["light.light_outdoor_sconces"]).toMatchObject({ state: "off" });
    });
  });

  describe("Explicit RGBW endpoint selection", () => {
    it("should target only the aggregate endpoint when it is specified", () => {
      const testScene: Scene = {
        name: "Test Scene",
        lights: [
          {
            device: "office_abovetv",
            state: "on",
            brightness: 255,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeUndefined();
    });

    it("should preserve an explicitly requested individual endpoint without auto-expanding", () => {
      const testScene: Scene = {
        name: "Test Scene",
        lights: [
          {
            device: "office_abovetv_white",
            state: "on",
            brightness: 180,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(180);
      expect(sceneEntities["light.light_office_abovetv"]).toBeUndefined();
    });

    it("should use one aggregate command to turn every RGBW channel off", () => {
      const testScene: Scene = {
        name: "Test Off Scene",
        lights: [
          {
            device: "office_abovetv",
            state: "off",
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      expect(sceneEntities["light.light_office_abovetv"].state).toBe("off");
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeUndefined();
    });

    it("should preserve both endpoints only when both are explicitly requested", () => {
      const testScene: Scene = {
        name: "Test Explicit Scene",
        lights: [
          {
            device: "office_abovetv",
            state: "on",
            brightness: 255,
          },
          {
            device: "office_abovetv_white",
            state: "on",
            brightness: 100,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(100);
    });

    it("should leave ordinary lights as one explicit target", () => {
      const testScene: Scene = {
        name: "Test Unpaired",
        lights: [
          {
            device: "office_sidetable",
            state: "on",
            brightness: 255,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      expect(sceneEntities["light.office_light_sidetable"]).toBeDefined();
      expect(Object.keys(sceneEntities).length).toBe(1);
    });
  });

  describe("Integration test with actual scenes", () => {
    it("should use at most one endpoint per RGBW controller in every scene", () => {
      for (const [sceneId, scene] of Object.entries(scenes)) {
        const targetEntities = new Set(
          generateSceneTargets(scene).map((target) => target.entityId)
        );
        for (const [deviceName, device] of Object.entries(devices.lights)) {
          if (deviceName.endsWith("_white")) {
            continue;
          }
          const pairedName = getPairedDeviceName(deviceName);
          if (!pairedName) {
            continue;
          }
          const pairedEntity = devices.lights[pairedName].entity;
          expect(
            targetEntities.has(device.entity) && targetEntities.has(pairedEntity),
            `${sceneId} targets both ${device.entity} and ${pairedEntity}`
          ).toBe(false);
        }
      }
    });

    it("should use aggregate RGBW entities for every operational scene", () => {
      const individualEndpointEntities = new Set(
        Object.entries(devices.lights)
          .filter(([deviceName]) => deviceName.endsWith("_white"))
          .map(([, device]) => device.entity)
      );

      for (const [sceneId, scene] of Object.entries(scenes)) {
        for (const target of generateSceneTargets(scene)) {
          expect(
            individualEndpointEntities.has(target.entityId),
            `${sceneId} targets diagnostic-only endpoint ${target.entityId}`
          ).toBe(false);
        }
      }
    });

    it("should omit every temporarily excluded device from every scene", () => {
      const excludedEntities = new Set(
        [
          ...Object.values(devices.lights),
          ...Object.values(devices.switches),
          ...Object.values(devices.outlets),
        ]
          .filter((device) => device.sceneStatus === "temporarily_excluded")
          .map((device) => device.entity)
      );

      for (const [sceneId, scene] of Object.entries(scenes)) {
        for (const target of generateSceneTargets(scene)) {
          expect(
            excludedEntities.has(target.entityId),
            `${sceneId} still targets excluded ${target.entityId}`
          ).toBe(false);
        }
      }
    });

    it("should generate deterministic white through one aggregate RGBW command", () => {
      const result = generateScenes({ office_high: scenes.office_high });
      const yamlOutput = yaml.stringify(result);

      expect(yamlOutput).toContain("light.light_office_abovetv:");
      expect(yamlOutput).not.toContain("light.light_office_abovetv_white:");
      expect(yamlOutput).toContain("brightness: 255");
      expect(yamlOutput).toContain("rgbw_color:");
    });

    it("should restore the recovered dining nook through its aggregate RGBW entity", () => {
      const highTarget = generateSceneTargets(scenes.kitchen_high).find(
        (target) => target.entityId === "light.light_dining_nook"
      );
      const offTargets = generateSceneTargets(scenes.kitchen_off).map(
        (target) => target.entityId
      );

      expect(highTarget?.entityState).toMatchObject({
        state: "on",
        brightness: 255,
        rgbw_color: [0, 0, 0, 255],
      });
      expect(offTargets).toContain("light.light_dining_nook");
      expect(offTargets).not.toContain("light.light_dining_nook_white");
    });

    it("should submit on/off-only Z-Wave dimmer loads without waiting and isolate every target", () => {

      const calls = generateFastCalls(scenes.living_room_high);

      expect(calls).toHaveLength(12);
      expect(
        calls.flatMap((call: any) => call.target.entity_id)
      ).not.toContain("switch.light_living_sillleftpower");
      expect(
        [
          "light.light_living_cornerspot",
          "light.light_living_desklamps",
          "light.light_living_sliderring",
        ].every((entityId) =>
          calls.some(
            (call: any) =>
              call.action === "zwave_js.set_value" &&
              call.data?.command_class === 38 &&
              call.data?.value === 99 &&
              call.data?.options?.transitionDuration === "0s" &&
              call.data?.wait_for_result === false &&
              call.target.entity_id.length === 1 &&
              call.target.entity_id[0] === entityId
          )
        )
      ).toBe(true);
      expect(
        calls.some((call: any) => call.action === "zwave_js.multicast_set_value")
      ).toBe(false);
      expect(
        calls.find(
          (call: any) =>
            call.action === "switch.turn_on" &&
            call.target.entity_id.includes("switch.light_living_ledwall") &&
            !call.target.entity_id.includes("switch.light_living_sillleftpower")
        )
      ).toBeDefined();
      expect(
        calls.find(
          (call: any) =>
            call.action === "light.turn_on" &&
            call.data?.brightness === 255 &&
            call.data?.rgbw_color?.join(",") === "0,0,0,255" &&
            call.target.entity_id.length === 1 &&
            call.target.entity_id[0] === "light.light_living_curtains"
        )
      ).toBeDefined();
      expect(
        calls.find(
          (call: any) =>
            call.action === "light.turn_on" &&
            call.data?.brightness === 255 &&
            call.target.entity_id.includes("light.living_light_floor") &&
            call.target.entity_id.includes("light.entry_light_nook") &&
            !call.target.entity_id.includes("light.living_light_nook") &&
            !call.target.entity_id.includes("light.living_light_corner")
        )
      ).toBeDefined();
    });

    it("should route guest bathroom scenes around noisy node 23", () => {
      const calls = generateFastCalls(scenes.guest_bathroom_medium);

      expect(calls).toHaveLength(1);
      expect(calls[0].target.entity_id).toEqual([
        "light.light_guestbathroom_sconce",
      ]);
      for (const call of calls) {
        expect(call).toMatchObject({
          action: "zwave_js.set_value",
          data: {
            command_class: 38,
            property: "targetValue",
            value: 50,
            options: { transitionDuration: "0s" },
            wait_for_result: false,
          },
        });
      }
    });

    it("should group all bathroom Zigbee lights into one fast call", () => {

      const calls = generateFastCalls(scenes.bathroom_high);

      expect(calls).toHaveLength(1);
      expect(
        calls.find(
          (call: any) =>
            call.data?.brightness === 254 &&
            call.target.entity_id.length === 5 &&
            call.target.entity_id.includes("light.light_bathroom_edison_bottom") &&
            call.target.entity_id.includes("light.light_bathroom_edison_top") &&
            call.target.entity_id.includes("light.light_bathroom_vanity_left") &&
            call.target.entity_id.includes("light.light_bathroom_vanity_right") &&
            call.target.entity_id.includes("light.light_bathroom_abovesauna")
        )
      ).toBeDefined();
    });

    it("should generate the current bathroom medium, low, and off behavior", () => {
      const mediumCalls = generateFastCalls(scenes.bathroom_medium);
      const lowCalls = generateFastCalls(scenes.bathroom_low);
      const offCalls = generateFastCalls(scenes.bathroom_off);

      expect(mediumCalls).toEqual([
        {
          action: "light.turn_on",
          target: {
            entity_id: [
              "light.light_bathroom_abovesauna",
              "light.light_bathroom_edison_bottom",
              "light.light_bathroom_edison_top",
              "light.light_bathroom_vanity_left",
              "light.light_bathroom_vanity_right",
            ],
          },
          data: { brightness: 155 },
        },
      ]);
      expect(lowCalls).toHaveLength(2);
      expect(lowCalls).toEqual(
        expect.arrayContaining([
          {
            action: "light.turn_off",
            target: { entity_id: ["light.light_bathroom_abovesauna"] },
          },
          {
            action: "light.turn_on",
            target: {
              entity_id: [
                "light.light_bathroom_edison_bottom",
                "light.light_bathroom_edison_top",
                "light.light_bathroom_vanity_left",
                "light.light_bathroom_vanity_right",
              ],
            },
            data: { brightness: 50 },
          },
        ])
      );
      expect(offCalls).toEqual([
        {
          action: "light.turn_off",
          target: {
            entity_id: [
              "light.light_bathroom_abovesauna",
              "light.light_bathroom_edison_bottom",
              "light.light_bathroom_edison_top",
              "light.light_bathroom_vanity_left",
              "light.light_bathroom_vanity_right",
            ],
          },
        },
      ]);
    });

    it("should use aggregate RGBW targets instead of individual channel entities", () => {

      const calls = generateFastCalls(scenes.office_high);
      const allTargets = calls.flatMap((call: any) => call.target.entity_id);

      expect(allTargets).toContain("light.light_office_abovetv");
      expect(allTargets).not.toContain("light.light_office_abovetv_white");
    });

    it("should exclude controller-only switches from all_off fast calls", () => {

      const calls = generateFastCalls(scenes.all_off);
      const allTargets = calls.flatMap((call: any) => call.target.entity_id);

      expect(allTargets).not.toContain("switch.office_wall_switch");
      expect(allTargets).not.toContain("switch.light_bedroom_flamingopower");
      expect(allTargets).toContain("light.light_bathroom_abovesauna");
      expect(allTargets).toContain("light.light_bathroom_edison_bottom");
      expect(allTargets).toContain("light.light_bathroom_edison_top");
      expect(allTargets).toContain("light.light_bathroom_vanity_left");
      expect(allTargets).toContain("light.light_bathroom_vanity_right");
      expect(
        calls.find(
          (call: any) =>
            call.action === "light.turn_off" &&
            call.target.entity_id.length === 1 &&
            call.target.entity_id[0] === "light.light_living_curtains"
        )
      ).toBeDefined();
    });

    it("should keep smart-bulb power energized in bedroom off scenes", () => {
      const calls = generateFastCalls(scenes.bedroom_off);
      const allTargets = calls.flatMap((call: any) => call.target.entity_id);

      expect(allTargets).toContain("light.bedroom_light_flamingo");
      expect(allTargets).not.toContain("switch.light_bedroom_flamingopower");
    });

    it("should batch Z-Wave submissions behind one paced RF gate", () => {

      const scripts = generateFastScripts({ all_off: scenes.all_off });
      const sequence = getSceneWorkerSequence(scripts, "all", "all_off");
      const parallelSteps = collectObjects(sequence, (step) => Boolean(step.parallel));
      const serviceActions = collectObjects(sequence, (step) => Boolean(step.action));
      const gate = scripts.fast_scene_zwave_gate;

      expect(sequence.length).toBeGreaterThan(1);
      expect(parallelSteps[0].parallel.length).toBeGreaterThan(0);
      expect(gate.mode).toBe("queued");
      expect(gate.max).toBe(32);
      expect(collectObjects(gate.sequence, (step) => step.delay?.milliseconds === 250))
        .toHaveLength(1);
      expect(
        serviceActions.some(
          (call: any) =>
            call.action === "switch.turn_off" &&
            call.target.entity_id.includes("switch.light_office_pianolight") &&
            call.continue_on_error === true
        )
      ).toBe(true);
      expect(
        serviceActions.filter(
          (call: any) => call.action === "script.fast_scene_zwave_gate"
        ).length
      ).toBeGreaterThan(0);
      expect(
        sequence.some(
          (step: any) =>
            step.variables?.fast_scene_skipped_entities?.includes("_node_status")
        )
      ).toBe(true);
      expect(
        collectObjects(sequence, (step) => step.event === "fast_scene_targets_skipped")
      ).toHaveLength(1);
    });

    it("should pace residual calls while allowing newer intent to restart scenes", () => {

      const scripts = generateFastScripts({ living_room_high: scenes.living_room_high });
      const script = scripts.fast_scene_living_room_high;
      const dispatcher = scripts.fast_scene_dispatch;
      const familyDispatcher = scripts.fast_scene_dispatch_living_room;
      const worker = scripts.fast_scene_dispatch_worker_living_room;
      const sequence = getSceneWorkerSequence(
        scripts,
        "living_room",
        "living_room_high"
      );

      expect(script.mode).toBe("restart");
      expect(script.sequence).toEqual(expect.arrayContaining([
        expect.objectContaining({ action: "input_text.set_value" }),
        expect.objectContaining({
          action: "script.fast_scene_dispatch",
          data: expect.objectContaining({ scene_id: "living_room_high" }),
        }),
      ]));
      expect(dispatcher.mode).toBe("parallel");
      expect(dispatcher.max).toBe(16);
      expect(familyDispatcher.mode).toBe("restart");
      expect(worker.mode).toBe("restart");
      expect(sequence.length).toBeGreaterThan(1);
      expect(
        collectObjects(familyDispatcher.sequence, (step) => step.delay?.milliseconds === 2000)
      ).toHaveLength(1);
      expect(scripts.fast_scene_zwave_gate.mode).toBe("queued");
      expect(
        collectObjects(scripts.fast_scene_zwave_gate.sequence,
          (step) => step.delay?.milliseconds === 250)
      ).toHaveLength(1);
      expect(JSON.stringify(sequence)).toContain("expected_brightness");
      expect(
        sequence.some(
          (step: any) =>
            step.parallel?.length === 2 &&
            step.parallel.every((branch: any) => Array.isArray(branch.sequence))
        )
      ).toBe(true);
    });

    it("should omit temporarily excluded Z-Wave routes from generated workers", () => {
      const scripts = generateFastScripts({ all_off: scenes.all_off });
      const sequence = getSceneWorkerSequence(scripts, "all", "all_off");
      const eligibleVariables = sequence.find(
        (step: any) => step.variables?.fast_scene_eligible_entities
      );
      const zwaveBatchSteps = collectObjects(sequence,
        (step: any) => step.if && step.then?.some((action: any) => action.parallel)
      );

      expect(eligibleVariables.variables.fast_scene_eligible_entities).toContain(
        "fast_scene_mismatched_entities"
      );
      expect(eligibleVariables.variables.fast_scene_eligible_entities).toContain(
        "origin_entity_id"
      );
      expect(JSON.stringify(zwaveBatchSteps)).not.toContain(
        "switch.light_living_sillleftpower"
      );
      expect(JSON.stringify(sequence)).not.toContain(
        "light.light_guestbathroom_overhead"
      );
      expect(JSON.stringify(zwaveBatchSteps)).not.toContain(
        "zwave_js.multicast_set_value"
      );
      expect(JSON.stringify(zwaveBatchSteps)).toContain("zwave_js.set_value");
    });

    it("should force scene automations to latest-intent restart mode", () => {
      expect(
        getEffectiveAutomationMode({
          alias: "Test Scene Automation",
          trigger: { type: "webhook", webhook_id: "test_scene" },
          action: { type: "scene", scene: "living_room_high" },
          mode: "restart",
        })
      ).toBe("restart");
    });

    it("should keep bathroom webhooks on the current fast-scene paths", () => {
      expect(automations.bathroom_webhook_high).toMatchObject({
        trigger: { type: "webhook", webhook_id: "scene_bathroom_high" },
        action: { type: "scene", scene: "bathroom_high" },
      });
      expect(automations.bathroom_webhook_medium).toMatchObject({
        trigger: { type: "webhook", webhook_id: "scene_bathroom_medium" },
        action: { type: "scene", scene: "bathroom_medium" },
      });
      expect(automations.bathroom_webhook_off).toMatchObject({
        trigger: { type: "webhook", webhook_id: "scene_bathroom_off" },
        action: { type: "scene", scene: "bathroom_off" },
      });
      expect(
        [
          automations.bathroom_webhook_high,
          automations.bathroom_webhook_medium,
          automations.bathroom_webhook_off,
        ].every((automation) => getEffectiveAutomationMode(automation) === "restart")
      ).toBe(true);
    });

    it("should allow callers to lower the batching cap when needed", () => {

      const scripts = generateFastScripts(
        { living_room_high: scenes.living_room_high },
        { maxZwaveCallsPerStep: 1 }
      );
      const sequence = getSceneWorkerSequence(
        scripts,
        "living_room",
        "living_room_high"
      );
      const zwaveBatchSteps = collectObjects(
        sequence,
        (step: any) => step.if && step.then?.some((action: any) => action.parallel)
      );

      expect(zwaveBatchSteps.length).toBeGreaterThan(4);
    });

    it("should reject invalid Z-Wave batching caps", () => {

      expect(() =>
        generateFastScripts(
          { living_room_high: scenes.living_room_high },
          { maxZwaveCallsPerStep: 0 }
        )
      ).toThrow("maxZwaveCallsPerStep must be a positive integer");
    });

    it("should reject invalid Z-Wave batch delays", () => {
      expect(() =>
        generateFastScripts(
          { living_room_high: scenes.living_room_high },
          { zwaveBatchDelayMs: -1 }
        )
      ).toThrow("zwaveBatchDelayMs must be a non-negative integer");
    });

    it("should restore kitchen upper/lower physical white output in high scenes", () => {

      const testScenes: Record<string, Scene> = {
        kitchen_high: {
          name: "Kitchen - High",
          lights: [
            {
              device: "kitchen_upper",
              state: "on",
              brightness: 255,
              rgbw_color: [0, 0, 0, 255],
            },
            {
              device: "kitchen_lower",
              state: "on",
              brightness: 255,
              rgbw_color: [0, 0, 0, 255],
            },
          ],
        },
      };

      const result = generateScenes(testScenes);
      const entities = result[0].entities;

      expect(entities["light.light_kitchen_upper"]).toMatchObject({
        brightness: 255,
        rgbw_color: [0, 0, 0, 255],
      });
      expect(entities["light.light_kitchen_lower"]).toMatchObject({
        brightness: 255,
        rgbw_color: [0, 0, 0, 255],
      });
      expect(entities["light.light_kitchen_upper_white"]).toBeUndefined();
      expect(entities["light.light_kitchen_lower_white"]).toBeUndefined();
    });
  });
});
