import * as _ from 'underscore';

const nopProducer = () => Promise.resolve(null);

function isExpired(then, ttl) {
  const now = new Date().getTime();
  return then + ttl <= now;
}

export class Cache {
  ttl: any;
  data: any;

  constructor(params?) {
    const usedParams = params || {
      ttl: 60 * 1000, // 60 seconds
    };

    this.ttl = usedParams.ttl;
    this.data = {
      // example:
      // someKey: {
      //   value: 'SomeValue',
      //   insertedAt: new Date().getTime() - (this.ttl + 1000),
      // }
    };
  }

  // producer is a promise
  get(key, producer) {
    const usedProducer = producer || nopProducer;
    if (_.isUndefined(this.data[key]) || isExpired(this.data[key].insertedAt, this.ttl)) {
      // console.log('Key [' + key + '] missing or expired');
      return this.set(key, usedProducer);
    }
    return Promise.resolve(this.data[key].value);
  }

  // producer is a promise
  set(key, producer) {
    return producer.then((val) => {
      this.data[key] = {
        value: val,
        insertedAt: new Date().getTime(),
      };
      return Promise.resolve(val);
    });
  }
}
