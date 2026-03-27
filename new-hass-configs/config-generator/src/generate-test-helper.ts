import { Scene } from "./types";
import {
  HAScene,
  generateFastSceneCalls,
  generateFastScriptsFromRegistry,
  generateScenesFromRegistry,
} from "./scene-generation";

export function generateScenes(scenes: Record<string, Scene>): HAScene[] {
  return generateScenesFromRegistry(scenes);
}

export function generateFastScripts(scenes: Record<string, Scene>) {
  return generateFastScriptsFromRegistry(scenes);
}

export function generateFastCalls(scene: Scene) {
  return generateFastSceneCalls(scene);
}
