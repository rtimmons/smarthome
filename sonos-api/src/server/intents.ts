import rpn = require('request-promise-native');

import '../types/sonos';

export type SonosIntentStatusValue =
  'running' |
  'completed' |
  'timed_out' |
  'failed' |
  'superseded' |
  'cancelled';

export interface GroupAllIntentRequest {
  targetRoom: string;
  roomNames: string[];
  requestedFromRoom?: string;
}

export interface GroupAllIntentStep {
  action: 'join';
  room: string;
  joiningToRoom: string;
  startedAt: string;
}

export interface GroupAllIntentError {
  message: string;
  at: string;
}

export interface GroupAllIntent {
  id: string;
  kind: 'group_all_to_room';
  status: SonosIntentStatusValue;
  targetRoom: string;
  roomNames: string[];
  requestedFromRoom?: string;
  createdAt: string;
  expiresAt: string;
  finishedAt?: string;
  coordinatorRoom?: string;
  joinedRooms: string[];
  missingRooms: string[];
  attemptCount: number;
  currentStep: GroupAllIntentStep | null;
  lastError: GroupAllIntentError | null;
  volumeSync?: {
    sourceRoom: string;
    targetVolume?: number;
  };
  message: string;
}

export interface SonosIntentStatusResponse {
  activeIntent: GroupAllIntent | null;
  recentIntent: GroupAllIntent | null;
  serverTime: string;
}

export interface SonosIntentStore {
  createGroupAllIntent(req: GroupAllIntentRequest): GroupAllIntent;
  getStatus(): SonosIntentStatusResponse;
  cancelActiveIntent(message: string): GroupAllIntent | null;
  enableVolumeSync(sourceRoom: string): GroupAllIntent | null;
  isTopologyMutationRoute(route: string): boolean;
}

interface SonosHttpClient {
  getZones(): Promise<Sonos.Zone[]>;
  joinRoom(roomName: string, coordinatorRoom: string): Promise<void>;
  getState(roomName: string): Promise<Sonos.State>;
  setVolume(roomName: string, volume: number): Promise<void>;
}

interface SonosIntentCoordinatorOptions {
  timeoutMs?: number;
  observeDelayMs?: number;
  terminalRetentionMs?: number;
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
}

const DEFAULT_TIMEOUT_MS = 45 * 1000;
const DEFAULT_OBSERVE_DELAY_MS = 500;
const DEFAULT_TERMINAL_RETENTION_MS = 1500;
const FAILURE_TERMINAL_RETENTION_MS = 1000;
const TOPOLOGY_ACTIONS = {
  add: true,
  isolate: true,
  join: true,
  leave: true,
  ungroup: true,
};

const cloneIntent = (intent: GroupAllIntent | null): GroupAllIntent | null => {
  if (!intent) {
    return null;
  }
  return JSON.parse(JSON.stringify(intent)) as GroupAllIntent;
};

const uniqueRoomNames = (rooms: string[]): string[] => {
  const seen: {[key: string]: boolean} = {};
  const result: string[] = [];

  rooms.forEach(room => {
    if (seen[room]) {
      return;
    }
    seen[room] = true;
    result.push(room);
  });

  return result;
};

const isoNow = (now: () => number): string => new Date(now()).toISOString();

const makeIntentId = (now: () => number): string => {
  return `igt_${now()}_${Math.random().toString(36).slice(2, 8)}`;
};

const formatJoinedProgress = (intent: GroupAllIntent): string => {
  return `${intent.joinedRooms.length}/${intent.roomNames.length}`;
};

const zoneForRoom = (
  zones: Sonos.Zone[],
  roomName: string
): Sonos.Zone | undefined => {
  return zones.find(zone =>
    zone.members.some(member => member.roomName === roomName)
  );
};

const joinedRoomsForZone = (
  roomNames: string[],
  zone: Sonos.Zone | undefined
): string[] => {
  if (!zone) {
    return [];
  }

  const members = zone.members.map(member => member.roomName);
  return roomNames.filter(roomName => members.indexOf(roomName) >= 0);
};

const missingRoomsForZone = (
  roomNames: string[],
  joinedRooms: string[]
): string[] => {
  return roomNames.filter(roomName => joinedRooms.indexOf(roomName) < 0);
};

const buildRunningMessage = (intent: GroupAllIntent): string => {
  if (intent.missingRooms.length === 0) {
    return `Joined all to ${intent.targetRoom} (${formatJoinedProgress(intent)})`;
  }
  return `Joining all to ${intent.targetRoom} (${formatJoinedProgress(intent)})`;
};

