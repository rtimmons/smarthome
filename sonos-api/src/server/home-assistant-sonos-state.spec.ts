import {strict as assert} from 'assert';

import {
  projectCanonicalSonosTopology,
  projectLegacySonosState,
  projectRoomState,
  sonosFreshnessHeaders,
  SonosProjectionError,
} from './home-assistant-sonos-state';
import {haSnapshot, haState} from './home-assistant-test-fixtures';
import {SONOS_ROOM_NAMES, SonosRoomName} from './sonos-room-map';

const run = (): void => {
  const projectionNow = Date.parse('2026-08-28T12:00:05.000Z');
  const projectionCases = [
    {
      label: 'playing on-demand media',
      state: 'playing',
      attributes: {
        media_title: 'Playing track',
        media_artist: 'Playing artist',
        media_album_name: 'Playing album',
        media_content_id: 'x-test:playing',
        media_content_type: 'music',
        media_duration: 300,
        media_position: 12,
        media_position_updated_at: '2026-08-28T12:00:00.000Z',
      },
      playbackState: 'PLAYING',
      elapsedTime: 17,
    },
    {
      label: 'paused live radio',
      state: 'paused',
      attributes: {
        media_title: 'Radio track',
        media_channel: 'Radio station',
        media_position: 12,
        media_position_updated_at: '2026-08-28T12:00:00.000Z',
      },
      playbackState: 'STOPPED',
      elapsedTime: 12,
    },
    {
      label: 'paused on-demand media',
      state: 'paused',
      attributes: {
        media_title: 'Paused track',
        media_artist: 'Paused artist',
        media_position: 12,
        media_position_updated_at: '2026-08-28T12:00:00.000Z',
      },
      playbackState: 'PAUSED_PLAYBACK',
      elapsedTime: 12,
    },
    {
      label: 'stopped media',
      state: 'idle',
      attributes: {media_title: 'Stopped track', media_position: 9},
      playbackState: 'STOPPED',
      elapsedTime: 9,
    },
    {
      label: 'buffering media',
      state: 'buffering',
      attributes: {media_title: 'Buffering track', media_position: 4},
      playbackState: 'STOPPED',
      elapsedTime: 4,
    },
  ] as const;
  for (const expected of projectionCases) {
    const state = haState('Kitchen', {
      state: expected.state,
      attributes: expected.attributes,
    });
    const projected = projectLegacySonosState(state, state, 'Kitchen', {
      now: () => projectionNow,
    });
    assert.equal(projected.playbackState, expected.playbackState, expected.label);
    assert.equal(projected.elapsedTime, expected.elapsedTime, expected.label);
  }

  const missingMetadataState = haState('Kitchen', {
    state: 'idle',
    attributes: {
      media_title: null,
      media_artist: 17,
      media_album_name: undefined,
      media_channel: false,
      media_content_id: null,
      media_content_type: [],
      media_duration: 'not-a-number',
      media_position: undefined,
    },
  });
  const missingMetadata = projectLegacySonosState(
    missingMetadataState,
    missingMetadataState,
    'Kitchen',
    {now: () => projectionNow}
  );
  assert.deepEqual(missingMetadata.currentTrack, {
    artist: '',
    title: '',
    album: '',
    albumArtUri: './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z',
    absoluteAlbumArtUri: './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z',
    duration: 0,
    uri: '',
    trackUri: '',
    type: '',
    stationName: '',
  }, 'missing and malformed media metadata projects to stable compatibility defaults');
  assert.equal(missingMetadata.elapsedTime, 0);

  const singletonGolden = projectCanonicalSonosTopology(
    haSnapshot([haState('Kitchen')]),
    {now: () => projectionNow}
  );
  assert.deepEqual(singletonGolden.zones, [{
    uuid: 'ha:media_player.kitchen',
    coordinator: {
      uuid: 'media_player.kitchen',
      roomName: 'Kitchen',
      coordinator: 'Kitchen',
      state: {
        volume: 10,
        mute: false,
        equalizer: {bass: 0, treble: 0, loudness: false},
        currentTrack: {
          artist: '',
          title: '',
          album: '',
          albumArtUri: './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z',
          absoluteAlbumArtUri: './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z',
          duration: 0,
          uri: '',
          trackUri: '',
          type: '',
          stationName: '',
        },
        nextTrack: {artist: '', title: '', album: '', albumArtUri: '', duration: 0, uri: ''},
        trackNo: 0,
        elapsedTime: 0,
        elapsedTimeFormatted: '0:00',
        playbackState: 'STOPPED',
        playMode: {repeat: 'none', shuffle: false, crossfade: false},
        sub: {gain: 0, crossover: 0, polarity: 0, enabled: false},
      },
      groupState: {volume: 10, mute: false},
    },
    members: [{
      uuid: 'media_player.kitchen',
      roomName: 'Kitchen',
      coordinator: 'Kitchen',
      state: {
        volume: 10,
        mute: false,
        equalizer: {bass: 0, treble: 0, loudness: false},
        currentTrack: {
          artist: '',
          title: '',
          album: '',
          albumArtUri: './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z',
          absoluteAlbumArtUri: './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z',
          duration: 0,
          uri: '',
          trackUri: '',
          type: '',
          stationName: '',
        },
        nextTrack: {artist: '', title: '', album: '', albumArtUri: '', duration: 0, uri: ''},
        trackNo: 0,
        elapsedTime: 0,
        elapsedTimeFormatted: '0:00',
        playbackState: 'STOPPED',
        playMode: {repeat: 'none', shuffle: false, crossfade: false},
        sub: {gain: 0, crossover: 0, polarity: 0, enabled: false},
      },
      groupState: {volume: 10, mute: false},
    }],
  }], 'the complete legacy /zones member schema and defaults are frozen');
  assert.deepEqual(singletonGolden.unknownRooms, [
    'Bathroom', 'Bedroom', 'Closet', 'Guest Bathroom', 'Living Room', 'Move', 'Office',
  ]);

  const coordinator: SonosRoomName = 'Bedroom';
  const remaining = SONOS_ROOM_NAMES.filter(room => room !== coordinator);
  const states = SONOS_ROOM_NAMES.map((roomName, index) => {
    const tail = index % 2 === 0 ? remaining : [...remaining].reverse();
    return haState(roomName, {
      state: roomName === coordinator ? 'playing' : 'idle',
      members: [coordinator, ...tail],
      attributes: roomName === coordinator ? {
        volume_level: 0.15,
        media_title: 'Test Track',
        media_artist: '',
        media_channel: 'Test Station',
        media_album_name: 'Test Album',
        media_content_id: 'x-test:track',
        media_duration: 300,
        media_position: 12,
        media_position_updated_at: '2026-08-28T12:00:00.000Z',
      } : {
        volume_level: roomName === 'Kitchen' ? 0.32 : 0.1,
      },
    });
  });
  const snapshot = haSnapshot(states);
  const topology = projectCanonicalSonosTopology(snapshot, {
    now: () => Date.parse('2026-08-28T12:00:05.000Z'),
  });
  assert.equal(topology.zones.length, 1);
  assert.equal(topology.zones[0].coordinator.roomName, 'Bedroom');
  assert.deepEqual(
    topology.zones[0].members.map(member => member.roomName),
    ['Bedroom', ...remaining.sort()]
  );
  assert.equal(topology.unknownRooms.length, 0);

  const kitchen = projectRoomState(snapshot, 'Kitchen', {
    now: () => Date.parse('2026-08-28T12:00:05.000Z'),
  });
  assert.equal(kitchen.volume, 32, 'member volume comes from the requested room');
  assert.equal(kitchen.currentTrack.title, 'Test Track', 'metadata comes from coordinator');
  assert.equal(kitchen.currentTrack.artist, 'Test Station', 'channel is the artist fallback');
  assert.equal(kitchen.elapsedTime, 17);
  assert.equal(kitchen.currentTrack.absoluteAlbumArtUri,
    './sonos/Kitchen/artwork?v=2026-08-28T12%3A00%3A00.000Z');
  assert.deepEqual(kitchen.nextTrack, {
    artist: '', title: '', album: '', albumArtUri: '', duration: 0, uri: '',
  });

  for (const possibleCoordinator of SONOS_ROOM_NAMES) {
    const otherRooms = SONOS_ROOM_NAMES.filter(room => room !== possibleCoordinator);
    const coordinatorFirst = [possibleCoordinator, ...otherRooms] as SonosRoomName[];
    const candidate = projectCanonicalSonosTopology(haSnapshot(
      SONOS_ROOM_NAMES.map((room, index) => haState(room, {
        state: room === possibleCoordinator ? 'playing' : 'idle',
        members: [
          possibleCoordinator,
          ...(index % 2 === 0 ? otherRooms : [...otherRooms].reverse()),
        ],
        attributes: room === possibleCoordinator
          ? {media_title: `Owned by ${possibleCoordinator}`}
          : {},
      }))
    ));
    assert.equal(candidate.zones.length, 1, possibleCoordinator);
    assert.equal(candidate.zones[0].coordinator.roomName, possibleCoordinator);
    assert.equal(candidate.zones[0].members[0].roomName, possibleCoordinator);
    assert.ok(candidate.zones[0].members.every(member =>
      member.coordinator === possibleCoordinator &&
      member.state.currentTrack.title === `Owned by ${possibleCoordinator}`
    ), `all group members project ${possibleCoordinator}'s coordinator-owned state`);
    assert.deepEqual(
      new Set(candidate.zones[0].members.map(member => member.roomName)),
      new Set(coordinatorFirst),
      `${possibleCoordinator} topology contains every configured room`
    );
  }

  const allSingletons = projectCanonicalSonosTopology(haSnapshot(
    SONOS_ROOM_NAMES.map(room => haState(room))
  ));
  assert.equal(allSingletons.zones.length, SONOS_ROOM_NAMES.length);
  assert.deepEqual(
    new Set(allSingletons.zones.map(zone => zone.coordinator.roomName)),
    new Set(SONOS_ROOM_NAMES)
  );
  assert.ok(allSingletons.zones.every(zone =>
    zone.members.length === 1 &&
    zone.members[0].roomName === zone.coordinator.roomName
  ), 'all eight singleton rooms remain eight authoritative groups');

  const groupDefinitions: Array<{
    coordinator: SonosRoomName;
    members: SonosRoomName[];
  }> = [
    {coordinator: 'Bathroom', members: ['Bathroom', 'Kitchen']},
    {coordinator: 'Bedroom', members: ['Bedroom', 'Closet', 'Office']},
    {coordinator: 'Living Room', members: ['Living Room', 'Guest Bathroom']},
    {coordinator: 'Move', members: ['Move']},
  ];
  const multipleGroups = projectCanonicalSonosTopology(haSnapshot(
    SONOS_ROOM_NAMES.map((room, index) => {
      const group = groupDefinitions.find(candidate => candidate.members.includes(room));
      assert.ok(group, `group fixture includes ${room}`);
      const followers = group.members.filter(member => member !== group.coordinator);
      return haState(room, {
        state: room === group.coordinator ? 'playing' : 'idle',
        members: [
          group.coordinator,
          ...(index % 2 === 0 ? followers : [...followers].reverse()),
        ],
      });
    })
  ));
  assert.deepEqual(
    multipleGroups.zones.map(zone => ({
      coordinator: zone.coordinator.roomName,
      members: zone.members.map(member => member.roomName),
    })),
    [
      {coordinator: 'Bathroom', members: ['Bathroom', 'Kitchen']},
      {coordinator: 'Bedroom', members: ['Bedroom', 'Closet', 'Office']},
      {coordinator: 'Living Room', members: ['Living Room', 'Guest Bathroom']},
      {coordinator: 'Move', members: ['Move']},
    ],
    'multiple groups and a singleton are independently canonicalized'
  );

  const pausedMembers = [
    'Bedroom' as SonosRoomName,
    ...SONOS_ROOM_NAMES.filter(room => room !== 'Bedroom'),
  ];
  const pausedState = projectRoomState(haSnapshot(
    SONOS_ROOM_NAMES.map(room => haState(room, {
      state: room === 'Bedroom' ? 'paused' : 'idle',
      members: pausedMembers,
      attributes: room === 'Bedroom' ? {media_channel: 'Test Station'} : {},
    }))
  ), 'Kitchen');
  assert.equal(pausedState.playbackState, 'STOPPED',
    'paused live radio preserves the live-observed node compatibility value');

  const pausedOnDemandState = projectRoomState(haSnapshot(
    SONOS_ROOM_NAMES.map(room => haState(room, {
      state: room === 'Bedroom' ? 'paused' : 'idle',
      members: pausedMembers,
      attributes: room === 'Bedroom' ? {media_title: 'On-demand track'} : {},
    }))
  ), 'Kitchen');
  assert.equal(pausedOnDemandState.playbackState, 'PAUSED_PLAYBACK',
    'paused on-demand media retains the legacy PAUSED_PLAYBACK value');

  const unavailable = haSnapshot([
    ...SONOS_ROOM_NAMES.filter(room => room !== 'Office').map(room => haState(room)),
    haState('Office', {state: 'unavailable'}),
  ]);
  const partial = projectCanonicalSonosTopology(unavailable);
  assert.ok(partial.unknownRooms.includes('Office'));
  assert.equal(partial.zones.some(zone =>
    zone.members.some(member => member.roomName === 'Office')), false,
  'an unavailable room is not invented as a singleton');

  assert.throws(
    () => projectCanonicalSonosTopology({...snapshot, freshness: 'unknown'}),
    /topology is unknown/
  );

  const invalidRoomCases = [
    {
      label: 'unavailable coordinator',
      states: [
        haState('Bedroom', {state: 'unavailable', members: ['Bedroom', 'Kitchen']}),
        haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
      ],
    },
    {
      label: 'requested member omitted',
      states: [
        haState('Bedroom', {members: ['Bedroom']}),
        haState('Kitchen', {members: ['Bedroom']}),
      ],
    },
    {
      label: 'duplicate requested member',
      states: [
        haState('Bedroom', {members: ['Bedroom', 'Kitchen']}),
        haState('Kitchen', {members: ['Bedroom', 'Kitchen', 'Kitchen']}),
      ],
    },
    {
      label: 'coordinator disagrees with follower set',
      states: [
        haState('Bedroom', {members: ['Bedroom']}),
        haState('Kitchen', {members: ['Bedroom', 'Kitchen']}),
      ],
    },
  ];
  for (const invalid of invalidRoomCases) {
    assert.throws(
      () => projectRoomState(haSnapshot(invalid.states), 'Kitchen'),
      SonosProjectionError,
      invalid.label
    );
  }

  const malformedKitchen = haState('Kitchen');
  malformedKitchen.attributes.group_members = [
    'media_player.kitchen',
    'media_player.maker_room',
  ];
  assert.throws(
    () => projectCanonicalSonosTopology(haSnapshot([
      malformedKitchen,
      ...SONOS_ROOM_NAMES.filter(room => room !== 'Kitchen').map(room => haState(room)),
    ])),
    (error: unknown) => error instanceof SonosProjectionError &&
      error.message.includes('media_player.maker_room')
  );

  assert.deepEqual(sonosFreshnessHeaders({...snapshot, freshness: 'stale', ageMs: 1250}), {
    'X-Sonos-Response-Source': 'home_assistant',
    'X-Sonos-Response-Stale': 'true',
    'X-Sonos-Observed-At': '2026-08-28T12:00:00.000Z',
    'X-Sonos-Age-Ms': '1250',
  });
};

try {
  run();
} catch (error) {
  console.error(error);
  process.exit(1);
}
