import {HomeAssistantBinaryResponse} from './home-assistant-client';
import {SonosBackendError, SonosStateSnapshot} from './sonos-contract';
import {
  roomForSonosEntity,
  SONOS_ROOM_TO_ENTITY,
  SonosRoomName,
} from './sonos-room-map';

export interface SonosArtworkFetcher {
  fetchAuthenticatedPath(path: string): Promise<HomeAssistantBinaryResponse>;
}

export interface SonosArtworkOptions {
  maxBytes?: number;
  allowedContentTypes?: readonly string[];
}

export interface SonosArtwork {
  contentType: string;
  body: Uint8Array;
  cacheControl: string;
}

export const DEFAULT_ARTWORK_MAX_BYTES = 5 * 1024 * 1024;
const DEFAULT_CONTENT_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
] as const;

const tooLarge = (): SonosBackendError => new SonosBackendError(
  'artwork_too_large',
  'Sonos artwork is too large',
  502
);

const artworkFetchFailed = (): SonosBackendError => new SonosBackendError(
  'artwork_fetch_failed',
  'Home Assistant artwork request failed',
  502,
  true
);

const cancelBody = async (
  body: ReadableStream<Uint8Array> | null
): Promise<void> => {
  if (!body) return;
  try {
    await body.cancel('Sonos artwork exceeds configured byte limit');
  } catch (_error) {
    // Preserve the size error even if the upstream stream cannot be cancelled.
  }
};

const readBoundedBody = async (
  body: ReadableStream<Uint8Array> | null,
  maxBytes: number
): Promise<Uint8Array> => {
  if (!body) return new Uint8Array(0);

  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let totalBytes = 0;
  try {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      if (!value || value.byteLength === 0) continue;
      if (totalBytes + value.byteLength > maxBytes) {
        try {
          await reader.cancel('Sonos artwork exceeds configured byte limit');
        } catch (_error) {
          // Preserve the size error even if the upstream stream cannot be cancelled.
        }
        throw tooLarge();
      }
      chunks.push(value);
      totalBytes += value.byteLength;
    }
  } finally {
    reader.releaseLock();
  }

  const result = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
};

export const resolveSonosArtworkOwner = (
  snapshot: SonosStateSnapshot,
  roomName: SonosRoomName
): SonosRoomName => {
  if (snapshot.freshness === 'unknown') {
    throw new SonosBackendError('state_unavailable', 'Sonos artwork state is unknown', 503, true);
  }
  const requestedEntityId = SONOS_ROOM_TO_ENTITY[roomName];
  const requestedState = snapshot.entities.get(requestedEntityId);
  if (
    !requestedState ||
    requestedState.state === 'unknown' ||
    requestedState.state === 'unavailable'
  ) {
    throw new SonosBackendError(
      'room_unavailable',
      `Sonos room ${roomName} is unavailable`,
      503,
      true
    );
  }
  const members = requestedState.attributes.group_members;
  if (
    !Array.isArray(members) ||
    members.length === 0 ||
    members.some(member => typeof member !== 'string') ||
    !members.includes(requestedEntityId) ||
    new Set(members).size !== members.length ||
    members.some(member => typeof member === 'string' && !roomForSonosEntity(member))
  ) {
    throw new SonosBackendError(
      'invalid_topology',
      `Sonos room ${roomName} has no authoritative artwork coordinator`,
      502,
      true
    );
  }
  const coordinatorRoom = roomForSonosEntity(members[0]);
  const coordinatorState = coordinatorRoom
    ? snapshot.entities.get(SONOS_ROOM_TO_ENTITY[coordinatorRoom])
    : undefined;
  if (!coordinatorRoom || !coordinatorState) {
    throw new SonosBackendError(
      'invalid_topology',
      `Sonos room ${roomName} has an unknown artwork coordinator`,
      502,
      true
    );
  }
  if (coordinatorState.state === 'unknown' || coordinatorState.state === 'unavailable') {
    throw new SonosBackendError(
      'room_unavailable',
      `Sonos artwork coordinator ${coordinatorRoom} is unavailable`,
      503,
      true
    );
  }
  const coordinatorMembers = coordinatorState.attributes.group_members;
  if (
    !Array.isArray(coordinatorMembers) ||
    coordinatorMembers.length !== members.length ||
    coordinatorMembers[0] !== members[0] ||
    coordinatorMembers.some(member =>
      typeof member !== 'string' || !members.includes(member)
    )
  ) {
    throw new SonosBackendError(
      'invalid_topology',
      `Sonos room ${roomName} has inconsistent artwork ownership`,
      502,
      true
    );
  }
  return coordinatorRoom;
};

