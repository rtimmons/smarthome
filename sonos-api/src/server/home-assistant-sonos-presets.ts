import type {HomeAssistantClientLike} from './home-assistant-client';
import {SonosBackendError} from './sonos-contract';
import {
  isSonosRoomName,
  SONOS_ROOM_NAMES,
  SONOS_ROOM_TO_ENTITY,
  SonosRoomName,
} from './sonos-room-map';

export const HOME_ASSISTANT_SONOS_PRESET_NAMES = [
  'Bedroom-tv',
  'Living Room-tv',
  'Office-tv',
] as const;

export type HomeAssistantSonosPresetName =
  (typeof HOME_ASSISTANT_SONOS_PRESET_NAMES)[number];

export interface HomeAssistantSonosPresetPlayer {
  roomName: SonosRoomName;
  volume: number;
}

export interface HomeAssistantSonosPresetDefinition {
  players: readonly HomeAssistantSonosPresetPlayer[];
  source: 'TV';
  pauseOthers?: true;
}

export type HomeAssistantSonosPresetDefinitions = Readonly<
  Record<HomeAssistantSonosPresetName, HomeAssistantSonosPresetDefinition>
>;

const player = (
  roomName: SonosRoomName,
  volume: number
): Readonly<HomeAssistantSonosPresetPlayer> => Object.freeze({roomName, volume});

export const HOME_ASSISTANT_SONOS_PRESETS: HomeAssistantSonosPresetDefinitions =
  Object.freeze({
    'Bedroom-tv': Object.freeze({
      players: Object.freeze([
        player('Bedroom', 30),
        player('Bathroom', 30),
        player('Closet', 30),
      ]),
      source: 'TV' as const,
    }),
    'Living Room-tv': Object.freeze({
      players: Object.freeze([
        player('Living Room', 30),
        player('Kitchen', 30),
        player('Guest Bathroom', 30),
      ]),
      source: 'TV' as const,
      pauseOthers: true as const,
    }),
    'Office-tv': Object.freeze({
      players: Object.freeze([player('Office', 20)]),
      source: 'TV' as const,
    }),
  });

export class HomeAssistantSonosPresetDefinitionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'HomeAssistantSonosPresetDefinitionError';
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const hasExactKeys = (
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = []
): boolean => {
  const keys = Object.keys(value);
  return required.every(key => keys.includes(key)) &&
    keys.every(key => required.includes(key) || optional.includes(key));
};

/**
 * Strict startup validation for repository-owned definitions. Unknown preset
 * names and extra fields are rejected so a URI or arbitrary entity cannot be
 * smuggled into the service-call policy.
 */
export function assertValidHomeAssistantSonosPresetDefinitions(
  value: unknown
): asserts value is HomeAssistantSonosPresetDefinitions {
  if (!isRecord(value)) {
    throw new HomeAssistantSonosPresetDefinitionError('Preset definitions must be an object');
  }
  const names = Object.keys(value);
  if (
    names.length !== HOME_ASSISTANT_SONOS_PRESET_NAMES.length ||
    names.some(name => !(HOME_ASSISTANT_SONOS_PRESET_NAMES as readonly string[]).includes(name))
  ) {
    throw new HomeAssistantSonosPresetDefinitionError(
      `Preset definitions must contain exactly ${HOME_ASSISTANT_SONOS_PRESET_NAMES.join(', ')}`
    );
  }

  for (const name of HOME_ASSISTANT_SONOS_PRESET_NAMES) {
    const definition = value[name];
    if (!isRecord(definition) || !hasExactKeys(definition, ['players', 'source'], ['pauseOthers'])) {
      throw new HomeAssistantSonosPresetDefinitionError(`Preset ${name} has invalid fields`);
    }
    if (definition.source !== 'TV') {
      throw new HomeAssistantSonosPresetDefinitionError(`Preset ${name} must use the TV source`);
    }
    if (definition.pauseOthers !== undefined && definition.pauseOthers !== true) {
      throw new HomeAssistantSonosPresetDefinitionError(
        `Preset ${name} pauseOthers must be true or omitted`
      );
    }
    if (!Array.isArray(definition.players) || definition.players.length === 0) {
      throw new HomeAssistantSonosPresetDefinitionError(`Preset ${name} must contain players`);
    }
    const rooms = new Set<SonosRoomName>();
    for (const candidate of definition.players) {
      if (!isRecord(candidate) || !hasExactKeys(candidate, ['roomName', 'volume'])) {
        throw new HomeAssistantSonosPresetDefinitionError(`Preset ${name} has an invalid player`);
      }
      if (!isSonosRoomName(candidate.roomName)) {
        throw new HomeAssistantSonosPresetDefinitionError(
          `Preset ${name} contains unknown room ${String(candidate.roomName)}`
        );
      }
      if (rooms.has(candidate.roomName)) {
        throw new HomeAssistantSonosPresetDefinitionError(
          `Preset ${name} contains duplicate room ${candidate.roomName}`
        );
      }
      rooms.add(candidate.roomName);
      if (
        typeof candidate.volume !== 'number' ||
        !Number.isInteger(candidate.volume) ||
        candidate.volume < 0 ||
        candidate.volume > 100
      ) {
        throw new HomeAssistantSonosPresetDefinitionError(
          `Preset ${name} has an invalid volume for ${candidate.roomName}`
        );
      }
    }
  }
}

