export interface ShadowMemberLike {
  roomName: string;
  state?: {
    volume?: number;
    playbackState?: string;
    currentTrack?: {
      title?: string;
      artist?: string;
      album?: string;
      stationName?: string;
    };
  };
}

export interface ShadowZoneLike {
  coordinator: ShadowMemberLike;
  members: ShadowMemberLike[];
}

export type SonosShadowDifferenceKind =
  | 'missing_room'
  | 'topology'
  | 'coordinator'
  | 'volume'
  | 'playback'
  | 'metadata';

export interface SonosShadowDifference {
  kind: SonosShadowDifferenceKind;
  roomName: string;
  field?: string;
  nodeValue: unknown;
  homeAssistantValue: unknown;
}

export interface SonosShadowComparison {
  equal: boolean;
  differences: SonosShadowDifference[];
}

export interface SonosShadowCompareOptions {
  volumeTolerance?: number;
}

export interface SonosShadowPersistenceAssessment {
  persistentDifferences: SonosShadowDifference[];
  newlyPersistentDifferences: SonosShadowDifference[];
  oldestPersistentAgeMs: number;
}

export interface SonosShadowPersistenceTrackerOptions {
  graceMs?: number;
  now?: () => number;
}

interface NormalizedRoom {
  coordinator: string;
  members: string[];
  state: ShadowMemberLike['state'];
}

const normalize = (zones: readonly ShadowZoneLike[]): Map<string, NormalizedRoom> => {
  const rooms = new Map<string, NormalizedRoom>();
  for (const zone of zones) {
    const coordinator = zone.coordinator?.roomName || '';
    const members = zone.members.map(member => member.roomName).sort();
    for (const member of zone.members) {
      rooms.set(member.roomName, {
        coordinator,
        members,
        state: member.state,
      });
    }
  }
  return rooms;
};

const metadataFields = ['title', 'artist', 'album', 'stationName'] as const;

const normalizedMetadata = (
  state: ShadowMemberLike['state']
): Record<(typeof metadataFields)[number], string> => {
  const track = state?.currentTrack;
  const normalized = {
    title: track?.title || '',
    artist: track?.artist || '',
    album: track?.album || '',
    stationName: track?.stationName || '',
  };
  if (!normalized.title.startsWith('TYPE=')) {
    return normalized;
  }
  const fields = new Map<string, string>();
  for (const segment of normalized.title.split('|')) {
    const separator = segment.search(/[= ]/);
    if (separator <= 0) {
      continue;
    }
    fields.set(segment.slice(0, separator), segment.slice(separator + 1).trim());
  }
  if (!fields.has('TYPE') || !fields.has('TITLE')) {
    return normalized;
  }
  return {
    ...normalized,
    title: fields.get('TITLE') || normalized.title,
    artist: fields.get('ARTIST') || normalized.artist,
    album: fields.get('ALBUM') || normalized.album,
  };
};

const differenceIdentity = (difference: SonosShadowDifference): string => [
  difference.kind,
  difference.roomName,
  difference.field || '',
].join('|');

/**
 * Tracks semantic differences across consecutive observations. Values are not
 * part of the identity: a volume mismatch remains the same mismatch while the
 * two backends converge, until it either clears or reaches the grace period.
 */
export class SonosShadowPersistenceTracker {
  private readonly graceMs: number;
  private readonly now: () => number;
  private readonly observed = new Map<string, {firstSeenAt: number; emitted: boolean}>();

  constructor(options: SonosShadowPersistenceTrackerOptions = {}) {
    this.graceMs = options.graceMs ?? 5_000;
    this.now = options.now ?? Date.now;
  }

  observe(differences: readonly SonosShadowDifference[]): SonosShadowPersistenceAssessment {
    const observedAt = this.now();
    const activeIdentities = new Set(differences.map(differenceIdentity));

    for (const identity of this.observed.keys()) {
      if (!activeIdentities.has(identity)) {
        this.observed.delete(identity);
      }
    }

    const persistentDifferences: SonosShadowDifference[] = [];
    const newlyPersistentDifferences: SonosShadowDifference[] = [];
    let oldestPersistentAgeMs = 0;

    for (const difference of differences) {
      const identity = differenceIdentity(difference);
      let observation = this.observed.get(identity);
      if (!observation) {
        observation = {firstSeenAt: observedAt, emitted: false};
        this.observed.set(identity, observation);
      }

      const ageMs = Math.max(0, observedAt - observation.firstSeenAt);
      if (ageMs < this.graceMs) {
        continue;
      }

      persistentDifferences.push(difference);
      oldestPersistentAgeMs = Math.max(oldestPersistentAgeMs, ageMs);
      if (!observation.emitted) {
        observation.emitted = true;
        newlyPersistentDifferences.push(difference);
      }
    }

    return {
      persistentDifferences,
      newlyPersistentDifferences,
      oldestPersistentAgeMs,
    };
  }
}

export const compareSonosBackends = (
  nodeZones: readonly ShadowZoneLike[],
  homeAssistantZones: readonly ShadowZoneLike[],
  options: SonosShadowCompareOptions = {}
): SonosShadowComparison => {
  const volumeTolerance = options.volumeTolerance ?? 1;
  const nodeRooms = normalize(nodeZones);
  const haRooms = normalize(homeAssistantZones);
  const roomNames = [...new Set([...nodeRooms.keys(), ...haRooms.keys()])].sort();
  const differences: SonosShadowDifference[] = [];

  for (const roomName of roomNames) {
    const nodeRoom = nodeRooms.get(roomName);
    const haRoom = haRooms.get(roomName);
    if (!nodeRoom || !haRoom) {
      differences.push({
        kind: 'missing_room',
        roomName,
        nodeValue: Boolean(nodeRoom),
        homeAssistantValue: Boolean(haRoom),
      });
      continue;
    }
    if (nodeRoom.coordinator !== haRoom.coordinator) {
      differences.push({
        kind: 'coordinator',
        roomName,
        nodeValue: nodeRoom.coordinator,
        homeAssistantValue: haRoom.coordinator,
      });
    }
    if (nodeRoom.members.join('|') !== haRoom.members.join('|')) {
      differences.push({
        kind: 'topology',
        roomName,
        nodeValue: nodeRoom.members,
        homeAssistantValue: haRoom.members,
      });
    }

    const nodeVolume = Number(nodeRoom.state?.volume);
    const haVolume = Number(haRoom.state?.volume);
    if (
      Number.isFinite(nodeVolume) &&
      Number.isFinite(haVolume) &&
      Math.abs(nodeVolume - haVolume) > volumeTolerance
    ) {
      differences.push({
        kind: 'volume',
        roomName,
        nodeValue: nodeVolume,
        homeAssistantValue: haVolume,
      });
    }

    const nodePlayback = nodeRoom.state?.playbackState || '';
    const haPlayback = haRoom.state?.playbackState || '';
    if (nodePlayback !== haPlayback) {
      differences.push({
        kind: 'playback',
        roomName,
        nodeValue: nodePlayback,
        homeAssistantValue: haPlayback,
      });
    }

    const nodeMetadata = normalizedMetadata(nodeRoom.state);
    const homeAssistantMetadata = normalizedMetadata(haRoom.state);
    for (const field of metadataFields) {
      const nodeValue = nodeMetadata[field];
      const homeAssistantValue = homeAssistantMetadata[field];
      if (nodeValue !== homeAssistantValue) {
        differences.push({
          kind: 'metadata',
          roomName,
          field,
          nodeValue,
          homeAssistantValue,
        });
      }
    }
  }

  return {equal: differences.length === 0, differences};
};
