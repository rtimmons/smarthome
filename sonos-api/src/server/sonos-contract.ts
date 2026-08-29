import type {HomeAssistantEntityState} from './home-assistant-client';
import type {SonosRoomName} from './sonos-room-map';

export type SonosFreshness = 'live' | 'stale' | 'unknown';

export interface SonosStateSnapshot {
  freshness: SonosFreshness;
  connected: boolean;
  observedAt: number | null;
  ageMs: number;
  entities: ReadonlyMap<string, HomeAssistantEntityState>;
  lastError?: string;
}

export interface LegacySonosTrack {
  artist: string;
  title: string;
  album: string;
  albumArtUri: string;
  absoluteAlbumArtUri?: string;
  duration: number;
  uri: string;
  trackUri?: string;
  type?: string;
  stationName?: string;
}

export interface LegacySonosState {
  volume: number;
  mute: boolean;
  equalizer: {
    bass: number;
    treble: number;
    loudness: boolean;
  };
  currentTrack: LegacySonosTrack;
  nextTrack: LegacySonosTrack;
  trackNo: number;
  elapsedTime: number;
  elapsedTimeFormatted: string;
  playbackState: 'PLAYING' | 'PAUSED_PLAYBACK' | 'STOPPED';
  playMode: {
    repeat: 'none' | 'one' | 'all';
    shuffle: boolean;
    crossfade: boolean;
  };
  sub: {
    gain: number;
    crossover: number;
    polarity: number;
    enabled: boolean;
  };
}

export interface LegacySonosMember {
  uuid: string;
  roomName: SonosRoomName;
  coordinator: SonosRoomName;
  state: LegacySonosState;
  groupState: {
    volume: number;
    mute: boolean;
  };
}

export interface LegacySonosZone {
  uuid: string;
  coordinator: LegacySonosMember;
  members: LegacySonosMember[];
}

export type SonosOperationKind = 'join' | 'leave' | 'join_all' | 'preset';
export type SonosOperationStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'timed_out'
  | 'cancelled'
  | 'superseded';

export interface SonosOperation {
  id: string;
  kind: SonosOperationKind;
  key: string;
  status: SonosOperationStatus;
  targetRoom?: SonosRoomName;
  requestedRooms: SonosRoomName[];
  unavailableRooms: SonosRoomName[];
  serviceCallCount: number;
  createdAt: number;
  deadlineAt: number;
  startedAt?: number;
  finishedAt?: number;
  error?: string;
  failedStep?: string;
  observedTopology?: Array<{
    coordinator: SonosRoomName;
    members: SonosRoomName[];
  }>;
}

export class SonosBackendError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly retryable: boolean;

  constructor(
    code: string,
    message: string,
    statusCode = 502,
    retryable = false
  ) {
    super(message);
    this.name = 'SonosBackendError';
    this.code = code;
    this.statusCode = statusCode;
    this.retryable = retryable;
  }
}