const validatedPicturePath = (
  snapshot: SonosStateSnapshot,
  requestedRoom: SonosRoomName
): string => {
  const ownerRoom = resolveSonosArtworkOwner(snapshot, requestedRoom);
  const entityId = SONOS_ROOM_TO_ENTITY[ownerRoom];
  const state = snapshot.entities.get(entityId);
  const picture = state?.attributes.entity_picture;
  if (typeof picture !== 'string' || !picture) {
    throw new SonosBackendError(
      'artwork_missing',
      `No artwork is available for ${requestedRoom}`,
      404
    );
  }
  if (!picture.startsWith('/') || picture.startsWith('//')) {
    throw new SonosBackendError('invalid_artwork', 'Home Assistant artwork path is invalid', 502);
  }

  const rawPath = picture.split(/[?#]/, 1)[0];
  if (rawPath.includes('\\')) {
    throw new SonosBackendError('invalid_artwork', 'Home Assistant artwork path is invalid', 502);
  }
  for (const segment of rawPath.split('/')) {
    let decoded: string;
    try {
      decoded = decodeURIComponent(segment);
    } catch (_error) {
      throw new SonosBackendError('invalid_artwork', 'Home Assistant artwork path is invalid', 502);
    }
    if (decoded === '.' || decoded === '..') {
      throw new SonosBackendError('invalid_artwork', 'Home Assistant artwork path is invalid', 502);
    }
  }

  let parsed: URL;
  try {
    parsed = new URL(picture, 'http://homeassistant.invalid');
  } catch (_error) {
    throw new SonosBackendError('invalid_artwork', 'Home Assistant artwork path is invalid', 502);
  }
  if (
    parsed.origin !== 'http://homeassistant.invalid' ||
    !parsed.pathname.startsWith('/api/media_player_proxy/') ||
    parsed.username ||
    parsed.password
  ) {
    throw new SonosBackendError('invalid_artwork', 'Home Assistant artwork path is not allowed', 502);
  }

  const expectedPath = `/api/media_player_proxy/${entityId}`;
  if (parsed.pathname !== expectedPath) {
    throw new SonosBackendError(
      'invalid_artwork',
      'Home Assistant artwork path does not match the observed coordinator',
      502
    );
  }
  return `${parsed.pathname}${parsed.search}`;
};

export const fetchSonosArtwork = async (
  fetcher: SonosArtworkFetcher,
  snapshot: SonosStateSnapshot,
  roomName: SonosRoomName,
  options: SonosArtworkOptions = {}
): Promise<SonosArtwork> => {
  const maxBytes = options.maxBytes ?? DEFAULT_ARTWORK_MAX_BYTES;
  const allowedContentTypes = new Set(
    options.allowedContentTypes || DEFAULT_CONTENT_TYPES
  );
  const path = validatedPicturePath(snapshot, roomName);
  let response: HomeAssistantBinaryResponse;
  try {
    response = await fetcher.fetchAuthenticatedPath(path);
  } catch (_error) {
    throw artworkFetchFailed();
  }
  if (!response.ok) {
    await cancelBody(response.body);
    throw artworkFetchFailed();
  }
  const contentType = (response.headers.get('content-type') || '')
    .split(';', 1)[0]
    .trim()
    .toLowerCase();
  if (!allowedContentTypes.has(contentType)) {
    throw new SonosBackendError(
      'invalid_artwork_type',
      'Home Assistant artwork response was not an allowed image type',
      502
    );
  }
  const contentLength = Number(response.headers.get('content-length'));
  if (Number.isFinite(contentLength) && contentLength > maxBytes) {
    await cancelBody(response.body);
    throw tooLarge();
  }

  let buffer: Uint8Array;
  try {
    buffer = await readBoundedBody(response.body, maxBytes);
  } catch (error) {
    if (error instanceof SonosBackendError) {
      throw error;
    }
    throw artworkFetchFailed();
  }
  return {
    contentType,
    body: buffer,
    cacheControl: 'private, max-age=30',
  };
};
