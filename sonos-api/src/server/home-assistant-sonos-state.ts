import {HomeAssistantEntityState} from './home-assistant-client';
import {
  LegacySonosMember,
  LegacySonosState,
  LegacySonosZone,
  SonosBackendError,
  SonosStateSnapshot,
} from './sonos-contract';
import {
  roomForSonosEntity,
  SONOS_ENTITY_IDS,
  SONOS_ROOM_TO_ENTITY,
  SonosRoomName,
} from './sonos-room-map';

export interface CanonicalSonosTopology {
  zones: LegacySonosZone[];
  unknownRooms: SonosRoomName[];
}

export interface StateProjectionOptions {
  now?: () => number;
  artworkPath?: (
    roomName: SonosRoomName,
    revision: string
  ) => string;
}

export class SonosProjectionError extends SonosBackendError {
  constructor(message: string) {
    super('invalid_topology', message, 502, true);
    this.name = 'SonosProjectionError';
  }
}

const stringAttribute = (
  state: HomeAssistantEntityState,
  name: string
): string => {
  const value = state.attributes[name];
  return typeof value === 'string' ? value : '';
};

const numberAttribute = (
  state: HomeAssistantEntityState,
  name: string
): number => {
  const value = Number(state.attributes[name]);
  return Number.isFinite(value) ? value : 0;
};

const booleanAttribute = (
  state: HomeAssistantEntityState,
  name: string
): boolean => state.attributes[name] === true;

const volumePercent = (state: HomeAssistantEntityState): number => {
  return Math.max(0, Math.min(100, Math.round(numberAttribute(state, 'volume_level') * 100)));
};

const formatElapsed = (elapsed: number): string => {
  const seconds = Math.max(0, Math.floor(elapsed));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  const minuteText = hours > 0 ? String(minutes).padStart(2, '0') : String(minutes);
  return `${hours > 0 ? `${hours}:` : ''}${minuteText}:${String(remainder).padStart(2, '0')}`;
};

const playbackState = (
  state: HomeAssistantEntityState
): LegacySonosState['playbackState'] => {
  if (state.state === 'playing') {
    return 'PLAYING';
  }
  if (state.state === 'paused') {
    // The deployed node API reports STOPPED after pausing live radio, even
    // though Home Assistant represents that transport state as paused. It
    // retains PAUSED_PLAYBACK for paused on-demand media.
    return stringAttribute(state, 'media_channel') ? 'STOPPED' : 'PAUSED_PLAYBACK';
  }
  return 'STOPPED';
};

const elapsedTime = (state: HomeAssistantEntityState, now: number): number => {
  let position = Math.max(0, numberAttribute(state, 'media_position'));
  if (state.state === 'playing') {
    const updatedAt = Date.parse(stringAttribute(state, 'media_position_updated_at'));
    if (Number.isFinite(updatedAt)) {
      position += Math.max(0, (now - updatedAt) / 1000);
    }
  }
  const duration = numberAttribute(state, 'media_duration');
  return duration > 0 ? Math.min(duration, position) : position;
};

const emptyTrack = () => ({
  artist: '',
  title: '',
  album: '',
  albumArtUri: '',
  duration: 0,
  uri: '',
});

/**
 * Keep the node API's legacy source-family discriminator. Home Assistant
 * reports radio, TV, line-in, and Apple Music as media_content_type "music";
 * the URI is the stable discriminator available to the compatibility layer.
 */
const legacyTrackType = (uri: string, source: string): string => {
  if (!uri && !source) {
    return '';
  }
  if (
    uri.startsWith('x-sonosapi-stream:') ||
    uri.startsWith('x-sonosapi-radio:') ||
    uri.startsWith('pndrradio:') ||
    uri.startsWith('x-sonosapi-hls:') ||
    uri.startsWith('x-sonosprog-http:') ||
    uri.startsWith('x-rincon-mp3radio:')
  ) {
    return 'radio';
  }
  if (
    uri.startsWith('x-rincon-stream:') ||
    uri.startsWith('x-sonos-htastream:') ||
    source === 'Line-in' ||
    source === 'TV'
  ) {
    return 'line_in';
  }
  return 'track';
};

