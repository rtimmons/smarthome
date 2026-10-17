import { SONOS_ROOM_TO_ENTITY } from './room-catalog';
export { SONOS_ROOM_TO_ENTITY } from './room-catalog';

export type SonosRoomName = keyof typeof SONOS_ROOM_TO_ENTITY;
export type SonosEntityId = (typeof SONOS_ROOM_TO_ENTITY)[SonosRoomName];

const roomNames = Object.keys(SONOS_ROOM_TO_ENTITY) as SonosRoomName[];

export const SONOS_ROOM_NAMES: readonly SonosRoomName[] = Object.freeze(roomNames);
export const SONOS_ENTITY_IDS: readonly SonosEntityId[] = Object.freeze(
  roomNames.map(roomName => SONOS_ROOM_TO_ENTITY[roomName])
);

const entityToRoom = new Map<string, SonosRoomName>(
  roomNames.map(roomName => [SONOS_ROOM_TO_ENTITY[roomName], roomName])
);

export const isSonosRoomName = (value: unknown): value is SonosRoomName => {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(
    SONOS_ROOM_TO_ENTITY,
    value
  );
};

export const requireSonosRoomName = (value: unknown): SonosRoomName => {
  if (!isSonosRoomName(value)) {
    throw new Error(`Unknown Sonos room: ${String(value)}`);
  }
  return value;
};

export const roomForSonosEntity = (entityId: string): SonosRoomName | undefined => {
  return entityToRoom.get(entityId);
};

export const requireRoomForSonosEntity = (entityId: string): SonosRoomName => {
  const roomName = roomForSonosEntity(entityId);
  if (!roomName) {
    throw new Error(`Unknown Sonos entity: ${entityId}`);
  }
  return roomName;
};
