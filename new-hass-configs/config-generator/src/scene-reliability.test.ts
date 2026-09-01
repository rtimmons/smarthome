import * as fs from "fs";
import * as path from "path";
import * as yaml from "yaml";

import { automations } from "./automations";
import { getEffectiveAutomationMode } from "./automation-generation";
import {
  convertAction,
  generateAutomationsFromRegistry,
} from "./generate";
import {
  DEFAULT_MAX_ZWAVE_CALLS_PER_STEP,
  FAST_SCENE_DISPATCH_WORKER_ID,
  FAST_SCENE_DISPATCHER_ID,
  FAST_SCENE_RF_QUIET_ID,
  FAST_SCENE_SKIPPED_EVENT,
  FAST_SCENE_ZWAVE_GATE_ID,
  generateFastSceneCalls,
  generateFastSceneIntentHelpersFromRegistry,
  generateFastScriptsFromRegistry,
  generateSceneTargets,
  getFastSceneScriptEntityId,
} from "./scene-generation";
import { scenes } from "./scenes";
import type { Action } from "./types";

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

function sceneActions(action: Action | Action[]): Array<Extract<Action, { type: "scene" }>> {
  return collectObjects(action, (candidate) => candidate.type === "scene") as Array<
    Extract<Action, { type: "scene" }>
  >;
}

function sceneFamilyId(sceneId: string): string {
  return sceneId.replace(/_(?:high|medium|low|off)$/, "");
}

function getSceneWorkerSequence(
  scripts: Record<string, any>,
  sceneId: string
): any[] {
  const worker = scripts[
    `${FAST_SCENE_DISPATCH_WORKER_ID}_${sceneFamilyId(sceneId)}`
  ];
  const choice = worker.sequence[0].choose.find((candidate: any) =>
    String(candidate.conditions).includes(`'${sceneId}'`)
  );
  return choice.sequence;
}

function intentHelpersForWrapper(script: Record<string, any>): string[] {
  return script.sequence.find(
    (step: any) => step.action === "input_text.set_value"
  ).target.entity_id;
}

