import {strict as assert} from 'assert';

import {
  GroupAllIntentRequest,
  SonosIntentCoordinator,
} from './intents';

import '../types/sonos';

const zone = (coordinatorRoomName: string, roomNames: string[]): Sonos.Zone => {
  const members: Sonos.Member[] = roomNames.map(roomName => ({
    uuid: `${roomName}-uuid`,
    roomName,
    coordinator: coordinatorRoomName,
    state: {
      volume: 10,
      mute: false,
      equalizer: {
        bass: 0,
        treble: 0,
        loudness: false,
      },
      currentTrack: {
        artist: '',
        title: '',
        album: '',
        albumArtUri: '',
        duration: 0,
        uri: '',
        trackUri: '',
        type: '',
        stationName: '',
      },
      nextTrack: {
        artist: '',
        title: '',
        album: '',
        albumArtUri: '',
        duration: 0,
        uri: '',
      },
      trackNo: 0,
      elapsedTime: 0,
      elapsedTimeFormatted: '0:00',
      playbackState: 'STOPPED',
      playMode: {
        repeat: 'none' as const,
        shuffle: false,
        crossfade: false,
      },
      sub: {
        gain: 0,
        crossover: 0,
        polarity: 0,
        enabled: false,
      },
    },
    groupState: {
      volume: 10,
      mute: false,
    },
  }));

  return {
    uuid: `${coordinatorRoomName}-zone`,
    coordinator: members[0],
    members,
  };
};

async function run(): Promise<void> {
  const roomRequest: GroupAllIntentRequest = {
    targetRoom: 'Kitchen',
    roomNames: ['Living Room', 'Bedroom', 'Kitchen'],
    requestedFromRoom: 'Bedroom',
  };

  {
    let joinedRooms = ['Kitchen'];
    const joins: Array<{roomName: string; coordinatorRoom: string}> = [];
    const volumeSets: Array<{roomName: string; volume: number}> = [];
    const coordinator = new SonosIntentCoordinator(
      {
        async getZones(): Promise<Sonos.Zone[]> {
          return [zone('Kitchen', joinedRooms)];
        },
        async joinRoom(roomName: string, coordinatorRoom: string): Promise<void> {
          joins.push({roomName, coordinatorRoom});
          if (joinedRooms.indexOf(roomName) < 0) {
            joinedRooms = joinedRooms.concat([roomName]);
          }
        },
        async getState(): Promise<Sonos.State> {
          return {
            volume: 17,
            mute: false,
            equalizer: {
              bass: 0,
              treble: 0,
              loudness: false,
            },
            currentTrack: {
              artist: '',
              title: '',
              album: '',
              albumArtUri: '',
              duration: 0,
              uri: '',
              trackUri: '',
              type: '',
              stationName: '',
            },
            nextTrack: {
              artist: '',
              title: '',
              album: '',
              albumArtUri: '',
              duration: 0,
              uri: '',
            },
            trackNo: 0,
            elapsedTime: 0,
            elapsedTimeFormatted: '0:00',
            playbackState: 'STOPPED',
            playMode: {
              repeat: 'none' as const,
              shuffle: false,
              crossfade: false,
            },
            sub: {
              gain: 0,
              crossover: 0,
              polarity: 0,
              enabled: false,
            },
          };
        },
        async setVolume(roomName: string, volume: number): Promise<void> {
          volumeSets.push({roomName, volume});
        },
      },
      {
        observeDelayMs: 0,
        terminalRetentionMs: 1000,
        sleep: async () => undefined,
      }
    );

    const initial = coordinator.createGroupAllIntent(roomRequest);
    assert.equal(initial.status, 'running');
    coordinator.enableVolumeSync('Bedroom');
    await new Promise(resolve => setTimeout(resolve, 25));

    const status = coordinator.getStatus();
    assert.equal(status.activeIntent, null);
    assert(status.recentIntent);
    assert.equal(status.recentIntent && status.recentIntent.status, 'completed');
    assert.deepEqual(
      joins,
      [
        {roomName: 'Living Room', coordinatorRoom: 'Kitchen'},
        {roomName: 'Bedroom', coordinatorRoom: 'Kitchen'},
      ]
    );
    assert.deepEqual(
      volumeSets,
      [
        {roomName: 'Kitchen', volume: 17},
        {roomName: 'Kitchen', volume: 17},
        {roomName: 'Living Room', volume: 17},
      ]
    );
  }

  {
    const coordinator = new SonosIntentCoordinator(
      {
        async getZones(): Promise<Sonos.Zone[]> {
          return [zone('Kitchen', ['Kitchen'])];
        },
        async joinRoom(): Promise<void> {
          return;
        },
        async getState(): Promise<Sonos.State> {
          throw new Error('unused');
        },
        async setVolume(): Promise<void> {
          return;
        },
      },
      {
        observeDelayMs: 100,
        terminalRetentionMs: 1000,
      }
    );

    const first = coordinator.createGroupAllIntent(roomRequest);
    const second = coordinator.createGroupAllIntent(roomRequest);
    assert.equal(first.id, second.id);

    coordinator.cancelActiveIntent('Cancelled by manual action');
    const status = coordinator.getStatus();
    assert.equal(status.activeIntent, null);
    assert(status.recentIntent);
    assert.equal(status.recentIntent && status.recentIntent.status, 'cancelled');
  }

  {
    let joins = 0;
    let nowValue = 0;
    const coordinator = new SonosIntentCoordinator(
      {
        async getZones(): Promise<Sonos.Zone[]> {
          return [zone('Kitchen', ['Kitchen'])];
        },
        async joinRoom(): Promise<void> {
          joins += 1;
          throw new Error('speaker busy');
        },
        async getState(): Promise<Sonos.State> {
          throw new Error('unused');
        },
        async setVolume(): Promise<void> {
          return;
        },
      },
      {
        observeDelayMs: 0,
        terminalRetentionMs: 1000,
        timeoutMs: 5,
        now: () => {
          nowValue += 10;
          return nowValue;
        },
        sleep: async () => undefined,
      }
    );

    coordinator.createGroupAllIntent(roomRequest);
    await new Promise(resolve => setTimeout(resolve, 25));

    const status = coordinator.getStatus();
    assert.equal(status.activeIntent, null);
    assert(status.recentIntent);
    assert.equal(status.recentIntent && status.recentIntent.status, 'timed_out');
  }

  {
    const coordinator = new SonosIntentCoordinator(
      {
        async getZones(): Promise<Sonos.Zone[]> {
          return [zone('Kitchen', ['Kitchen'])];
        },
        async joinRoom(): Promise<void> {
          return;
        },
        async getState(): Promise<Sonos.State> {
          throw new Error('unused');
        },
        async setVolume(): Promise<void> {
          return;
        },
      }
    );

    assert.equal(coordinator.isTopologyMutationRoute('Kitchen/join/Living%20Room'), true);
    assert.equal(coordinator.isTopologyMutationRoute('Kitchen/leave'), true);
    assert.equal(coordinator.isTopologyMutationRoute('Kitchen/groupVolume/+2'), false);
  }
}

run().catch(err => {
  console.error(err);
  process.exitCode = 1;
});
