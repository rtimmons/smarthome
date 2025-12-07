import { ObjectId } from "mongodb";
import { describe, expect, it } from "vitest";

import { mergeDuplicates, type TinyUrlDocument } from "../src/stores/mongoStore.js";

const baseDate = new Date("2024-01-01T00:00:00.000Z");

describe("mergeDuplicates", () => {
  it("merges visit counts, visits, and timestamps while keeping the first document", () => {
    const keepId = new ObjectId("111111111111111111111111");
    const removeId = new ObjectId("222222222222222222222222");
    const docs: TinyUrlDocument[] = [
      {
        _id: keepId,
        slug: "abc",
        target: "https://example.com",
        createdAt: baseDate,
        updatedAt: baseDate,
        visitCount: 2,
        visits: [new Date("2024-01-02T10:00:00Z")],
      },
      {
        _id: removeId,
        slug: "abc",
        target: "https://example.com",
        createdAt: new Date("2024-01-03T00:00:00Z"),
        updatedAt: new Date("2024-01-04T00:00:00Z"),
        visitCount: 5,
        visits: [new Date("2024-01-04T10:00:00Z"), new Date("2024-01-04T09:00:00Z")],
      },
    ];

    const { keep, removeIds } = mergeDuplicates(docs);
    expect(removeIds).toEqual([removeId]);
    expect(keep.visitCount).toBe(7);
    expect(keep.visits.map((d) => d.toISOString())).toEqual([
      "2024-01-04T10:00:00.000Z",
      "2024-01-04T09:00:00.000Z",
      "2024-01-02T10:00:00.000Z",
    ]);
    expect(keep.lastVisitedAt?.toISOString()).toBe("2024-01-04T10:00:00.000Z");
    expect(keep.createdAt.toISOString()).toBe(baseDate.toISOString());
    expect(keep.updatedAt.toISOString()).toBe("2024-01-04T00:00:00.000Z");
  });
});