describe("Fast scene reliability contract", () => {
  it("gives every source scene automation latest-intent restart behavior", () => {
    for (const [automationId, automation] of Object.entries(automations)) {
      if (sceneActions(automation.action).length > 0) {
        expect(getEffectiveAutomationMode(automation), automationId).toBe("restart");
      }
    }
  });

  it("generates blocking fast-script actions for every scene automation", () => {
    const generatedById = new Map(
      generateAutomationsFromRegistry(automations).map((automation) => [
        automation.id,
        automation,
      ])
    );

    for (const [automationId, automation] of Object.entries(automations)) {
      const expectedSceneActions = sceneActions(automation.action);
      if (expectedSceneActions.length === 0) {
        continue;
      }

      const generated = generatedById.get(automationId);
      expect(generated, automationId).toBeDefined();
      expect(generated!.mode, automationId).toBe("restart");
      const generatedActions = collectObjects(
        generated!.actions,
        (candidate) => typeof candidate.action === "string"
      );
      for (const sceneAction of expectedSceneActions) {
        expect(
          generatedActions.some(
            (action) =>
              action.action === getFastSceneScriptEntityId(sceneAction.scene)
          ),
          automationId
        ).toBe(true);
      }
      expect(
        generatedActions.some((action) => action.action === "script.turn_on"),
        automationId
      ).toBe(false);
    }

    expect(generatedById.get("office_switch_doubleup")!.actions).toEqual([
      {
        action: "script.fast_scene_office_high",
        data: { origin_entity_id: "light.light_office_toggle" },
      },
    ]);
  });

  it("keeps nested scene actions blocking too", () => {
    const nested = convertAction({
      type: "choose",
      choices: [
        {
          conditions: [],
          sequence: [{ type: "scene", scene: "kitchen_off" }],
        },
      ],
      default: [{ type: "scene", scene: "all_off" }],
    });

    expect(nested).toEqual({
      choose: [
        {
          conditions: [],
          sequence: [{ action: "script.fast_scene_kitchen_off" }],
        },
      ],
      default: [{ action: "script.fast_scene_all_off" }],
    });
    expect(
      getEffectiveAutomationMode({
        alias: "Nested scene",
        trigger: { type: "webhook", webhook_id: "nested_scene" },
        action: {
          type: "choose",
          choices: [
            {
              conditions: [],
              sequence: [{ type: "scene", scene: "kitchen_off" }],
            },
          ],
        },
        mode: "restart",
      })
    ).toBe("restart");
  });

  it("keeps hand-written automations on direct fast-script actions", () => {
    const manualAutomations = yaml.parse(
      fs.readFileSync(
        path.resolve(__dirname, "../../manual/automations.yaml"),
        "utf8"
      )
    ) as Array<Record<string, any>>;

    for (const automation of manualAutomations) {
      const actions = collectObjects(
        automation.actions,
        (candidate) => typeof candidate.action === "string"
      );
      const nonBlockingFastSceneActions = actions.filter(
        (action) =>
          action.action === "script.turn_on" &&
          JSON.stringify(action.target ?? {}).includes("script.fast_scene_")
      );

      expect(nonBlockingFastSceneActions, automation.id).toHaveLength(0);
      expect(
        actions.some((action) => action.action === "scene.turn_on"),
        automation.id
      ).toBe(false);
      if (
        actions.length === 1 &&
        actions[0].action.startsWith("script.fast_scene_")
      ) {
        expect(automation.mode, automation.id).toBe("restart");
      }
    }

    for (const automationId of [
      "living_hallway_switch_double_up_living_room_high",
      "kitchen_hanging_switch_double_up_kitchen_high",
      "kitchen_hanging_switch_double_down_kitchen_off",
    ]) {
      const automation = manualAutomations.find(
        (candidate) => candidate.id === automationId
      );
      expect(automation?.actions[0].data?.origin_entity_id, automationId).toMatch(
        /^light\./
      );
    }
  });

  it("gives every scene a blocking intent wrapper and family restart dispatcher", () => {
    const scripts = generateFastScriptsFromRegistry(scenes);
    expect(scripts[FAST_SCENE_DISPATCHER_ID].mode).toBe("parallel");
    expect(scripts[FAST_SCENE_DISPATCHER_ID].max).toBe(16);
    expect(scripts[FAST_SCENE_DISPATCH_WORKER_ID].mode).toBe("parallel");
    expect(scripts[FAST_SCENE_DISPATCHER_ID].sequence).toEqual([
      {
        action: `script.${FAST_SCENE_DISPATCH_WORKER_ID}`,
        data: {
          scene_id: "{{ scene_id }}",
          intent_token: "{{ intent_token }}",
          origin_entity_id: "{{ origin_entity_id | default('') }}",
        },
      },
    ]);

    for (const sceneId of Object.keys(scenes)) {
      const familyDispatcher = scripts[
        `${FAST_SCENE_DISPATCHER_ID}_${sceneFamilyId(sceneId)}`
      ];
      expect(scripts[`fast_scene_${sceneId}`], sceneId).toMatchObject({
        mode: "restart",
        sequence: [
          {
            variables: {
              intent_token: expect.stringMatching(/^scene-.*strftime/),
            },
          },
          { action: "input_text.set_value" },
          {
            if: [{ value_template: "{{ origin_entity_id != '' }}" }],
            then: [
              {
                action: "script.turn_on",
                target: { entity_id: `script.${FAST_SCENE_RF_QUIET_ID}` },
              },
            ],
          },
          { action: `script.${FAST_SCENE_DISPATCHER_ID}` },
        ],
      });
      expect(familyDispatcher.mode, sceneId).toBe("restart");
      expect(
        collectObjects(
          familyDispatcher.sequence,
          (candidate) => candidate.delay?.milliseconds === 2000
        ),
        sceneId
      ).toHaveLength(1);
    }
  });

  it("keeps disjoint double-tap scenes additive and makes overlap newest-wins", () => {
    const scripts = generateFastScriptsFromRegistry(scenes);
    const kitchenHelpers = intentHelpersForWrapper(scripts.fast_scene_kitchen_high);
    const livingHighHelpers = intentHelpersForWrapper(
      scripts.fast_scene_living_room_high
    );
    const livingMediumHelpers = intentHelpersForWrapper(
      scripts.fast_scene_living_room_medium
    );
    const allOffHelpers = intentHelpersForWrapper(scripts.fast_scene_all_off);

    expect(kitchenHelpers).toContain("input_text.fast_scene_intent_kitchen");
    expect(kitchenHelpers).toContain(
      "input_text.fast_scene_intent_kitchen_and_living_room"
    );
    expect(livingHighHelpers).toEqual([
      "input_text.fast_scene_intent_living_room",
    ]);
    expect(livingHighHelpers).not.toContain(
      "input_text.fast_scene_intent_kitchen_and_living_room"
    );
    expect(livingMediumHelpers).toContain(
      "input_text.fast_scene_intent_kitchen_and_living_room"
    );
    expect(allOffHelpers).toEqual(
      expect.arrayContaining([
        "input_text.fast_scene_intent_kitchen",
        "input_text.fast_scene_intent_kitchen_and_living_room",
        "input_text.fast_scene_intent_living_room",
      ])
    );
    expect(Object.keys(generateFastSceneIntentHelpersFromRegistry(scenes))).toEqual(
      expect.arrayContaining([
        "fast_scene_intent_kitchen",
        "fast_scene_intent_kitchen_and_living_room",
        "fast_scene_intent_living_room",
      ])
    );
  });

  it("covers every target once and isolates every currently configured Z-Wave target", () => {
    for (const [sceneId, scene] of Object.entries(scenes)) {
      const targets = generateSceneTargets(scene);
      const calls = generateFastSceneCalls(scene);
      const calledEntityIds = calls.flatMap((call) => call.target.entity_id);
      const expectedEntityIds = targets.map((target) => target.entityId);

      expect([...calledEntityIds].sort(), sceneId).toEqual(
        [...expectedEntityIds].sort()
      );
      expect(new Set(calledEntityIds).size, sceneId).toBe(calledEntityIds.length);
      for (const target of targets.filter((candidate) => candidate.zwaveBacked)) {
        const call = calls.find((candidate) =>
          candidate.target.entity_id.includes(target.entityId)
        );
        expect(call, `${sceneId}:${target.entityId}`).toBeDefined();
        expect(call!.target.entity_id, `${sceneId}:${target.entityId}`).toEqual([
          target.entityId,
        ]);
      }
    }
  });

  it("does not generate multicast calls for the current device registry", () => {
    const scripts = generateFastScriptsFromRegistry({
      living_room_high: scenes.living_room_high,
    });
    const sequence = getSceneWorkerSequence(scripts, "living_room_high");
    const serialized = JSON.stringify(sequence);

    expect(serialized).not.toContain("zwave_js.multicast_set_value");
    expect(serialized).toContain("zwave_js.set_value");
    expect(serialized).toContain('"wait_for_result":false');
  });

  it("submits compatible dimmers without waiting and forces instant transitions", () => {
    const calls = generateFastSceneCalls(scenes.guest_bathroom_off);

    expect(calls).toHaveLength(1);
    expect(calls[0].target.entity_id).toEqual([
      "light.light_guestbathroom_sconce",
    ]);
    expect(
      calls.every(
        (call) =>
          call.action === "zwave_js.set_value" &&
          call.data?.command_class === 38 &&
          call.data?.property === "targetValue" &&
          call.data?.value === 0 &&
          call.data?.options?.transitionDuration === "0s" &&
          call.data?.wait_for_result === false
      )
    ).toBe(true);

    const scripts = generateFastScriptsFromRegistry({
      guest_bathroom_off: scenes.guest_bathroom_off,
    });
    const sequence = getSceneWorkerSequence(scripts, "guest_bathroom_off");
    const serialized = JSON.stringify(sequence);
    expect(serialized).toContain("zwave_js.set_value");
    expect(serialized).toContain('"wait_for_result":false');
    expect(serialized).toContain("| count > 0");
  });

  it("rejects scenes that cut power to a protected smart-light outlet", () => {
    expect(() =>
      generateFastSceneCalls({
        name: "Unsafe smart-light power cut",
        lights: [],
        switches: { bedroom_flamingopower: "off" },
      })
    ).toThrow(
      "Scene cannot turn off protected power device bedroom_flamingopower"
    );
  });

  it("health-filters every scene, isolates action errors, and bounds Z-Wave batches", () => {
    const scripts = generateFastScriptsFromRegistry(scenes);
    expect(scripts[FAST_SCENE_ZWAVE_GATE_ID]).toMatchObject({
      mode: "queued",
      max: 32,
    });

    for (const [sceneId, scene] of Object.entries(scenes)) {
      const sequence = getSceneWorkerSequence(scripts, sceneId);
      const serialized = JSON.stringify(sequence);
      const serviceActions = collectObjects(
        sequence,
        (candidate) =>
          typeof candidate.action === "string" &&
          (/^(light|switch)\.turn_(on|off)$/.test(candidate.action) ||
            candidate.action === `script.${FAST_SCENE_ZWAVE_GATE_ID}`)
      );
      const skippedEvents = collectObjects(
        sequence,
        (candidate) => candidate.event === FAST_SCENE_SKIPPED_EVENT
      );
      const zwaveEntityIds = generateSceneTargets(scene)
        .filter((target) => target.zwaveBacked)
        .map((target) => target.entityId);

      expect(serialized, sceneId).toContain("_node_status");
      expect(serialized, sceneId).toContain("unavailable");
      expect(serialized, sceneId).toContain("unknown");
      expect(skippedEvents, sceneId).toHaveLength(1);
      expect(serviceActions.length, sceneId).toBeGreaterThan(0);
      expect(
        serviceActions.every((action) => action.continue_on_error === true),
        sceneId
      ).toBe(true);

      for (const parallel of collectObjects(
        sequence,
        (candidate) => Array.isArray(candidate.parallel)
      )) {
        const batchText = JSON.stringify(parallel.parallel);
        const containsZwave = zwaveEntityIds.some((entityId) =>
          batchText.includes(entityId)
        );
        if (containsZwave) {
          expect(
            parallel.parallel.filter(
              (candidate: any) =>
                candidate.action === `script.${FAST_SCENE_ZWAVE_GATE_ID}`
            ).length,
            sceneId
          ).toBeLessThanOrEqual(DEFAULT_MAX_ZWAVE_CALLS_PER_STEP);
        }
      }
    }
  });
});
