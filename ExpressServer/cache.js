const _ = require('underscore');

const nopProducer = (k) => Promise.resolve(null);

var isExpired = function(then, ttl) {
  var now = new Date().getTime();
  return then + ttl <= now;
}

class Cache {

  constructor(params) {
    params = params || {
      ttl: 60 * 1000, // 60 seconds
    };

    this.ttl = params.ttl;
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
    producer = producer || nopProducer;
    if (_.isUndefined(this.data[key]) || isExpired(this.data[key].insertedAt, this.ttl)) {
      // console.log('Key [' + key + '] missing or expired');
      return this.set(key, producer);
    }
    return Promise.resolve(this.data[key].value)
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

module.exports = Cache;
