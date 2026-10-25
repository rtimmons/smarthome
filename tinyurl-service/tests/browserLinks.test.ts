import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import { describe, expect, it } from "vitest";

function shortUrl(hostname: string, baseUrl?: string) {
  const element = { addEventListener() {}, classList: { add() {}, remove() {} } };
  const context = createContext({
    document: {
      querySelector: () => element,
      getElementById: () => element,
    },
    window: {
      location: { protocol: "http:", hostname },
      __TINYURL_CONFIG__: { baseUrl },
    },
    fetch: () => new Promise(() => {}),
  });
  runInContext(readFileSync("public/app.js", "utf8"), context);
  return runInContext('buildShortUrl("fixture")', context);
}

describe("shared short links", () => {
  it("keeps native LAN links when management uses SSO", () => {
    expect(shortUrl("tinyurl.home.rytim.com")).toBe("http://tinyurl.home.arpa/fixture");
  });
  it("preserves direct clients and an explicit public base URL", () => {
    expect(shortUrl("192.168.1.163")).toBe("http://192.168.1.163:4100/fixture");
    expect(shortUrl("tinyurl.home.rytim.com", "https://fixture.invalid/")).toBe(
      "https://fixture.invalid/fixture",
    );
  });
});