assertValidHomeAssistantSonosPresetDefinitions(HOME_ASSISTANT_SONOS_PRESETS);

export type HomeAssistantSonosPresetStepKind =
  | 'pause_others'
  | 'isolate_coordinator'
  | 'join_members'
  | 'set_volume'
  | 'select_source';

export interface HomeAssistantSonosPresetStep {
  id: string;
  kind: HomeAssistantSonosPresetStepKind;
  rooms: readonly SonosRoomName[];
  domain: 'media_player';
  service: 'media_pause' | 'unjoin' | 'join' | 'volume_set' | 'select_source';
  data: Readonly<Record<string, unknown>>;
}

export interface HomeAssistantSonosPresetPlan {
  name: HomeAssistantSonosPresetName;
  coordinator: SonosRoomName;
  members: readonly SonosRoomName[];
  source: 'TV';
  pauseOthers: readonly SonosRoomName[];
  steps: readonly HomeAssistantSonosPresetStep[];
}

const step = (
  id: string,
  kind: HomeAssistantSonosPresetStepKind,
  rooms: readonly SonosRoomName[],
  service: HomeAssistantSonosPresetStep['service'],
  data: Record<string, unknown>
): HomeAssistantSonosPresetStep => Object.freeze({
  id,
  kind,
  rooms: Object.freeze([...rooms]),
  domain: 'media_player' as const,
  service,
  data: Object.freeze(data),
});

export const isHomeAssistantSonosPresetName = (
  value: unknown
): value is HomeAssistantSonosPresetName => {
  return typeof value === 'string' &&
    (HOME_ASSISTANT_SONOS_PRESET_NAMES as readonly string[]).includes(value);
};

/**
 * Plans an ordered, non-atomic preset application. The coordinator is first
 * isolated so the following join cannot retain unrelated members. For the one
 * pauseOthers preset, configured rooms outside the preset are paused first.
 */
