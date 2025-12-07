import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { slugRegex } from "../src/slug.js";
import { buildServer } from "../src/server.js";
import { InMemoryTinyUrlStore } from "../src/stores/inMemoryStore.js";
import type { TinyUrl, TinyUrlStore } from "../src/types.js";

describe("tinyurl-service server", () => {
  let store: InMemoryTinyUrlStore;
  let app: Awaited<ReturnType<typeof buildServer>>;

  beforeEach(async () => {
    store = new InMemoryTinyUrlStore();
    app = await buildServer({ store });
    await app.ready();
  });

  afterEach(async () => {
    await app.close();
  });

  it("creates and lists entries", async () => {
    const createRes = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.com" },
    });
    expect(createRes.statusCode).toBe(201);
    const created = createRes.json();
    expect(created.slug).toMatch(slugRegex);

    const listRes = await app.inject({ method: "GET", url: "/api/urls" });
    expect(listRes.statusCode).toBe(200);
    const list = listRes.json();
    expect(list).toHaveLength(1);
    expect(list[0].target).toBe("https://example.com");
  });

  it("redirects and tracks visits", async () => {
    const createRes = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.com/visit" },
    });
    const { slug, target } = createRes.json();

    const redirectRes = await app.inject({ method: "GET", url: `/${slug}` });
    expect(redirectRes.statusCode).toBe(302);
    expect(redirectRes.headers.location).toBe(target);

    const updatedRes = await app.inject({ method: "GET", url: "/api/urls" });
    const [updated] = updatedRes.json();
    expect(updated.visitCount).toBe(1);
    expect(updated.visits.length).toBe(1);
  });

  it("redirects even with a trailing slash and records the visit", async () => {
    const createRes = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.org/trailing" },
    });
    const { slug } = createRes.json();

    const res = await app.inject({ method: "GET", url: `/${slug}/` });
    expect(res.statusCode).toBe(302);

    const listRes = await app.inject({ method: "GET", url: "/api/urls" });
    const [updated] = listRes.json();
    expect(updated.visitCount).toBe(1);
  });

  it("resets and deletes", async () => {
    const createRes = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.net/reset" },
    });
    const { slug } = createRes.json();

    const resetRes = await app.inject({ method: "POST", url: `/api/urls/${slug}/reset` });
    expect(resetRes.statusCode).toBe(200);
    const reset = resetRes.json();
    expect(reset.visitCount).toBe(0);
    expect(reset.visits.length).toBe(0);

    const deleteRes = await app.inject({ method: "DELETE", url: `/api/urls/${slug}` });
    expect(deleteRes.statusCode).toBe(204);

    const finalListRes = await app.inject({ method: "GET", url: "/api/urls" });
    expect(finalListRes.json()).toHaveLength(0);
  });

  it("redirects even if the store fails to return an updated record", async () => {
    const slug = "fb37rvb";
    const doc: TinyUrl = {
      slug,
      target: "https://example.org/fallback",
      createdAt: new Date(),
      updatedAt: new Date(),
      visitCount: 0,
      visits: [],
    };

    const flakyStore: TinyUrlStore = {
      create: async () => doc,
      list: async () => [doc],
      get: async (s) => (s === slug ? doc : null),
      getByTarget: async (url) => (url === doc.target ? doc : null),
      recordHit: async () => null, // simulate a driver that fails to return the updated doc
      reset: async () => doc,
      delete: async () => true,
    };

    const flakyApp = await buildServer({ store: flakyStore });
    await flakyApp.ready();

    const res = await flakyApp.inject({ method: "GET", url: `/${slug}` });
    expect(res.statusCode).toBe(302);
    expect(res.headers.location).toBe(doc.target);

    await flakyApp.close();
  });

  it("returns 404 for invalid slugs without touching stats", async () => {
    const createRes = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.com/ok" },
    });
    expect(createRes.statusCode).toBe(201);

    const res = await app.inject({ method: "GET", url: "/bad$slug" });
    expect(res.statusCode).toBe(404);

    const listRes = await app.inject({ method: "GET", url: "/api/urls" });
    const [entry] = listRes.json();
    expect(entry.visitCount).toBe(0);
  });

  it("returns 404 for missing slugs", async () => {
    const res = await app.inject({ method: "GET", url: "/doesnotexist" });
    expect(res.statusCode).toBe(404);
  });

  it("reuses slug for duplicate targets", async () => {
    const first = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.com/dupe" },
    });
    expect(first.statusCode).toBe(201);
    const slug = first.json().slug;

    const second = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: "https://example.com/dupe" },
    });
    expect(second.statusCode).toBe(200);
    expect(second.json().slug).toBe(slug);

    const list = await app.inject({ method: "GET", url: "/api/urls" });
    expect(list.json()).toHaveLength(1);
  });

  it("preserves URL fragments on redirect", async () => {
    const target = "https://example.com/path#section";
    const createRes = await app.inject({
      method: "POST",
      url: "/api/urls",
      payload: { url: target },
    });
    expect(createRes.statusCode).toBe(201);
    const { slug } = createRes.json();

    const res = await app.inject({ method: "GET", url: `/${slug}` });
    expect(res.statusCode).toBe(302);
    expect(res.headers.location).toBe(target);
  });

  it("serves static assets even with duplicate slashes in the path", async () => {
    const res = await app.inject({ method: "GET", url: "//assets/styles.css" });
    expect(res.statusCode).toBe(200);
    expect(res.headers["content-type"]).toContain("text/css");
  });
});
