import { Collection, MongoClient, ObjectId } from "mongodb";

import { generateSlug } from "../slug.js";
import { TinyUrl, TinyUrlStore } from "../types.js";

const MAX_VISITS = 10;
const MAX_ATTEMPTS = 30;
const COLLECTION_NAME = "tinyurls";

export interface TinyUrlDocument {
  _id?: ObjectId;
  slug: string;
  target: string;
  createdAt: Date;
  updatedAt: Date;
  visitCount: number;
  visits: Date[];
  lastVisitedAt?: Date;
}

export class MongoTinyUrlStore implements TinyUrlStore {
  private constructor(
    private readonly client: MongoClient,
    private readonly collection: Collection<TinyUrlDocument>,
  ) {}

  static async connect(mongoUrl: string): Promise<MongoTinyUrlStore> {
    const client = new MongoClient(mongoUrl);
    await client.connect();
    const db = client.db();
    const collection = db.collection<TinyUrlDocument>(COLLECTION_NAME);
    await runMigrations(collection);
    return new MongoTinyUrlStore(client, collection);
  }

  async close(): Promise<void> {
    await this.client.close();
  }

  async create(target: string): Promise<TinyUrl> {
    const existing = await this.collection.findOne({ target });
    if (existing) {
      return this.serialize(existing);
    }

    const slug = await this.generateUniqueSlug();
    const now = new Date();
    const doc: TinyUrlDocument = {
      slug,
      target,
      createdAt: now,
      updatedAt: now,
      visitCount: 0,
      visits: [],
    };
    try {
      await this.collection.insertOne(doc);
      return this.serialize(doc);
    } catch (err) {
      // If a unique constraint was hit, return the existing record.
      const dup = await this.collection.findOne({ target });
      if (dup) {
        return this.serialize(dup);
      }
      throw err;
    }
  }

  async list(): Promise<TinyUrl[]> {
    const docs = await this.collection.find({}).sort({ createdAt: -1 }).toArray();
    return docs.map((doc) => this.serialize(doc));
  }

  async getByTarget(target: string): Promise<TinyUrl | null> {
    const doc = await this.collection.findOne({ target });
    return doc ? this.serialize(doc) : null;
  }

  async get(slug: string): Promise<TinyUrl | null> {
    const doc = await this.collection.findOne({ slug });
    return doc ? this.serialize(doc) : null;
  }

  async recordHit(slug: string, at: Date): Promise<TinyUrl | null> {
    const doc = await this.collection.findOneAndUpdate(
      { slug },
      {
        $inc: { visitCount: 1 },
        $set: { lastVisitedAt: at, updatedAt: at },
        $push: { visits: { $each: [at], $position: 0, $slice: MAX_VISITS } },
      },
      { returnDocument: "after" },
    );
    return doc ? this.serialize(doc as TinyUrlDocument) : null;
  }

  async reset(slug: string): Promise<TinyUrl | null> {
    const updatedAt = new Date();
    const doc = await this.collection.findOneAndUpdate(
      { slug },
      { $set: { visitCount: 0, visits: [], updatedAt }, $unset: { lastVisitedAt: "" } },
      { returnDocument: "after" },
    );
    return doc ? this.serialize(doc as TinyUrlDocument) : null;
  }

  async delete(slug: string): Promise<boolean> {
    const res = await this.collection.deleteOne({ slug });
    return res.deletedCount === 1;
  }

  private async generateUniqueSlug(): Promise<string> {
    for (let i = 0; i < MAX_ATTEMPTS; i += 1) {
      const candidate = generateSlug();
      const existing = await this.collection.findOne(
        { slug: candidate },
        { projection: { _id: 1 } },
      );
      if (!existing) {
        return candidate;
      }
    }
    throw new Error("Failed to generate unique slug after multiple attempts");
  }

  private serialize(doc: TinyUrlDocument): TinyUrl {
    return {
      slug: doc.slug,
      target: doc.target,
      createdAt: doc.createdAt,
      updatedAt: doc.updatedAt,
      visitCount: doc.visitCount ?? 0,
      visits: doc.visits ?? [],
      lastVisitedAt: doc.lastVisitedAt,
    };
  }
}

async function runMigrations(collection: Collection<TinyUrlDocument>) {
  await dedupeByKey(collection, "slug");
  await dedupeByKey(collection, "target");
  await Promise.all([
    collection.createIndex({ slug: 1 }, { unique: true }),
    collection.createIndex({ target: 1 }, { unique: true }),
  ]);
}

async function dedupeByKey(
  collection: Collection<TinyUrlDocument>,
  key: "slug" | "target",
): Promise<void> {
  const duplicates = await collection
    .aggregate<{
      _id: string;
      ids: ObjectId[];
      count: number;
    }>([
      { $group: { _id: `$${key}`, ids: { $push: "$_id" }, count: { $sum: 1 } } },
      { $match: { count: { $gt: 1 } } },
    ])
    .toArray();

  for (const group of duplicates) {
    const docs = await collection.find({ _id: { $in: group.ids } }).toArray();
    if (!docs.length) continue;
    const { keep, removeIds } = mergeDuplicates(docs);
    if (keep._id) {
      await collection.updateOne({ _id: keep._id }, { $set: keep });
    }
    if (removeIds.length) {
      await collection.deleteMany({ _id: { $in: removeIds } });
    }
  }
}

export function mergeDuplicates(docs: TinyUrlDocument[]): {
  keep: TinyUrlDocument;
  removeIds: ObjectId[];
} {
  if (!docs.length) {
    throw new Error("mergeDuplicates requires at least one document");
  }

  const sorted = [...docs].sort((a, b) => {
    const aTime = a.createdAt?.getTime() ?? 0;
    const bTime = b.createdAt?.getTime() ?? 0;
    return aTime - bTime;
  });

  const visits = docs
    .flatMap((d) => d.visits || [])
    .filter(Boolean)
    .sort((a, b) => b.getTime() - a.getTime())
    .slice(0, MAX_VISITS);

  const keepDoc = sorted[0];
  const visitCount = docs.reduce((acc, d) => acc + (d.visitCount || 0), 0);
  const lastVisitedAt = visits[0];
  const createdAt = sorted[0].createdAt ?? new Date();
  const updatedAt = new Date(
    Math.max(...docs.map((d) => (d.updatedAt ? d.updatedAt.getTime() : createdAt.getTime()))),
  );

  const merged: TinyUrlDocument = {
    ...keepDoc,
    visitCount,
    visits,
    lastVisitedAt,
    createdAt,
    updatedAt,
  };

  const removeIds = sorted
    .slice(1)
    .map((d) => d._id)
    .filter(Boolean) as ObjectId[];
  return { keep: merged, removeIds };
}
