import {strict as assert} from 'assert';

import {
  compareSonosBackends,
  SonosShadowPersistenceTracker,
  ShadowZoneLike,
} from './sonos-shadow-compare';

const member = (roomName: string, volume: number) => ({
  roomName,
  state: {
    volume,
    playbackState: 'PLAYING',
    currentTrack: {
      title: 'Track', artist: 'Artist', album: 'Album', stationName: 'Station',
    },
  },
});

const node: ShadowZoneLike[] = [{
  coordinator: member('Kitchen', 10),
  members: [member('Kitchen', 10), member('Office', 20), member('Bedroom', 30)],
}];
const reordered: ShadowZoneLike[] = [{
  coordinator: member('Kitchen', 11),
  members: [member('Kitchen', 11), member('Bedroom', 30), member('Office', 20)],
}];

assert.deepEqual(compareSonosBackends(node, reordered), {equal: true, differences: []},
  'member order and a one-point volume delta are comparison noise');

const nodeRadio: ShadowZoneLike[] = [{
  coordinator: {
    ...member('Kitchen', 10),
    state: {
      ...member('Kitchen', 10).state,
      currentTrack: {
        title: 'TYPE=SNG|TITLE Test Track|ARTIST Test Artist|ALBUM Test Album',
        artist: 'CH 735 - Test Radio',
        album: '',
        stationName: 'CH 735 - Test Radio',
      },
    },
  },
  members: [{
    ...member('Kitchen', 10),
    state: {
      ...member('Kitchen', 10).state,
      currentTrack: {
        title: 'TYPE=SNG|TITLE Test Track|ARTIST Test Artist|ALBUM Test Album',
        artist: 'CH 735 - Test Radio',
        album: '',
        stationName: 'CH 735 - Test Radio',
      },
    },
  }],
}];
const homeAssistantRadio: ShadowZoneLike[] = [{
  coordinator: {
    ...member('Kitchen', 10),
    state: {
      ...member('Kitchen', 10).state,
      currentTrack: {
        title: 'Test Track',
        artist: 'Test Artist',
        album: 'Test Album',
        stationName: 'CH 735 - Test Radio',
      },
    },
  },
  members: [{
    ...member('Kitchen', 10),
    state: {
      ...member('Kitchen', 10).state,
      currentTrack: {
        title: 'Test Track',
        artist: 'Test Artist',
        album: 'Test Album',
        stationName: 'CH 735 - Test Radio',
      },
    },
  }],
}];
assert.deepEqual(compareSonosBackends(nodeRadio, homeAssistantRadio), {
  equal: true,
  differences: [],
}, 'structured node live-radio metadata matches equivalent HA fields');

const wrongStation = structuredClone(homeAssistantRadio);
wrongStation[0].coordinator.state!.currentTrack!.stationName = 'Different Radio';
wrongStation[0].members[0].state!.currentTrack!.stationName = 'Different Radio';
assert.ok(compareSonosBackends(nodeRadio, wrongStation).differences.some(
  difference => difference.field === 'stationName'
), 'a real live-radio station difference remains visible');

const changed: ShadowZoneLike[] = [{
  coordinator: member('Office', 20),
  members: [member('Office', 20), member('Kitchen', 10)],
}];
const result = compareSonosBackends(node, changed);
assert.equal(result.equal, false);
assert.ok(result.differences.some(difference => difference.kind === 'coordinator'));
assert.ok(result.differences.some(difference => difference.kind === 'topology'));
assert.ok(result.differences.some(difference => difference.kind === 'missing_room'));

let now = 0;
const persistence = new SonosShadowPersistenceTracker({
  graceMs: 5_000,
  now: () => now,
});
const volumeDifference = compareSonosBackends(node, [{
  coordinator: member('Kitchen', 20),
  members: [member('Kitchen', 20), member('Office', 30), member('Bedroom', 40)],
}]).differences;

assert.deepEqual(persistence.observe(volumeDifference), {
  persistentDifferences: [],
  newlyPersistentDifferences: [],
  oldestPersistentAgeMs: 0,
}, 'the first mismatch observation is inside the grace interval');

now = 4_999;
assert.equal(persistence.observe(volumeDifference).persistentDifferences.length, 0,
  'a mismatch just inside the grace interval remains transient');

now = 5_000;
const firstPersistent = persistence.observe(volumeDifference);
assert.equal(firstPersistent.persistentDifferences.length, 3);
assert.equal(firstPersistent.newlyPersistentDifferences.length, 3);
assert.equal(firstPersistent.oldestPersistentAgeMs, 5_000);

now = 6_000;
const alreadyEmitted = persistence.observe(volumeDifference);
assert.equal(alreadyEmitted.persistentDifferences.length, 3);
assert.equal(alreadyEmitted.newlyPersistentDifferences.length, 0,
  'an unchanged persistent mismatch is emitted only once');

now = 6_001;
persistence.observe([]);
now = 10_000;
assert.equal(persistence.observe(volumeDifference).persistentDifferences.length, 0,
  'a converged observation clears persistence history');
now = 15_000;
assert.equal(persistence.observe(volumeDifference).newlyPersistentDifferences.length, 3,
  'a mismatch recurring after convergence must satisfy a new grace interval');
