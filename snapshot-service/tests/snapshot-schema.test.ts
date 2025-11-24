import { snapshotFixture } from "../src/fixtures/snapshot.js";
import { SnapshotSchema } from "../src/schema/snapshot.js";

describe("Snapshot schema", () => {
  it("accepts the fixture shape", () => {
    const parsed = SnapshotSchema.safeParse(snapshotFixture);
    expect(parsed.success).toBe(true);
  });
});
