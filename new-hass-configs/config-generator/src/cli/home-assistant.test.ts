import { parseArgs } from "./home-assistant";
import {
  DEFAULT_HASS_SSH_IDENTITY,
  getSshOptions,
  runCommand,
  selectOwnerRefreshToken,
} from "./home-assistant-client";

describe("Home Assistant CLI", () => {
  it("parses state commands and connection overrides", () => {
    expect(
      parseArgs(
        [
          "state",
          "light.kitchen",
          "--host",
          "root@192.0.2.10",
          "--server",
          "http://192.0.2.10:8123",
        ],
        {}
      )
    ).toMatchObject({
      command: "state",
      entityId: "light.kitchen",
      host: "root@192.0.2.10",
      server: "http://192.0.2.10:8123",
    });
  });

  it("merges entity shorthand with JSON service data", () => {
    expect(
      parseArgs(
        [
          "call",
          "light.turn_on",
          "--entity-id",
          "light.kitchen",
          "--data",
          '{"brightness":128}',
        ],
        {}
      ).data
    ).toEqual({
      entity_id: "light.kitchen",
      brightness: 128,
    });
  });

  it("uses repository-friendly inventory output defaults", () => {
    expect(parseArgs(["inventory"], {})).toMatchObject({
      command: "inventory",
      deviceOutput: "device_inventory.json",
      entityOutput: "entity_inventory.json",
    });
  });

  it("rejects malformed service names", () => {
    expect(() => parseArgs(["call", "turn_on"], {})).toThrow(
      "Usage: home-assistant call"
    );
  });
});

describe("selectOwnerRefreshToken", () => {
  const auth = {
    data: {
      users: [
        { id: "owner", is_owner: true },
        { id: "guest", is_owner: false },
      ],
      refresh_tokens: [
        { user_id: "guest", client_id: "http://example/", token: "guest" },
        { user_id: "owner", client_id: "http://fallback/", token: "fallback" },
        { user_id: "owner", client_id: "http://preferred/", token: "preferred" },
      ],
    },
  };

  it("prefers an owner token issued to the target client", () => {
    expect(selectOwnerRefreshToken(auth, "http://preferred")).toMatchObject({
      token: "preferred",
    });
  });

  it("falls back to another owner token", () => {
    expect(selectOwnerRefreshToken(auth, "http://missing")).toMatchObject({
      token: "fallback",
    });
  });
});

describe("runCommand", () => {
  it("does not include sensitive command arguments in failures", () => {
    const secret = "test-secret-that-must-not-be-logged";

    expect(() =>
      runCommand(process.execPath, [
        "-e",
        "process.stderr.write('expected failure'); process.exit(1)",
        secret,
      ])
    ).toThrow("node failed: expected failure");

    try {
      runCommand(process.execPath, ["-e", "process.exit(1)", secret]);
    } catch (error) {
      expect(String(error)).not.toContain(secret);
    }
  });
});

describe("getSshOptions", () => {
  it("selects the ignored repository-local Home Assistant identity", () => {
    expect(getSshOptions({})).toEqual(
      expect.arrayContaining([
        "-i",
        DEFAULT_HASS_SSH_IDENTITY,
        "-o",
        "IdentitiesOnly=yes",
      ])
    );
    expect(DEFAULT_HASS_SSH_IDENTITY).toMatch(
      /\.ssh\/id_ed25519_codex_smarthome$/
    );
  });

  it("supports an explicit identity override without using an SSH agent", () => {
    const options = getSshOptions({
      HASS_SSH_IDENTITY: "/tmp/test-home-assistant-key",
    });

    expect(options).toEqual(
      expect.arrayContaining([
        "-i",
        "/tmp/test-home-assistant-key",
        "-o",
        "IdentitiesOnly=yes",
      ])
    );
  });
});
