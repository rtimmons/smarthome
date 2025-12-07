export interface TinyUrl {
  slug: string;
  target: string;
  createdAt: Date;
  updatedAt: Date;
  visitCount: number;
  visits: Date[];
  lastVisitedAt?: Date;
}

export interface TinyUrlStore {
  create(target: string): Promise<TinyUrl>;
  getByTarget(target: string): Promise<TinyUrl | null>;
  list(): Promise<TinyUrl[]>;
  get(slug: string): Promise<TinyUrl | null>;
  recordHit(slug: string, at: Date): Promise<TinyUrl | null>;
  reset(slug: string): Promise<TinyUrl | null>;
  delete(slug: string): Promise<boolean>;
}