export const planHomeAssistantSonosPreset = (
  name: string
): HomeAssistantSonosPresetPlan => {
  if (!isHomeAssistantSonosPresetName(name)) {
    throw new SonosBackendError('unknown_preset', `Unknown Sonos preset ${name}`, 404);
  }
  const definition = HOME_ASSISTANT_SONOS_PRESETS[name];
  const members = definition.players.map(entry => entry.roomName);
  const coordinator = members[0];
  const pauseOthers = definition.pauseOthers
    ? SONOS_ROOM_NAMES.filter(roomName => !members.includes(roomName))
    : [];
  const steps: HomeAssistantSonosPresetStep[] = [];

  if (pauseOthers.length > 0) {
    steps.push(step(
      'pause_others',
      'pause_others',
      pauseOthers,
      'media_pause',
      {entity_id: pauseOthers.map(roomName => SONOS_ROOM_TO_ENTITY[roomName])}
    ));
  }
  steps.push(step(
    `isolate_coordinator:${coordinator}`,
    'isolate_coordinator',
    [coordinator],
    'unjoin',
    {entity_id: SONOS_ROOM_TO_ENTITY[coordinator]}
  ));
  if (members.length > 1) {
    steps.push(step(
      `join_members:${coordinator}`,
      'join_members',
      members,
      'join',
      {
        entity_id: SONOS_ROOM_TO_ENTITY[coordinator],
        group_members: members.slice(1).map(roomName => SONOS_ROOM_TO_ENTITY[roomName]),
      }
    ));
  }
  for (const entry of definition.players) {
    steps.push(step(
      `set_volume:${entry.roomName}`,
      'set_volume',
      [entry.roomName],
      'volume_set',
      {
        entity_id: SONOS_ROOM_TO_ENTITY[entry.roomName],
        volume_level: entry.volume / 100,
      }
    ));
  }
  steps.push(step(
    `select_source:${coordinator}`,
    'select_source',
    [coordinator],
    'select_source',
    {entity_id: SONOS_ROOM_TO_ENTITY[coordinator], source: definition.source}
  ));

  return Object.freeze({
    name,
    coordinator,
    members: Object.freeze([...members]),
    source: definition.source,
    pauseOthers: Object.freeze([...pauseOthers]),
    steps: Object.freeze(steps),
  });
};

export interface HomeAssistantSonosPresetExecutorOptions<TObservation> {
  client: Pick<HomeAssistantClientLike, 'callService'>;
  observe: () => TObservation | Promise<TObservation>;
  isObsolete?: () => boolean;
}

export interface HomeAssistantSonosPresetCompleted {
  status: 'completed';
  atomic: false;
  rollbackAttempted: false;
  plan: HomeAssistantSonosPresetPlan;
  completedStepIds: readonly string[];
}

export interface HomeAssistantSonosPresetCancelled {
  status: 'cancelled';
  atomic: false;
  rollbackAttempted: false;
  plan: HomeAssistantSonosPresetPlan;
  completedStepIds: readonly string[];
}

export interface HomeAssistantSonosPresetFailed<TObservation> {
  status: 'failed';
  atomic: false;
  rollbackAttempted: false;
  plan: HomeAssistantSonosPresetPlan;
  failedStep: HomeAssistantSonosPresetStep;
  completedStepIds: readonly string[];
  observation: TObservation | null;
  observationError: unknown | null;
  cause: unknown;
}

export type HomeAssistantSonosPresetExecutionResult<TObservation> =
  | HomeAssistantSonosPresetCompleted
  | HomeAssistantSonosPresetCancelled
  | HomeAssistantSonosPresetFailed<TObservation>;

/**
 * Executes each trusted plan step once, in order. A failed call stops the
 * sequence and observes current state; no compensating calls or atomic
 * rollback are claimed.
 */
export const executeHomeAssistantSonosPreset = async <TObservation>(
  name: string,
  options: HomeAssistantSonosPresetExecutorOptions<TObservation>
): Promise<HomeAssistantSonosPresetExecutionResult<TObservation>> => {
  const plan = planHomeAssistantSonosPreset(name);
  const completedStepIds: string[] = [];
  for (const currentStep of plan.steps) {
    if (options.isObsolete?.()) {
      return {
        status: 'cancelled',
        atomic: false,
        rollbackAttempted: false,
        plan,
        completedStepIds: Object.freeze([...completedStepIds]),
      };
    }
    try {
      await options.client.callService(
        currentStep.domain,
        currentStep.service,
        currentStep.data as Record<string, unknown>
      );
      completedStepIds.push(currentStep.id);
    } catch (cause) {
      let observation: TObservation | null = null;
      let observationError: unknown | null = null;
      try {
        observation = await options.observe();
      } catch (error) {
        observationError = error;
      }
      return {
        status: 'failed',
        atomic: false,
        rollbackAttempted: false,
        plan,
        failedStep: currentStep,
        completedStepIds: Object.freeze([...completedStepIds]),
        observation,
        observationError,
        cause,
      };
    }
  }
  return {
    status: 'completed',
    atomic: false,
    rollbackAttempted: false,
    plan,
    completedStepIds: Object.freeze([...completedStepIds]),
  };
};
