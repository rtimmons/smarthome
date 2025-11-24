import rawSnapshot from "./snapshot.json" assert { type: "json" };
import { SnapshotSchema } from "../schema/snapshot";

export const snapshotFixture = SnapshotSchema.parse(rawSnapshot);
