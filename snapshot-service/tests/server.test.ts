import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { buildServer } from "../src/server";
import { snapshotFixture } from "../src/fixtures/snapshot";

describe("snapshot-service server", () => {
  const app = buildServer();

  beforeAll(async () => {
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  it("responds on /healthz", async () => {
    const res = await app.inject({ method: "GET", url: "/healthz" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ status: "ok" });
  });

  it("returns the snapshot fixture", async () => {
    const res = await app.inject({ method: "GET", url: "/snapshot" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual(snapshotFixture);
  });
});
