import { describe, expect, it } from "vitest";

import { generateSlug, isValidSlug } from "../src/slug.js";

describe("slug generation", () => {
  it("creates valid slugs within constraints", () => {
    for (let i = 0; i < 200; i += 1) {
      const slug = generateSlug();
      expect(isValidSlug(slug)).toBe(true);
      expect(slug.length).toBeLessThanOrEqual(10);
      expect(slug.startsWith("-")).toBe(false);
      expect(slug.endsWith("-")).toBe(false);
      expect(slug.includes("--")).toBe(false);
      expect(slug).not.toMatch(/[01iloILO]/);
    }
  });
});
