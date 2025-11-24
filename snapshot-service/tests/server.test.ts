import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { buildServer } from "../src/server.js";
import { snapshotFixture } from "../src/fixtures/snapshot.js";

describe("snapshot-service server", () => {
  let app: Awaited<ReturnType<typeof buildServer>>;

  beforeAll(async () => {
    app = await buildServer();
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