export const projectLegacySonosState = (
  memberState: HomeAssistantEntityState,
  coordinatorState: HomeAssistantEntityState = memberState,
  roomName: SonosRoomName = roomForSonosEntity(memberState.entity_id) as SonosRoomName,
  options: StateProjectionOptions = {}
): LegacySonosState => {
  if (!roomName) {
    throw new SonosProjectionError(`Cannot project unknown entity ${memberState.entity_id}`);
  }
  const now = (options.now || Date.now)();
  const elapsed = elapsedTime(coordinatorState, now);
  const revision = coordinatorState.last_updated || coordinatorState.last_changed;
  const artworkPath = (options.artworkPath || ((room, value) =>
    `./sonos/${encodeURIComponent(room)}/artwork?v=${encodeURIComponent(value)}`))(
      roomName,
      revision
    );
  const uri = stringAttribute(coordinatorState, 'media_content_id');
  const stationName = stringAttribute(coordinatorState, 'media_channel');
  const source = stringAttribute(coordinatorState, 'source');
  const artist = stringAttribute(coordinatorState, 'media_artist') || stationName;

  return {
    volume: volumePercent(memberState),
    mute: booleanAttribute(memberState, 'is_volume_muted'),
    equalizer: {bass: 0, treble: 0, loudness: false},
    currentTrack: {
      artist,
      title: stringAttribute(coordinatorState, 'media_title'),
      album: stringAttribute(coordinatorState, 'media_album_name'),
      albumArtUri: artworkPath,
      absoluteAlbumArtUri: artworkPath,
      duration: numberAttribute(coordinatorState, 'media_duration'),
      uri,
      trackUri: uri,
      type: legacyTrackType(uri, source),
      stationName,
    },
    nextTrack: emptyTrack(),
    trackNo: 0,
    elapsedTime: elapsed,
    elapsedTimeFormatted: formatElapsed(elapsed),
    playbackState: playbackState(coordinatorState),
    playMode: {repeat: 'none', shuffle: false, crossfade: false},
    sub: {gain: 0, crossover: 0, polarity: 0, enabled: false},
  };
};

const groupMembers = (state: HomeAssistantEntityState): string[] | null => {
  const value = state.attributes.group_members;
  if (!Array.isArray(value) || value.length === 0) {
    return null;
  }
  if (value.some(member => typeof member !== 'string')) {
    throw new SonosProjectionError(`Malformed group_members for ${state.entity_id}`);
  }
  return value as string[];
};

const unique = (values: readonly string[]): boolean => new Set(values).size === values.length;

export const projectCanonicalSonosTopology = (
  snapshot: SonosStateSnapshot,
  options: StateProjectionOptions = {}
): CanonicalSonosTopology => {
  if (snapshot.freshness === 'unknown') {
    throw new SonosBackendError(
      'state_unavailable',
      'Home Assistant Sonos topology is unknown',
      503,
      true
    );
  }

  const groups = new Map<string, {coordinatorId: string; memberIds: string[]} >();
  const unknownRooms = new Set<SonosRoomName>();
  const unknownEntityIds = new Set<string>();

  for (const entityId of SONOS_ENTITY_IDS) {
    const state = snapshot.entities.get(entityId);
    const roomName = roomForSonosEntity(entityId) as SonosRoomName;
    if (!state || state.state === 'unavailable' || state.state === 'unknown') {
      unknownRooms.add(roomName);
      unknownEntityIds.add(entityId);
    }
  }

  for (const entityId of SONOS_ENTITY_IDS) {
    const state = snapshot.entities.get(entityId);
    if (!state || unknownEntityIds.has(entityId)) {
      continue;
    }
    const members = groupMembers(state);
    if (!members) {
      throw new SonosProjectionError(`Missing group_members for ${entityId}`);
    }
    if (!unique(members) || !members.includes(entityId)) {
      throw new SonosProjectionError(`Invalid group membership for ${entityId}`);
    }
    for (const member of members) {
      if (!roomForSonosEntity(member)) {
        throw new SonosProjectionError(`Unknown entity ${member} in Sonos group`);
      }
    }

    // Home Assistant can retain an unavailable player in the reachable
    // speakers' group_members list. Project the reachable subset so one
    // offline room does not make every healthy zone unusable.
    const reachableMembers = members.filter(member => !unknownEntityIds.has(member));
    const coordinatorId = reachableMembers[0];
    const sortedSet = [...reachableMembers].sort();
    const key = sortedSet.join('|');
    const existing = groups.get(key);
    if (existing && existing.coordinatorId !== coordinatorId) {
      throw new SonosProjectionError(`Conflicting coordinators for group ${key}`);
    }
    groups.set(key, {coordinatorId, memberIds: sortedSet});
  }

  const claimedMembers = new Map<string, string>();
  for (const [key, group] of groups) {
    for (const memberId of group.memberIds) {
      const prior = claimedMembers.get(memberId);
      if (prior && prior !== key) {
        throw new SonosProjectionError(`Entity ${memberId} appears in multiple groups`);
      }
      claimedMembers.set(memberId, key);
    }
  }

  const zones = [...groups.values()].map(group => {
    const coordinatorRoom = roomForSonosEntity(group.coordinatorId);
    const coordinatorState = snapshot.entities.get(group.coordinatorId);
    if (!coordinatorRoom || !coordinatorState) {
      throw new SonosProjectionError(`Missing coordinator ${group.coordinatorId}`);
    }
    const orderedMemberIds = [
      group.coordinatorId,
      ...group.memberIds
        .filter(memberId => memberId !== group.coordinatorId)
        .sort((left, right) => {
          return String(roomForSonosEntity(left)).localeCompare(String(roomForSonosEntity(right)));
        }),
    ];
    const members: LegacySonosMember[] = orderedMemberIds.map(memberId => {
      const roomName = roomForSonosEntity(memberId);
      const memberState = snapshot.entities.get(memberId);
      if (!roomName || !memberState) {
        throw new SonosProjectionError(`Missing state for grouped entity ${memberId}`);
      }
      const state = projectLegacySonosState(
        memberState,
        coordinatorState,
        roomName,
        options
      );
      return {
        uuid: memberId,
        roomName,
        coordinator: coordinatorRoom,
        state,
        groupState: {
          volume: volumePercent(coordinatorState),
          mute: booleanAttribute(coordinatorState, 'is_volume_muted'),
        },
      };
    });
    return {
      uuid: `ha:${group.coordinatorId}`,
      coordinator: members[0],
      members,
    };
  });

  zones.sort((left, right) =>
    left.coordinator.roomName.localeCompare(right.coordinator.roomName)
  );
  return {
    zones,
    unknownRooms: [...unknownRooms].sort(),
  };
};

