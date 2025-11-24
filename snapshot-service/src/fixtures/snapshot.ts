import rawSnapshot from "./snapshot.json" with { type: "json" };
import { SnapshotSchema } from "../schema/snapshot.js";

export const snapshotFixture = SnapshotSchema.parse(rawSnapshot);
