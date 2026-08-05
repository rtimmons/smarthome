import { describe, expect, it, vi } from "vitest";

import { loadConfig } from "../src/config.js";
import { _test } from "../src/server.js";

describe("createStoreWithRetry", () => {
  it("retries before succeeding", async () => {
    const config = {
      ...loadConfig(),
      mongoRetries: 3,
      mongoRetryDelayMs: 1,
      mongoUrl: "mongodb://fake",
    };
    const connectFn = vi
      .fn<(url: string) => Promise<unknown>>()
      .mockRejectedValueOnce(new Error("fail1"))
      .mockRejectedValueOnce(new Error("fail2"))
      .mockResolvedValue({ store: "ok" });

    const store = await _test.createStoreWithRetry(config, fakeLogger(), connectFn as never);
    expect(store.isMongo).toBe(true);
    expect(connectFn).toHaveBeenCalledTimes(3);
  });

  it("throws after exhausting retries", async () => {
    const config = {
      ...loadConfig(),
      mongoRetries: 2,
      mongoRetryDelayMs: 1,
      mongoUrl: "mongodb://fake",
    };
    const connectFn = vi
      .fn<(url: string) => Promise<unknown>>()
      .mockRejectedValue(new Error("boom"));

    await expect(
      _test.createStoreWithRetry(config, fakeLogger(), connectFn as never),
    ).rejects.toThrow("boom");
    expect(connectFn).toHaveBeenCalledTimes(2);
  });

  it("prioritizes the canonical MongoDB hostname over a saved legacy alias", async () => {
    const config = {
      ...loadConfig(),
      mongoRetries: 3,
      mongoRetryDelayMs: 1,
      mongoUrl: "mongodb://addon_local_mongodb:27017/tinyurl",
    };

    const connectFn = vi.fn<(url: string) => Promise<unknown>>().mockResolvedValue({ ok: true });

    const store = await _test.createStoreWithRetry(config, fakeLogger(), connectFn as never);
    expect(store.isMongo).toBe(true);
    expect(connectFn).toHaveBeenCalledWith("mongodb://local-mongodb:27017/tinyurl");
    expect(connectFn).toHaveBeenCalledTimes(1);
  });

  it("expands Mongo URLs with known fallbacks", () => {
    expect(_test.expandMongoUrls("mongodb://mongodb:27017/tinyurl")).toEqual([
      "mongodb://local-mongodb:27017/tinyurl",
      "mongodb://local-mongodb.local.hass.io:27017/tinyurl",
      "mongodb://addon_local_mongodb:27017/tinyurl",
      "mongodb://addon_mongodb:27017/tinyurl",
      "mongodb://mongodb:27017/tinyurl",
    ]);

    expect(
      _test.expandMongoUrls("mongodb://user:pass@addon_local_mongodb:27018/db?retry=1"),
    ).toEqual([
      "mongodb://user:pass@local-mongodb:27018/db?retry=1",
      "mongodb://user:pass@local-mongodb.local.hass.io:27018/db?retry=1",
      "mongodb://user:pass@addon_local_mongodb:27018/db?retry=1",
      "mongodb://user:pass@addon_mongodb:27018/db?retry=1",
      "mongodb://user:pass@mongodb:27018/db?retry=1",
    ]);
  });
});

function fakeLogger() {
  return {
    error: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    fatal: vi.fn(),
    trace: vi.fn(),
    child: vi.fn().mockReturnThis(),
  } as unknown as import("fastify").FastifyBaseLogger;
}
