import {strict as assert} from 'assert';

import {SonosBackendError} from './sonos-contract';
import {
  assertValidHomeAssistantSonosPresetDefinitions,
  executeHomeAssistantSonosPreset,
  HOME_ASSISTANT_SONOS_PRESETS,
  HomeAssistantSonosPresetDefinitionError,
  planHomeAssistantSonosPreset,
} from './home-assistant-sonos-presets';

interface RecordedCall {
  domain: string;
  service: string;
  data: Record<string, unknown>;
}

const expectedCalls = (
  name: string
): Array<Omit<RecordedCall, 'domain'>> => {
  return planHomeAssistantSonosPreset(name).steps.map(({service, data}) => ({
    service,
    data: {...data},
  }));
};

const run = async (): Promise<void> => {
  assert.doesNotThrow(() =>
    assertValidHomeAssistantSonosPresetDefinitions(HOME_ASSISTANT_SONOS_PRESETS));

  {
    const plan = planHomeAssistantSonosPreset('Bedroom-tv');
    assert.equal(plan.coordinator, 'Bedroom');
    assert.deepEqual(plan.members, ['Bedroom', 'Bathroom', 'Closet']);
    assert.deepEqual(plan.pauseOthers, []);
    assert.deepEqual(expectedCalls('Bedroom-tv'), [
      {service: 'unjoin', data: {entity_id: 'media_player.bedroom'}},
      {
        service: 'join',
        data: {
          entity_id: 'media_player.bedroom',
          group_members: ['media_player.bathroom', 'media_player.closet'],
        },
      },
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.bedroom', volume_level: 0.3},
      },
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.bathroom', volume_level: 0.3},
      },
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.closet', volume_level: 0.3},
      },
      {
        service: 'select_source',
        data: {entity_id: 'media_player.bedroom', source: 'TV'},
      },
    ]);
  }

  {
    const plan = planHomeAssistantSonosPreset('Living Room-tv');
    assert.equal(plan.coordinator, 'Living Room');
    assert.deepEqual(plan.members, ['Living Room', 'Kitchen', 'Guest Bathroom']);
    assert.deepEqual(plan.pauseOthers, [
      'Bathroom',
      'Closet',
      'Bedroom',
      'Move',
      'Office',
    ]);
    assert.deepEqual(expectedCalls('Living Room-tv'), [
      {
        service: 'media_pause',
        data: {entity_id: [
          'media_player.bathroom',
          'media_player.closet',
          'media_player.bedroom',
          'media_player.move',
          'media_player.office',
        ]},
      },
      {service: 'unjoin', data: {entity_id: 'media_player.living_room'}},
      {
        service: 'join',
        data: {
          entity_id: 'media_player.living_room',
          group_members: ['media_player.kitchen', 'media_player.guest_bathroom'],
        },
      },
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.living_room', volume_level: 0.3},
      },
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.kitchen', volume_level: 0.3},
      },
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.guest_bathroom', volume_level: 0.3},
      },
      {
        service: 'select_source',
        data: {entity_id: 'media_player.living_room', source: 'TV'},
      },
    ]);
  }

  {
    const plan = planHomeAssistantSonosPreset('Office-tv');
    assert.equal(plan.coordinator, 'Office');
    assert.deepEqual(plan.members, ['Office']);
    assert.deepEqual(plan.pauseOthers, []);
    assert.deepEqual(expectedCalls('Office-tv'), [
      {service: 'unjoin', data: {entity_id: 'media_player.office'}},
      {
        service: 'volume_set',
        data: {entity_id: 'media_player.office', volume_level: 0.2},
      },
      {
        service: 'select_source',
        data: {entity_id: 'media_player.office', source: 'TV'},
      },
    ]);
  }

  for (const name of ['example', 'Unknown', '', 'office-tv']) {
    assert.throws(
      () => planHomeAssistantSonosPreset(name),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'unknown_preset' && error.statusCode === 404
    );
  }

  {
    let calls = 0;
    await assert.rejects(
      async () => executeHomeAssistantSonosPreset('example', {
        client: {callService: async () => { calls += 1; }},
        observe: () => ({groups: []}),
      }),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'unknown_preset'
    );
    assert.equal(calls, 0);
  }

  {
    const invalidDefinitions: unknown[] = [
      {
        ...HOME_ASSISTANT_SONOS_PRESETS,
        example: HOME_ASSISTANT_SONOS_PRESETS['Office-tv'],
      },
      {
        ...HOME_ASSISTANT_SONOS_PRESETS,
        'Office-tv': {
          players: [{roomName: 'TV Room', volume: 20}],
          source: 'TV',
        },
      },
      {
        ...HOME_ASSISTANT_SONOS_PRESETS,
        'Office-tv': {
          players: [{roomName: 'Office', volume: 20, entity_id: 'media_player.maker_room'}],
          source: 'TV',
        },
      },
      {
        ...HOME_ASSISTANT_SONOS_PRESETS,
        'Office-tv': {
          players: [{roomName: 'Office', volume: 20}],
          source: 'x-sonos-htastream:arbitrary',
          uri: 'x-sonos-htastream:arbitrary',
        },
      },
      {
        ...HOME_ASSISTANT_SONOS_PRESETS,
        'Office-tv': {
          players: [
            {roomName: 'Office', volume: 20},
            {roomName: 'Office', volume: 20},
          ],
          source: 'TV',
        },
      },
    ];
    for (const definitions of invalidDefinitions) {
      assert.throws(
        () => assertValidHomeAssistantSonosPresetDefinitions(definitions),
        HomeAssistantSonosPresetDefinitionError
      );
    }
  }

  {
    const calls: RecordedCall[] = [];
    const result = await executeHomeAssistantSonosPreset('Office-tv', {
      client: {
        callService: async (domain, service, data) => {
          calls.push({domain, service, data});
        },
      },
      observe: () => {
        throw new Error('success must not perform a failure observation');
      },
    });
    assert.equal(result.status, 'completed');
    assert.equal(result.atomic, false);
    assert.equal(result.rollbackAttempted, false);
    assert.equal(calls.length, 3);
    assert.ok(calls.every(call => call.domain === 'media_player'));
  }

  for (let failAt = 0; failAt < planHomeAssistantSonosPreset('Bedroom-tv').steps.length; failAt += 1) {
    const calls: RecordedCall[] = [];
    const failure = new Error(`failure-${failAt}`);
    const observation = {groupMembers: ['media_player.bedroom'], revision: failAt};
    const result = await executeHomeAssistantSonosPreset('Bedroom-tv', {
      client: {
        callService: async (domain, service, data) => {
          calls.push({domain, service, data});
          if (calls.length - 1 === failAt) {
            throw failure;
          }
        },
      },
      observe: () => observation,
    });
    assert.equal(result.status, 'failed');
    if (result.status !== 'failed') {
      throw new Error('expected a failed preset result');
    }
    assert.equal(result.failedStep.id,
      planHomeAssistantSonosPreset('Bedroom-tv').steps[failAt].id);
    assert.equal(result.completedStepIds.length, failAt);
    assert.deepEqual(result.observation, observation);
    assert.equal(result.observationError, null);
    assert.equal(result.cause, failure);
    assert.equal(result.atomic, false);
    assert.equal(result.rollbackAttempted, false);
    assert.equal(calls.length, failAt + 1);
  }

  {
    const serviceFailure = new Error('service failed');
    const observationFailure = new Error('observation failed');
    const result = await executeHomeAssistantSonosPreset('Office-tv', {
      client: {callService: async () => { throw serviceFailure; }},
      observe: () => { throw observationFailure; },
    });
    assert.equal(result.status, 'failed');
    if (result.status !== 'failed') {
      throw new Error('expected a failed preset result');
    }
    assert.equal(result.observation, null);
    assert.equal(result.observationError, observationFailure);
    assert.equal(result.cause, serviceFailure);
  }

  {
    let calls = 0;
    let obsolete = false;
    const result = await executeHomeAssistantSonosPreset('Bedroom-tv', {
      client: {
        callService: async () => {
          calls += 1;
          obsolete = true;
        },
      },
      observe: () => ({groups: []}),
      isObsolete: () => obsolete,
    });
    assert.equal(result.status, 'cancelled');
    assert.equal(calls, 1,
      'a superseded preset finishes only its in-flight call and submits no later step');
    assert.deepEqual(result.completedStepIds, ['isolate_coordinator:Bedroom']);
  }
};

run().catch(error => {
  console.error(error);
  process.exit(1);
});
