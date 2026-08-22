/**
 * Tests for scene generation with automatic pairing
 */

import * as yaml from "yaml";
import { getEffectiveAutomationMode } from "./automation-generation";
import { automations } from "./automations";
import { generateFastCalls, generateFastScripts, generateScenes } from "./generate-test-helper";
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

describe("Scene Generation with Pairing", () => {
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

  describe("Paired device synchronization", () => {
    it("should automatically add _white pair when RGBW device is specified", () => {
      const testScene: Scene = {
        name: "Test Scene",
        lights: [
          {
            device: "office_abovetv", // RGBW device
            state: "on",
            brightness: 255,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both the RGBW and white entities should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();

      // RGBW entity should have brightness
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);

      // White entity should also have brightness to match
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(255);
      expect(sceneEntities["light.light_office_abovetv_white"].state).toBe("on");
    });

    it("should automatically add RGBW pair when _white device is specified", () => {

      const testScene: Scene = {
        name: "Test Scene",
        lights: [
          {
            device: "office_abovetv_white", // White device
            state: "on",
            brightness: 180,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both entities should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();

      // White entity should have its specified brightness
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(180);

      // RGBW entity should also have brightness
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(180);
      expect(sceneEntities["light.light_office_abovetv"].rgbw_color).toEqual([0, 0, 0, 180]);
    });

    it("should default paired RGBW white channel to full when _white brightness is omitted", () => {

      const testScene: Scene = {
        name: "Test White Default Brightness",
        lights: [
          {
            device: "living_abovetv_white",
            state: "on",
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      expect(sceneEntities["light.light_living_abovetv"].rgbw_color).toEqual([0, 0, 0, 255]);
    });

    it("should turn off both paired devices when one is turned off", () => {

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

      // Both should be off
      expect(sceneEntities["light.light_office_abovetv"].state).toBe("off");
      expect(sceneEntities["light.light_office_abovetv_white"].state).toBe("off");
    });

    it("should respect explicitly defined paired devices", () => {

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
            brightness: 100, // Different brightness explicitly set
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();

      // RGBW should have 255
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);

      // White should have explicitly set 100 (not auto-synced to 255)
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(100);
    });

    it("should handle multiple paired devices in one scene", () => {

      const testScene: Scene = {
        name: "Test Multiple Pairs",
        lights: [
          {
            device: "office_abovetv",
            state: "on",
            brightness: 255,
          },
          {
            device: "living_curtains",
            state: "on",
            brightness: 180,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // All four devices should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();
      expect(sceneEntities["light.light_living_curtains"]).toBeDefined();
      expect(sceneEntities["light.light_living_curtains_white"]).toBeDefined();

      // Each pair should have matching brightness
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(255);
      expect(sceneEntities["light.light_living_curtains"].brightness).toBe(180);
      expect(sceneEntities["light.light_living_curtains_white"].brightness).toBe(180);
    });

    it("should not add pairs for unpaired devices", () => {

      const testScene: Scene = {
        name: "Test Unpaired",
        lights: [
          {
            device: "office_sidetable", // No pair
            state: "on",
            brightness: 255,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Only the specified device should be present
      expect(sceneEntities["light.office_light_sidetable"]).toBeDefined();
      expect(Object.keys(sceneEntities).length).toBe(1);
    });
  });

  describe("Integration test with actual scenes", () => {
    it("should generate valid YAML with paired devices", () => {

      const testScenes: Record<string, Scene> = {
        office_high: {
          name: "Office - High",
          lights: [
            {
              device: "office_abovetv_white",
              state: "on",
              brightness: 255,
            },
          ],
        },
      };

      const result = generateScenes(testScenes);
      const yamlOutput = yaml.stringify(result);

      // YAML should include both entities
      expect(yamlOutput).toContain("light.light_office_abovetv:");
      expect(yamlOutput).toContain("light.light_office_abovetv_white:");
      expect(yamlOutput).toContain("brightness: 255");
    });

    it("should submit on/off-only Z-Wave dimmer loads without waiting and isolate weak outlets", () => {

      const calls = generateFastCalls(scenes.living_room_high);

      expect(calls).toHaveLength(16);
      expect(
        calls.find(
          (call: any) =>
            call.action === "switch.turn_on" &&
            call.target.entity_id.length === 1 &&
            call.target.entity_id[0] === "switch.light_living_sillleftpower"
        )
      ).toBeDefined();
      expect(
        calls.find(
          (call: any) =>
            call.action === "zwave_js.multicast_set_value" &&
            call.data?.command_class === 38 &&
            call.data?.value === 99 &&
            call.data?.options?.transitionDuration === "0s" &&
            call.data?.wait_for_result === undefined &&
            call.target.entity_id.length === 3 &&
            call.target.entity_id.includes("light.light_living_cornerspot") &&
            call.target.entity_id.includes("light.light_living_desklamps") &&
            call.target.entity_id.includes("light.light_living_sliderring")
        )
      ).toBeDefined();
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
            call.target.entity_id.length === 1 &&
            call.target.entity_id[0] === "light.light_living_curtains_white"
        )
      ).toBeDefined();
      expect(
        calls.find(
          (call: any) =>
            call.action === "light.turn_on" &&
            call.data?.brightness === 255 &&
            call.target.entity_id.includes("light.living_light_floor") &&
            call.target.entity_id.includes("light.living_light_nook")
        )
      ).toBeDefined();
    });

    it("should submit both guest bathroom dimmers immediately without waiting", () => {
      const calls = generateFastCalls(scenes.guest_bathroom_medium);

      expect(calls).toHaveLength(2);
      expect(calls.map((call: any) => call.target.entity_id[0]).sort()).toEqual([
        "light.light_guestbathroom_overhead",
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

    it("should not duplicate targets when a paired RGBW entity is already explicit", () => {

      const calls = generateFastCalls(scenes.office_high);
      const allTargets = calls.flatMap((call: any) => call.target.entity_id);

      expect(allTargets.filter((entityId: string) => entityId === "light.light_office_abovetv"))
        .toHaveLength(1);
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

    it("should batch large Z-Wave scenes into multiple parallel steps", () => {

      const scripts = generateFastScripts({ all_off: scenes.all_off });
      const script = scripts.fast_scene_dispatch_worker;
      const sequence = script.sequence[0].choose[0].sequence;
      const parallelSteps = collectObjects(sequence, (step) => Boolean(step.parallel));
      const delaySteps = collectObjects(sequence, (step) => Boolean(step.delay));
      const pacingDelaySteps = delaySteps.filter(
        (step: any) => step.delay.milliseconds !== 2000
      );
      const serviceActions = collectObjects(sequence, (step) => Boolean(step.action));

      expect(sequence.length).toBeGreaterThan(1);
      expect(parallelSteps[0].parallel.length).toBeGreaterThan(0);
      expect(delaySteps.length).toBeGreaterThan(1);
      expect(
        pacingDelaySteps.every((step: any) => step.delay.milliseconds === 250)
      ).toBe(true);
      expect(
        serviceActions.some(
          (call: any) =>
            call.action === "switch.turn_off" &&
            call.target.entity_id.includes("switch.light_office_pianolight") &&
            call.continue_on_error === true
        )
      ).toBe(true);
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
      const worker = scripts.fast_scene_dispatch_worker;
      const sequence = worker.sequence[0].choose[0].sequence;

      expect(script.mode).toBe("restart");
      expect(script.sequence).toEqual([
        {
          action: "script.fast_scene_dispatch",
          data: { scene_id: "living_room_high" },
        },
      ]);
      expect(dispatcher.mode).toBe("restart");
      expect(dispatcher.max).toBeUndefined();
      expect(worker.mode).toBe("restart");
      expect(sequence.length).toBeGreaterThan(1);
      expect(
        collectObjects(sequence, (step) => step.delay?.milliseconds === 250).length
      ).toBeGreaterThan(0);
      expect(
        collectObjects(dispatcher.sequence, (step) => step.delay?.milliseconds === 2000)
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

    it("should skip satisfied off targets and dispatch weak Z-Wave routes last", () => {
      const scripts = generateFastScripts({ all_off: scenes.all_off });
      const sequence = scripts.fast_scene_dispatch_worker.sequence[0].choose[0].sequence;
      const eligibleVariables = sequence.find(
        (step: any) => step.variables?.fast_scene_initial_eligible_entities
      );
      const zwaveBatchSteps = collectObjects(sequence,
        (step: any) => step.if && step.then?.some((action: any) => action.parallel)
      );

      expect(eligibleVariables.variables.fast_scene_initial_eligible_entities).toContain(
        "states(entity_id) != 'off'"
      );
      expect(
        JSON.stringify(zwaveBatchSteps[zwaveBatchSteps.length - 1]).includes(
          "switch.light_living_sillleftpower"
        )
      ).toBe(true);
      expect(JSON.stringify(zwaveBatchSteps[0])).toContain(
        "zwave_js.multicast_set_value"
      );
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
      const dispatcher = scripts.fast_scene_dispatch;
      const sequence = scripts.fast_scene_dispatch_worker.sequence[0].choose[0].sequence;
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

    it("should restore kitchen upper/lower brightness in high scenes", () => {

      const testScenes: Record<string, Scene> = {
        kitchen_high: {
          name: "Kitchen - High",
          lights: [
            {
              device: "kitchen_upper_white",
              state: "on",
              brightness: 255,
            },
            {
              device: "kitchen_lower_white",
              state: "on",
              brightness: 255,
            },
          ],
        },
      };

      const result = generateScenes(testScenes);
      const entities = result[0].entities;

      expect(entities["light.light_kitchen_upper_white"].brightness).toBe(255);
      expect(entities["light.light_kitchen_lower_white"].brightness).toBe(255);
      expect(entities["light.light_kitchen_upper"].brightness).toBe(255);
      expect(entities["light.light_kitchen_lower"].brightness).toBe(255);
    });
  });
});
