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
  // Lighting controls are interactive. Restart the caller so a newer press can
  // cancel stale wrapper/dispatcher work instead of being ignored while an
  // earlier scene is still draining.
  if (containsSceneAction(automation.action)) {
    return "restart";
  }

  return automation.mode;
}
