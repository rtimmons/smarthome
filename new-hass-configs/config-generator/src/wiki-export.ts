/** Documentation export: desired configuration only, no HA clients or generated secrets. */
import { devices } from "./devices";
import { scenes } from "./scenes";
import { Device } from "./types";

const inventory = Object.entries(devices).flatMap(([category, entries]) =>
  Object.entries(entries as Record<string, Device>).map(([key, device]) => ({
    category, key, entity: device.entity, type: device.type,
    inventoryStatus: device.inventoryStatus ?? "active",
    sceneStatus: device.sceneStatus ?? "active",
    includeInAllOff: device.includeInAllOff !== false,
    allowSceneTurnOff: device.allowSceneTurnOff !== false,
  }))
);
const definitions = Object.entries(scenes).map(([id, scene]) => ({
  id, name: scene.name, script: `script.fast_scene_${id}`,
  targets: [...scene.lights.map((target) => target.device), ...Object.keys(scene.switches ?? {})],
}));
process.stdout.write(JSON.stringify({ devices: inventory, scenes: definitions }, null, 2) + "\n");