const buildTimedOutMessage = (intent: GroupAllIntent): string => {
  if (intent.missingRooms.length === 0) {
    return `Join-all to ${intent.targetRoom} timed out after convergence`;
  }
  return `Join-all to ${intent.targetRoom} timed out; missing ${intent.missingRooms.join(', ')}`;
};

export class SonosIntentCoordinator implements SonosIntentStore {
  private readonly client: SonosHttpClient;
  private readonly timeoutMs: number;
  private readonly observeDelayMs: number;
  private readonly terminalRetentionMs: number;
  private readonly now: () => number;
  private readonly sleep: (ms: number) => Promise<void>;
  private activeIntent: GroupAllIntent | null = null;
  private recentIntent: GroupAllIntent | null = null;
  private recentIntentTimer: NodeJS.Timeout | null = null;

  constructor(
    client: SonosHttpClient,
    options: SonosIntentCoordinatorOptions = {}
  ) {
    this.client = client;
    this.timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
    this.observeDelayMs = options.observeDelayMs || DEFAULT_OBSERVE_DELAY_MS;
    this.terminalRetentionMs = options.terminalRetentionMs || DEFAULT_TERMINAL_RETENTION_MS;
    this.now = options.now || (() => Date.now());
    this.sleep = options.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  }

  createGroupAllIntent(req: GroupAllIntentRequest): GroupAllIntent {
    const validated = this.validateRequest(req);
    const activeIntent = this.activeIntent;

    if (activeIntent && activeIntent.targetRoom === validated.targetRoom) {
      return cloneIntent(activeIntent) as GroupAllIntent;
    }

    if (activeIntent) {
      this.finishIntent(
        activeIntent,
        'superseded',
        `Join-all to ${activeIntent.targetRoom} superseded by ${validated.targetRoom}`
      );
    }

    const now = this.now();
    const intent: GroupAllIntent = {
      id: makeIntentId(this.now),
      kind: 'group_all_to_room',
      status: 'running',
      targetRoom: validated.targetRoom,
      roomNames: validated.roomNames,
      requestedFromRoom: validated.requestedFromRoom,
      createdAt: new Date(now).toISOString(),
      expiresAt: new Date(now + this.timeoutMs).toISOString(),
      joinedRooms: [],
      missingRooms: validated.roomNames.slice(),
      attemptCount: 0,
      currentStep: null,
      lastError: null,
      message: `Joining all to ${validated.targetRoom} (0/${validated.roomNames.length})`,
    };

    this.activeIntent = intent;
    console.log(
      `[sonos-intents] started ${intent.id} target=${intent.targetRoom} requestedFrom=${intent.requestedFromRoom || 'unknown'}`
    );

    this.runIntent(intent).catch(err => {
      if (this.activeIntent !== intent) {
        return;
      }

      const message = err instanceof Error ? err.message : 'Unknown intent failure';
      this.finishIntent(
        intent,
        'failed',
        `Join-all to ${intent.targetRoom} failed: ${message}`,
        message
      );
    });

    return cloneIntent(intent) as GroupAllIntent;
  }

  getStatus(): SonosIntentStatusResponse {
    return {
      activeIntent: cloneIntent(this.activeIntent),
      recentIntent: cloneIntent(this.recentIntent),
      serverTime: isoNow(this.now),
    };
  }

  cancelActiveIntent(message: string): GroupAllIntent | null {
    if (!this.activeIntent) {
      return null;
    }

    const cancelled = this.activeIntent;
    this.finishIntent(cancelled, 'cancelled', message);
    return cloneIntent(cancelled);
  }

  enableVolumeSync(sourceRoom: string): GroupAllIntent | null {
    if (!this.activeIntent) {
      return null;
    }

    this.activeIntent.volumeSync = {
      sourceRoom,
      targetVolume: this.activeIntent.volumeSync &&
          this.activeIntent.volumeSync.sourceRoom === sourceRoom
        ? this.activeIntent.volumeSync.targetVolume
        : undefined,
    };
    console.log(
      `[sonos-intents] ${this.activeIntent.id} volume-sync enabled source=${sourceRoom}`
    );
    return cloneIntent(this.activeIntent);
  }

  isTopologyMutationRoute(route: string): boolean {
    const trimmed = route.replace(/^\/+/, '');
    const segments = trimmed.split('/').filter(Boolean);
    if (segments.length < 2) {
      return false;
    }

    const action = decodeURIComponent(segments[1]).toLowerCase();
    return Boolean((TOPOLOGY_ACTIONS as {[key: string]: boolean})[action]);
  }

