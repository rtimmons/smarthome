
function isExpired(then: number, ttl: number): boolean {
  const now = new Date().getTime();
  return then + ttl <= now;
}

interface CacheParams {
  ttl: number;
}

interface CacheValue {
  value: any;
  insertedAt: number;
}

type CacheValueProducer<T> = (key: keyof CacheDataMap) => Promise<T>;

function nopProducer<T>(): CacheValueProducer<T | null> {
  return (key: keyof CacheDataMap) => null;
}


// example:
// someKey: {
//   value: 'SomeValue',
//   insertedAt: new Date().getTime() - (this.ttl + 1000),
// }
type CacheDataMap = {
  [key:string]: CacheValue
};

export class Cache {
  ttl: number;
  data: CacheDataMap = {};

  constructor(params: CacheParams = {ttl: 60 * 1000}) {
    this.ttl = params.ttl;
  }

  async get<T>(key: keyof CacheDataMap, producer?: CacheValueProducer<T|null>): Promise<T|null> {
    const usedProducer = producer || nopProducer<T>();
    if (this.data[key] === undefined || isExpired(this.data[key].insertedAt, this.ttl)) {
      // console.log('Key [' + key + '] missing or expired');
      return this.set(key, usedProducer);
    }
    return Promise.resolve(this.data[key].value);
  }

  // producer is a promise
  async set<T>(key, producer: CacheValueProducer<T>): Promise<T> {
    const produced: T = await producer(key);
    this.data[key] = {
      value: produced,
      insertedAt: new Date().getTime(),
    };
    return produced;
  }
}
