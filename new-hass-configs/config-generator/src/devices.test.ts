/**
 * Tests for device pairing functionality
 */

import {
  getPairedDeviceName,
  hasPairedDevice,
  getDeviceWithPair,
} from "./devices";

describe("Device Pairing Functions", () => {
  describe("getPairedDeviceName", () => {
    it("should find _white pair for RGBW device", () => {
      expect(getPairedDeviceName("office_abovetv")).toBe("office_abovetv_white");
      expect(getPairedDeviceName("living_curtains")).toBe("living_curtains_white");
      expect(getPairedDeviceName("kitchen_upper")).toBe("kitchen_upper_white");
    });

    it("should find RGBW pair for _white device", () => {
      expect(getPairedDeviceName("office_abovetv_white")).toBe("office_abovetv");
      expect(getPairedDeviceName("living_curtains_white")).toBe("living_curtains");
      expect(getPairedDeviceName("kitchen_upper_white")).toBe("kitchen_upper");
    });

    it("should return null for devices without pairs", () => {
      expect(getPairedDeviceName("office_sidetable")).toBeNull();
      expect(getPairedDeviceName("bathroom_sauna")).toBeNull();
      expect(getPairedDeviceName("living_floor")).toBeNull();
    });

    it("should return null for non-existent devices", () => {
      expect(getPairedDeviceName("nonexistent_device")).toBeNull();
      expect(getPairedDeviceName("fake_light_white")).toBeNull();
    });
  });

  describe("hasPairedDevice", () => {
    it("should return true for devices with pairs", () => {
      expect(hasPairedDevice("office_abovetv")).toBe(true);
      expect(hasPairedDevice("office_abovetv_white")).toBe(true);
      expect(hasPairedDevice("living_curtains")).toBe(true);
      expect(hasPairedDevice("living_curtains_white")).toBe(true);
    });

    it("should return false for devices without pairs", () => {
      expect(hasPairedDevice("office_sidetable")).toBe(false);
      expect(hasPairedDevice("bathroom_sauna")).toBe(false);
      expect(hasPairedDevice("nonexistent_device")).toBe(false);
    });
  });

  describe("getDeviceWithPair", () => {
    it("should return both devices for RGBW device", () => {
      expect(getDeviceWithPair("office_abovetv")).toEqual([
        "office_abovetv",
        "office_abovetv_white",
      ]);
    });

    it("should return both devices for _white device", () => {
      expect(getDeviceWithPair("office_abovetv_white")).toEqual([
        "office_abovetv_white",
        "office_abovetv",
      ]);
    });

    it("should return only the device for unpaired devices", () => {
      expect(getDeviceWithPair("office_sidetable")).toEqual(["office_sidetable"]);
      expect(getDeviceWithPair("bathroom_sauna")).toEqual(["bathroom_sauna"]);
    });
  });

  describe("All _white devices should have pairs", () => {
    const whiteDevices = [
      "office_abovecouch_white",
      "office_abovetv_white",
      "living_curtains_white",
      "living_windowsillleft_white",
      "living_windowsillright_white",
      "living_behindtv_white",
      "living_abovetv_white",
      "kitchen_upper_white",
      "kitchen_lower_white",
      "kitchen_dining_nook_white",
    ];

    whiteDevices.forEach((deviceName) => {
      it(`should have RGBW pair for ${deviceName}`, () => {
        const baseName = deviceName.replace(/_white$/, "");
        expect(getPairedDeviceName(deviceName)).toBe(baseName);
        expect(getPairedDeviceName(baseName)).toBe(deviceName);
      });
    });
  });
});