  private validateRequest(req: GroupAllIntentRequest): GroupAllIntentRequest {
    const targetRoom = typeof req.targetRoom === 'string' ? req.targetRoom.trim() : '';
    const roomNames = Array.isArray(req.roomNames)
      ? uniqueRoomNames(
          req.roomNames
            .filter(roomName => typeof roomName === 'string')
            .map(roomName => roomName.trim())
            .filter(roomName => roomName.length > 0)
        )
      : [];

    if (!targetRoom) {
      throw new Error('targetRoom is required');
    }
    if (roomNames.length === 0) {
      throw new Error('roomNames must contain at least one room');
    }
    if (roomNames.indexOf(targetRoom) < 0) {
      throw new Error('targetRoom must be included in roomNames');
    }

    return {
      targetRoom,
      roomNames,
      requestedFromRoom:
        typeof req.requestedFromRoom === 'string' && req.requestedFromRoom.trim()
          ? req.requestedFromRoom.trim()
          : undefined,
    };
  }

  private async runIntent(intent: GroupAllIntent): Promise<void> {
    const startedAt = this.now();

    while (this.activeIntent === intent) {
      if (this.now() - startedAt >= this.timeoutMs) {
        this.finishIntent(intent, 'timed_out', buildTimedOutMessage(intent));
        return;
      }

      try {
        const zones = await this.client.getZones();
        if (this.activeIntent !== intent) {
          return;
        }

        const targetZone = zoneForRoom(zones, intent.targetRoom);
        intent.coordinatorRoom = targetZone && targetZone.coordinator
          ? targetZone.coordinator.roomName
          : undefined;
        intent.joinedRooms = joinedRoomsForZone(intent.roomNames, targetZone);
        intent.missingRooms = missingRoomsForZone(intent.roomNames, intent.joinedRooms);
        intent.currentStep = null;
        intent.message = buildRunningMessage(intent);

        await this.syncJoinedRoomVolumes(intent, targetZone);

        if (intent.missingRooms.length === 0) {
          this.finishIntent(
            intent,
            'completed',
            `Joined all to ${intent.targetRoom} (${formatJoinedProgress(intent)})`
          );
          return;
        }

        if (!intent.coordinatorRoom) {
          intent.lastError = {
            message: `Target room ${intent.targetRoom} is not present in Sonos zones`,
            at: isoNow(this.now),
          };
          await this.sleep(this.observeDelayMs);
          continue;
        }

        const roomsToJoin = intent.roomNames.filter(roomName =>
          intent.missingRooms.indexOf(roomName) >= 0
        );

        if (roomsToJoin.length === 0) {
          await this.sleep(this.observeDelayMs);
          continue;
        }

        intent.attemptCount += 1;
        intent.currentStep = {
          action: 'join',
          room: roomsToJoin[0],
          joiningToRoom: intent.coordinatorRoom,
          startedAt: isoNow(this.now),
        };
        intent.message =
          `Joining all to ${intent.targetRoom} (${formatJoinedProgress(intent)} joined; attempting ${roomsToJoin.length})`;

        console.log(
          `[sonos-intents] ${intent.id} joining ${roomsToJoin.join(', ')} -> ${intent.coordinatorRoom} attempt=${intent.attemptCount}`
        );

        const joinErrors: string[] = [];
        await Promise.all(
          roomsToJoin.map(async roomName => {
            try {
              await this.client.joinRoom(roomName, intent.coordinatorRoom as string);
            } catch (err) {
              const message = err instanceof Error ? err.message : 'Unknown Sonos join error';
              joinErrors.push(`${roomName}: ${message}`);
            }
          })
        );
        if (this.activeIntent !== intent) {
          return;
        }

        if (joinErrors.length > 0) {
          intent.lastError = {
            message: joinErrors.join('; '),
            at: isoNow(this.now),
          };
          intent.message =
            `Joining all to ${intent.targetRoom} (${formatJoinedProgress(intent)} joined; retrying ${intent.missingRooms.length} rooms)`;
          console.warn(`[sonos-intents] ${intent.id} join wave errors: ${joinErrors.join('; ')}`);
        } else {
          intent.lastError = null;
        }
      } catch (err) {
        if (this.activeIntent !== intent) {
          return;
        }

        const message = err instanceof Error ? err.message : 'Unknown Sonos error';
        intent.lastError = {
          message,
          at: isoNow(this.now),
        };
        intent.message =
          `Joining all to ${intent.targetRoom} (${formatJoinedProgress(intent)} joined; retrying after error)`;
        console.warn(`[sonos-intents] ${intent.id} error: ${message}`);
      }

      await this.sleep(this.observeDelayMs);
    }
  }

