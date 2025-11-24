import { snapshotFixture } from "../src/fixtures/snapshot";
import { SnapshotSchema } from "../src/schema/snapshot";

describe("Snapshot schema", () => {
  it("accepts the fixture shape", () => {
    const parsed = SnapshotSchema.safeParse(snapshotFixture);
    expect(parsed.success).toBe(true);
  });
});
