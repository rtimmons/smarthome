/** Shared spoken labels; scene/script IDs keep their existing high/low suffixes. */
export const SCENE_PRESET_LABELS = {
  high: "Bright",
  medium: "Medium",
  low: "Dim",
  off: "Off",
} as const;

export type ScenePresetLevel = keyof typeof SCENE_PRESET_LABELS;

export function getScenePresetLevel(sceneId: string): ScenePresetLevel | undefined {
  const separator = sceneId.lastIndexOf("_");
  if (separator < 0) return undefined;
  const level = sceneId.slice(separator + 1);
  return Object.prototype.hasOwnProperty.call(SCENE_PRESET_LABELS, level)
    ? level as ScenePresetLevel : undefined;
}
