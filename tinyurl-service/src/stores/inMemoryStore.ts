import { generateSlug } from "../slug.js";
import { TinyUrl, TinyUrlStore } from "../types.js";

const MAX_VISITS = 10;

export class InMemoryTinyUrlStore implements TinyUrlStore {
  private items = new Map<string, TinyUrl>();
  private targetIndex = new Map<string, string>();

  async create(target: string): Promise<TinyUrl> {
    const existingSlug = this.targetIndex.get(target);
    if (existingSlug) {
      const existing = this.items.get(existingSlug);
      if (existing) {
        return structuredClone(existing);
      }
    }

    const slug = this.generateUniqueSlug();
    const now = new Date();
    const doc: TinyUrl = {
      slug,
      target,
      createdAt: now,
      updatedAt: now,
      visitCount: 0,
      visits: [],
    };
    this.items.set(slug, doc);
    this.targetIndex.set(target, slug);
    return structuredClone(doc);
  }

  async getByTarget(target: string): Promise<TinyUrl | null> {
    const slug = this.targetIndex.get(target);
    return slug ? this.get(slug) : null;
  }

  async list(): Promise<TinyUrl[]> {
    return Array.from(this.items.values())
      .map((item) => structuredClone(item))
      .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
  }

  async get(slug: string): Promise<TinyUrl | null> {
    const item = this.items.get(slug);
    return item ? structuredClone(item) : null;
  }

  async recordHit(slug: string, at: Date): Promise<TinyUrl | null> {
    const item = this.items.get(slug);
    if (!item) return null;
    item.visitCount += 1;
    item.lastVisitedAt = at;
    item.updatedAt = at;
    item.visits = [at, ...item.visits].slice(0, MAX_VISITS);
    return structuredClone(item);
  }

  async reset(slug: string): Promise<TinyUrl | null> {
    const item = this.items.get(slug);
    if (!item) return null;
    item.visitCount = 0;
    item.visits = [];
    item.lastVisitedAt = undefined;
    item.updatedAt = new Date();
    return structuredClone(item);
  }

  async delete(slug: string): Promise<boolean> {
    const item = this.items.get(slug);
    if (item) {
      this.targetIndex.delete(item.target);
    }
    return this.items.delete(slug);
  }

  private generateUniqueSlug(): string {
    for (let i = 0; i < 50; i += 1) {
      const candidate = generateSlug();
      if (!this.items.has(candidate)) {
        return candidate;
      }
    }
    throw new Error("Failed to generate unique slug");
  }
}
