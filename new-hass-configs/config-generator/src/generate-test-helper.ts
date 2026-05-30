import { Scene } from "./types";
import {
  FastSceneGenerationOptions,
  HAScene,
  generateFastSceneCalls,
  generateFastScriptsFromRegistry,
  generateScenesFromRegistry,
} from "./scene-generation";

export function generateScenes(scenes: Record<string, Scene>): HAScene[] {
  return generateScenesFromRegistry(scenes);
}

export function generateFastScripts(
  scenes: Record<string, Scene>,
  options?: FastSceneGenerationOptions
) {
  return generateFastScriptsFromRegistry(scenes, options);
}

export function generateFastCalls(scene: Scene) {
  return generateFastSceneCalls(scene);
}
