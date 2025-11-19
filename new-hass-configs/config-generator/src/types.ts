/**
 * Home Assistant Configuration Generator - Type Definitions
 *
 * This file defines TypeScript types for Home Assistant devices, scenes, and automations.
 * These types provide compile-time validation and IDE support for configuration generation.
 */

// ============================================================================
// Device Types
// ============================================================================

export type DeviceType =
  | "rgbw_light"
  | "dimmer_light"
  | "color_light"
  | "white_light"
  | "outlet"
  | "switch"
  | "zwave_switch_light" // Z-Wave dimmer hardware with non-dimmable fixture (on/off only)
  | "zwave_dimmer_46203"
  | "zwave_zen31_rgbw";

export type ZWaveEvent =
  | "singleUp"
  | "singleDown"
  | "doubleUp"
  | "doubleDown"
  | "tripleUp"
  | "tripleDown"
  | "quadUp"
  | "quadDown"
  | "quintUp"
  | "quintDown"
  | "holdStart"
  | "holdEnd";

export interface ZWaveEventData {
  scene_id?: number;
  scene_data?: number;
  command_class_name?: string;
  property_key_name?: string;
  value?: string;
}

export interface Device {
  entity: string;
  type: DeviceType;
  capabilities?: DeviceCapability[];
  events?: Partial<Record<ZWaveEvent, ZWaveEventData>>;
  device_id?: string; // For Z-Wave JS triggers
}

export type DeviceCapability =
  | "brightness"
  | "color_temp"
  | "rgb_color"
  | "rgbw_color"
  | "white_value"
  | "on_off";

// ============================================================================
// Scene Types
// ============================================================================

export interface LightState {
  device: string; // Reference to device key in devices registry
  state?: "on" | "off";
  brightness?: number; // 0-255
  rgb_color?: [number, number, number]; // RGB values 0-255
  rgbw_color?: [number, number, number, number]; // RGBW values 0-255
  color_temp?: number; // Kelvin
  white_value?: number; // 0-255
  transition?: number; // Transition time in seconds
}

export interface Scene {
  name: string;
  icon?: string;
  lights: LightState[];
  switches?: Record<string, "on" | "off">; // For outlets/switches
}

// ============================================================================
// Automation Types
// ============================================================================

export type TriggerType =
  | "zwave_js_scene"
  | "webhook"
  | "time"
  | "state"
  | "numeric_state"
  | "template"
  | "event";

export interface ZWaveJsSceneTrigger {
  type: "zwave_js_scene";
  device: string; // Reference to device key in devices registry
  event: ZWaveEvent;
}

export interface WebhookTrigger {
  type: "webhook";
  webhook_id: string;
}

export interface TimeTrigger {
  type: "time";
  at: string; // Time in HH:MM:SS format
}

export interface StateTrigger {
  type: "state";
  entity_id: string;
  to?: string;
  from?: string;
  for?: string | number; // Duration
}

export interface NumericStateTrigger {
  type: "numeric_state";
  entity_id: string;
  above?: number;
  below?: number;
  for?: string | number;
}

export interface TemplateTrigger {
  type: "template";
  value_template: string;
}

export interface EventTrigger {
  type: "event";
  event_type: string;
  event_data?: Record<string, any>;
}

export type Trigger =
  | ZWaveJsSceneTrigger
  | WebhookTrigger
  | TimeTrigger
  | StateTrigger
  | NumericStateTrigger
  | TemplateTrigger
  | EventTrigger;

// ============================================================================
// Action Types
// ============================================================================

export type ActionType =
  | "scene"
  | "service"
  | "delay"
  | "wait_template"
  | "choose"
  | "repeat";

export interface SceneAction {
  type: "scene";
  scene: string; // Reference to scene key in scenes registry
}

export interface ServiceAction {
  type: "service";
  service: string;
  target?: {
    entity_id?: string | string[];
    device_id?: string | string[];
    area_id?: string | string[];
  };
  data?: Record<string, any>;
}

export interface DelayAction {
  type: "delay";
  duration: string | number; // Duration in seconds or HH:MM:SS format
}

export interface WaitTemplateAction {
  type: "wait_template";
  template: string;
  timeout?: string | number;
}

export interface ChooseAction {
  type: "choose";
  choices: Array<{
    conditions: Condition[];
    sequence: Action[];
  }>;
  default?: Action[];
}

export interface RepeatAction {
  type: "repeat";
  count?: number;
  while?: Condition[];
  until?: Condition[];
  sequence: Action[];
}

export type Action =
  | SceneAction
  | ServiceAction
  | DelayAction
  | WaitTemplateAction
  | ChooseAction
  | RepeatAction;

// ============================================================================
// Condition Types
// ============================================================================

export type ConditionType =
  | "state"
  | "numeric_state"
  | "template"
  | "time"
  | "zone"
  | "and"
  | "or"
  | "not";

export interface StateCondition {
  type: "state";
  entity_id: string;
  state: string;
}

export interface NumericStateCondition {
  type: "numeric_state";
  entity_id: string;
  above?: number;
  below?: number;
}

export interface TemplateCondition {
  type: "template";
  value_template: string;
}

export interface TimeCondition {
  type: "time";
  after?: string;
  before?: string;
  weekday?: string[];
}

export interface ZoneCondition {
  type: "zone";
  entity_id: string;
  zone: string;
}

export interface AndCondition {
  type: "and";
  conditions: Condition[];
}

export interface OrCondition {
  type: "or";
  conditions: Condition[];
}

export interface NotCondition {
  type: "not";
  conditions: Condition[];
}

export type Condition =
  | StateCondition
  | NumericStateCondition
  | TemplateCondition
  | TimeCondition
  | ZoneCondition
  | AndCondition
  | OrCondition
  | NotCondition;

// ============================================================================
// Automation
// ============================================================================

export interface Automation {
  alias: string;
  description?: string;
  trigger: Trigger | Trigger[];
  condition?: Condition | Condition[];
  action: Action | Action[];
  mode?: "single" | "restart" | "queued" | "parallel";
  max?: number; // Max executions for queued/parallel modes
}

// ============================================================================
// Registry Types
// ============================================================================

export interface DeviceRegistry {
  lights: Record<string, Device>;
  switches: Record<string, Device>;
  outlets: Record<string, Device>;
  sensors?: Record<string, Device>;
}

export interface SceneRegistry {
  [key: string]: Scene;
}

export interface AutomationRegistry {
  [key: string]: Automation;
}
