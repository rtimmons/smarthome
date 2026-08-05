import { Automation } from "./types";

export function getEffectiveAutomationMode(
  automation: Automation
): Automation["mode"] {
  const actions = Array.isArray(automation.action)
    ? automation.action
    : [automation.action];

  // Scene automations call blocking fast-scene wrappers. Keeping the caller in
  // single mode makes repeated button/webhook events coalesce while the first
  // activation is still draining through the shared dispatcher.
  if (actions.some((action) => action.type === "scene")) {
    return "single";
  }

  return automation.mode;
}
