import {HomeAssistantEntityState} from './home-assistant-client';
import {SonosStateSnapshot} from './sonos-contract';
import {
  SONOS_ROOM_TO_ENTITY,
  SonosRoomName,
} from './sonos-room-map';

export const haState = (
  roomName: SonosRoomName,
  options: {
    state?: string;
    members?: SonosRoomName[];
    attributes?: Record<string, unknown>;
    updated?: string;
  } = {}
): HomeAssistantEntityState => {
  const entityId = SONOS_ROOM_TO_ENTITY[roomName];
  return {
    entity_id: entityId,
    state: options.state || 'idle',
    attributes: {
      friendly_name: roomName,
      volume_level: 0.1,
      is_volume_muted: false,
      group_members: (options.members || [roomName]).map(
        member => SONOS_ROOM_TO_ENTITY[member]
      ),
      ...options.attributes,
    },
    last_changed: options.updated || '2026-08-28T12:00:00.000Z',
    last_updated: options.updated || '2026-08-28T12:00:00.000Z',
  };
};

export const haSnapshot = (
  states: readonly HomeAssistantEntityState[],
  options: Partial<Omit<SonosStateSnapshot, 'entities'>> = {}
): SonosStateSnapshot => ({
  freshness: 'live',
  connected: true,
  observedAt: Date.parse('2026-08-28T12:00:00.000Z'),
  ageMs: 0,
  entities: new Map(states.map(state => [state.entity_id, state])),
  ...options,
});

export const deferred = <T>() => {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return {promise, resolve, reject};
};

export const nextTurn = (): Promise<void> => new Promise(resolve => setImmediate(resolve));
