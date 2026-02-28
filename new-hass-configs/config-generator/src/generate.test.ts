/**
 * Tests for scene generation with automatic pairing
 */

import * as yaml from "yaml";
import * as fs from "fs";
import * as path from "path";

// Mock filesystem to prevent actual file writes during tests
jest.mock("fs");

describe("Scene Generation with Pairing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Paired device synchronization", () => {
    it("should automatically add _white pair when RGBW device is specified", () => {
      // Import after mocking
      const { generateScenes } = require("./generate-test-helper");

      const testScene = {
        name: "Test Scene",
        lights: [
          {
            device: "office_abovetv", // RGBW device
            state: "on",
            brightness: 255,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both the RGBW and white entities should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();

      // RGBW entity should have brightness
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);

      // White entity should also have brightness to match
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(255);
      expect(sceneEntities["light.light_office_abovetv_white"].state).toBe("on");
    });

    it("should automatically add RGBW pair when _white device is specified", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScene = {
        name: "Test Scene",
        lights: [
          {
            device: "office_abovetv_white", // White device
            state: "on",
            brightness: 180,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both entities should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();

      // White entity should have its specified brightness
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(180);

      // RGBW entity should also have brightness
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(180);
    });

    it("should turn off both paired devices when one is turned off", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScene = {
        name: "Test Off Scene",
        lights: [
          {
            device: "office_abovetv",
            state: "off",
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both should be off
      expect(sceneEntities["light.light_office_abovetv"].state).toBe("off");
      expect(sceneEntities["light.light_office_abovetv_white"].state).toBe("off");
    });

    it("should respect explicitly defined paired devices", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScene = {
        name: "Test Explicit Scene",
        lights: [
          {
            device: "office_abovetv",
            state: "on",
            brightness: 255,
          },
          {
            device: "office_abovetv_white",
            state: "on",
            brightness: 100, // Different brightness explicitly set
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Both should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();

      // RGBW should have 255
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);

      // White should have explicitly set 100 (not auto-synced to 255)
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(100);
    });

    it("should handle multiple paired devices in one scene", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScene = {
        name: "Test Multiple Pairs",
        lights: [
          {
            device: "office_abovetv",
            state: "on",
            brightness: 255,
          },
          {
            device: "living_curtains",
            state: "on",
            brightness: 180,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // All four devices should be present
      expect(sceneEntities["light.light_office_abovetv"]).toBeDefined();
      expect(sceneEntities["light.light_office_abovetv_white"]).toBeDefined();
      expect(sceneEntities["light.light_living_curtains"]).toBeDefined();
      expect(sceneEntities["light.light_living_curtains_white"]).toBeDefined();

      // Each pair should have matching brightness
      expect(sceneEntities["light.light_office_abovetv"].brightness).toBe(255);
      expect(sceneEntities["light.light_office_abovetv_white"].brightness).toBe(255);
      expect(sceneEntities["light.light_living_curtains"].brightness).toBe(180);
      expect(sceneEntities["light.light_living_curtains_white"].brightness).toBe(180);
    });

    it("should not add pairs for unpaired devices", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScene = {
        name: "Test Unpaired",
        lights: [
          {
            device: "office_sidetable", // No pair
            state: "on",
            brightness: 255,
          },
        ],
      };

      const result = generateScenes({ test_scene: testScene });
      const sceneEntities = result[0].entities;

      // Only the specified device should be present
      expect(sceneEntities["light.office_light_sidetable"]).toBeDefined();
      expect(Object.keys(sceneEntities).length).toBe(1);
    });
  });

  describe("Integration test with actual scenes", () => {
    it("should generate valid YAML with paired devices", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScenes = {
        office_high: {
          name: "Office - High",
          lights: [
            {
              device: "office_abovetv_white",
              state: "on",
              brightness: 255,
            },
          ],
        },
      };

      const result = generateScenes(testScenes);
      const yamlOutput = yaml.stringify(result);

      // YAML should include both entities
      expect(yamlOutput).toContain("light.light_office_abovetv:");
      expect(yamlOutput).toContain("light.light_office_abovetv_white:");
      expect(yamlOutput).toContain("brightness: 255");
    });

    it("should restore kitchen upper/lower brightness in high scenes", () => {
      const { generateScenes } = require("./generate-test-helper");

      const testScenes = {
        kitchen_high: {
          name: "Kitchen - High",
          lights: [
            {
              device: "kitchen_upper_white",
              state: "on",
              brightness: 255,
            },
            {
              device: "kitchen_lower_white",
              state: "on",
              brightness: 255,
            },
          ],
        },
      };

      const result = generateScenes(testScenes);
      const entities = result[0].entities;

      expect(entities["light.light_kitchen_upper_white"].brightness).toBe(255);
      expect(entities["light.light_kitchen_lower_white"].brightness).toBe(255);
      expect(entities["light.light_kitchen_upper"].brightness).toBe(255);
      expect(entities["light.light_kitchen_lower"].brightness).toBe(255);
    });
  });
});