  private async syncJoinedRoomVolumes(
    intent: GroupAllIntent,
    targetZone: Sonos.Zone | undefined
  ): Promise<void> {
    if (!intent.volumeSync || !targetZone) {
      return;
    }

    const sourceRoom = intent.volumeSync.sourceRoom;
    let sourceVolume = 0;

    try {
      const sourceState = await this.client.getState(sourceRoom);
      sourceVolume = sourceState.volume;
      intent.volumeSync.targetVolume = sourceVolume;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown Sonos state error';
      intent.lastError = {
        message: `Volume sync source ${sourceRoom}: ${message}`,
        at: isoNow(this.now),
      };
      return;
    }

    const roomsToAdjust = targetZone.members.filter(member =>
      member.roomName !== sourceRoom &&
      member.state &&
      member.state.volume !== sourceVolume
    );

    if (roomsToAdjust.length === 0) {
      return;
    }

    await Promise.all(
      roomsToAdjust.map(async member => {
        try {
          await this.client.setVolume(member.roomName, sourceVolume);
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Unknown Sonos volume error';
          intent.lastError = {
            message: `Volume sync ${member.roomName}: ${message}`,
            at: isoNow(this.now),
          };
        }
      })
    );
  }

  private finishIntent(
    intent: GroupAllIntent,
    status: SonosIntentStatusValue,
    message: string,
    errorMessage?: string
  ): void {
    intent.status = status;
    intent.message = message;
    intent.finishedAt = isoNow(this.now);
    intent.currentStep = null;

    if (errorMessage) {
      intent.lastError = {
        message: errorMessage,
        at: isoNow(this.now),
      };
    }

    if (this.activeIntent === intent) {
      this.activeIntent = null;
    }

    this.setRecentIntent(intent);
    console.log(`[sonos-intents] ${intent.id} ${status}: ${message}`);
  }

  private setRecentIntent(intent: GroupAllIntent): void {
    this.recentIntent = cloneIntent(intent);

    if (this.recentIntentTimer) {
      clearTimeout(this.recentIntentTimer);
    }

    const recentIntentId = intent.id;
    const retentionMs =
      intent.status === 'failed' || intent.status === 'timed_out'
        ? FAILURE_TERMINAL_RETENTION_MS
        : this.terminalRetentionMs;
    this.recentIntentTimer = setTimeout(() => {
      if (this.recentIntent && this.recentIntent.id === recentIntentId) {
        this.recentIntent = null;
      }
    }, retentionMs);
  }
}

export const createSonosIntentCoordinator = (
  sonosBaseUrl: string,
  options: SonosIntentCoordinatorOptions = {}
): SonosIntentCoordinator => {
  const client: SonosHttpClient = {
    async getZones(): Promise<Sonos.Zone[]> {
      const response = await rpn({
        method: 'GET',
        uri: `${sonosBaseUrl}/zones`,
        json: true,
        resolveWithFullResponse: true,
        simple: false,
      });

      if (response.statusCode >= 400) {
        throw new Error(`Zones request failed with status ${response.statusCode}`);
      }

      return response.body as Sonos.Zone[];
    },

    async joinRoom(roomName: string, coordinatorRoom: string): Promise<void> {
      const response = await rpn({
        method: 'GET',
        uri: `${sonosBaseUrl}/${encodeURIComponent(roomName)}/join/${encodeURIComponent(coordinatorRoom)}`,
        resolveWithFullResponse: true,
        simple: false,
      });

      if (response.statusCode >= 400) {
        throw new Error(`Join request failed with status ${response.statusCode}`);
      }
    },

    async getState(roomName: string): Promise<Sonos.State> {
      const response = await rpn({
        method: 'GET',
        uri: `${sonosBaseUrl}/${encodeURIComponent(roomName)}/state`,
        json: true,
        resolveWithFullResponse: true,
        simple: false,
      });

      if (response.statusCode >= 400) {
        throw new Error(`State request failed with status ${response.statusCode}`);
      }

      return response.body as Sonos.State;
    },

    async setVolume(roomName: string, volume: number): Promise<void> {
      const response = await rpn({
        method: 'GET',
        uri: `${sonosBaseUrl}/${encodeURIComponent(roomName)}/volume/${volume}`,
        resolveWithFullResponse: true,
        simple: false,
      });

      if (response.statusCode >= 400) {
        throw new Error(`Volume request failed with status ${response.statusCode}`);
      }
    },
  };

  return new SonosIntentCoordinator(client, options);
};