export const projectRoomState = (
  snapshot: SonosStateSnapshot,
  roomName: SonosRoomName,
  options: StateProjectionOptions = {}
): LegacySonosState => {
  if (snapshot.freshness === 'unknown') {
    throw new SonosBackendError('state_unavailable', 'Sonos state is unknown', 503, true);
  }
  const entityId = SONOS_ROOM_TO_ENTITY[roomName];
  const memberState = snapshot.entities.get(entityId);
  if (!memberState || memberState.state === 'unknown' || memberState.state === 'unavailable') {
    throw new SonosBackendError(
      'room_unavailable',
      `Sonos room ${roomName} is unavailable`,
      503,
      true
    );
  }
  const members = groupMembers(memberState);
  if (!members) {
    throw new SonosProjectionError(`Missing group_members for ${entityId}`);
  }
  if (!unique(members) || !members.includes(entityId)) {
    throw new SonosProjectionError(`Invalid group membership for ${entityId}`);
  }
  if (members.some(member => !roomForSonosEntity(member))) {
    throw new SonosProjectionError(`Unknown entity in Sonos group for ${roomName}`);
  }
  const coordinatorState = snapshot.entities.get(members[0]);
  if (
    !coordinatorState ||
    !roomForSonosEntity(members[0]) ||
    coordinatorState.state === 'unknown' ||
    coordinatorState.state === 'unavailable'
  ) {
    throw new SonosProjectionError(`Missing coordinator state for ${roomName}`);
  }
  const coordinatorMembers = groupMembers(coordinatorState);
  if (
    !coordinatorMembers ||
    coordinatorMembers[0] !== members[0] ||
    coordinatorMembers.length !== members.length ||
    [...coordinatorMembers].sort().join('|') !== [...members].sort().join('|')
  ) {
    throw new SonosProjectionError(`Inconsistent coordinator group for ${roomName}`);
  }
  return projectLegacySonosState(memberState, coordinatorState, roomName, options);
};

export const sonosFreshnessHeaders = (
  snapshot: SonosStateSnapshot
): Record<string, string> => ({
  'X-Sonos-Response-Source': 'home_assistant',
  'X-Sonos-Response-Stale': snapshot.freshness === 'live' ? 'false' : 'true',
  'X-Sonos-Observed-At': snapshot.observedAt === null
    ? ''
    : new Date(snapshot.observedAt).toISOString(),
  'X-Sonos-Age-Ms': Number.isFinite(snapshot.ageMs) ? String(snapshot.ageMs) : '',
});
