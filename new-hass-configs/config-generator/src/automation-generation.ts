import { Automation } from "./types";

function containsSceneAction(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(containsSceneAction);
  }
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    candidate.type === "scene" || Object.values(candidate).some(containsSceneAction)
  );
}

export function getEffectiveAutomationMode(
  automation: Automation
): Automation["mode"] {
  // Scene automations call blocking fast-scene wrappers. Keeping the caller in
  // single mode makes repeated button/webhook events coalesce while the first
  // activation is still draining through the shared dispatcher.
  if (containsSceneAction(automation.action)) {
    return "single";
  }

  return automation.mode;
}
