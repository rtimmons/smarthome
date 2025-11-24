import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { buildServer } from "../src/server.js";
import { syntheticReceiptPng } from "./helpers/receipt.js";

describe("receipt routes", () => {
  let app: Awaited<ReturnType<typeof buildServer>>;

  beforeAll(async () => {
    app = await buildServer();
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  it("renders upload page with items from query", async () => {
    const items = encodeURIComponent(JSON.stringify(["Alpha", "Beta"]));
    const res = await app.inject({ method: "GET", url: `/receipt/upload?items=${items}&date=2025-01-01&receipt_id=abc` });
    expect(res.statusCode).toBe(200);
    expect(res.headers["content-type"]).toContain("text/html");
    expect(res.body).toContain("Alpha");
    expect(res.body).toContain("Beta");
    expect(res.body).toContain("2025-01-01");
  });

  it("accepts multipart upload and returns checkbox analysis", async () => {
    const image = await syntheticReceiptPng([1, 3]);
    const boundary = "testboundary";
    const items = encodeURIComponent(JSON.stringify(["Breakfast", "Lunch", "Dinner", "Meds AM"]));
    const body = Buffer.concat([
      Buffer.from(`--${boundary}\r\n`),
      Buffer.from(`Content-Disposition: form-data; name="items"\r\n\r\n${items}\r\n`),
      Buffer.from(`--${boundary}\r\n`),
      Buffer.from(`Content-Disposition: form-data; name="receipt"; filename="receipt.png"\r\n`),
      Buffer.from("Content-Type: image/png\r\n\r\n"),
      image,
      Buffer.from(`\r\n--${boundary}--\r\n`)
    ]);

    const res = await app.inject({
      method: "POST",
      url: "/receipt/analyze",
      payload: body,
      headers: {
        "Content-Type": `multipart/form-data; boundary=${boundary}`
      }
    });

    expect(res.statusCode).toBe(200);
    const json = res.json();
    const checked = (json.items as { label: string; checked: boolean }[]).filter((i) => i.checked).map((i) => i.label);
    expect(checked).toEqual(["Lunch", "Meds AM"]);
    expect(json.status).toBe("ok");
  });
});
