import {strict as assert} from 'assert';

import {SonosStatusProxy, sonosResponseHeaderNames} from './status-proxy';

async function run(): Promise<void> {
  {
    let now = 1_000;
    let requests = 0;
    const proxy = new SonosStatusProxy({
      now: () => now,
      request: async () => {
        requests += 1;
        return {
          statusCode: 200,
          body: {playbackState: 'PLAYING'},
          headers: {'content-type': 'application/json'},
        };
      },
    });

    const response = await proxy.get('http://localhost:5005', 'Kitchen/state');
    assert.equal(requests, 1);
    assert.equal(response.statusCode, 200);
    assert.equal(response.body, JSON.stringify({playbackState: 'PLAYING'}));
    assert.equal(response.headers[sonosResponseHeaderNames.source], 'live');
    assert.equal(response.headers[sonosResponseHeaderNames.stale], 'false');
    assert.equal(response.headers[sonosResponseHeaderNames.ageMs], '0');
  }

  {
    let now = 5_000;
    let requests = 0;
    const proxy = new SonosStatusProxy({
      cacheTtlMs: 30_000,
      now: () => now,
      request: async () => {
        requests += 1;
        if (requests === 1) {
          return {
            statusCode: 200,
            body: [{roomName: 'Kitchen'}],
            headers: {'content-type': 'application/json'},
          };
        }

        const err = new Error('AggregateError') as Error & {
          cause?: {code: string};
        };
        err.cause = {code: 'ECONNREFUSED'};
        throw err;
      },
    });

    await proxy.get('http://localhost:5005', 'zones');
    now = 8_250;
    const stale = await proxy.get('http://localhost:5005', 'zones');
    assert.equal(requests, 2);
    assert.equal(stale.statusCode, 200);
    assert.equal(stale.body, JSON.stringify([{roomName: 'Kitchen'}]));
    assert.equal(stale.headers[sonosResponseHeaderNames.source], 'cache');
    assert.equal(stale.headers[sonosResponseHeaderNames.stale], 'true');
    assert.equal(stale.headers[sonosResponseHeaderNames.ageMs], '3250');
  }

  {
    let now = 10_000;
    const proxy = new SonosStatusProxy({
      cacheTtlMs: 2_000,
      now: () => now,
      request: async () => {
        const err = new Error('AggregateError') as Error & {
          cause?: {code: string};
        };
        err.cause = {code: 'ECONNREFUSED'};
        throw err;
      },
    });

    await assert.rejects(
      () => proxy.get('http://localhost:5005', 'Kitchen/state'),
      /AggregateError/
    );
  }

  {
    let requests = 0;
    const proxy = new SonosStatusProxy({
      request: async () => {
        requests += 1;
        if (requests === 1) {
          return {
            statusCode: 200,
            body: [{roomName: 'Kitchen'}],
            headers: {'content-type': 'application/json'},
          };
        }

        const err = new Error('AggregateError') as Error & {
          cause?: {code: string};
        };
        err.cause = {code: 'ECONNREFUSED'};
        throw err;
      },
    });

    await proxy.get('http://localhost:5005', 'zones');
    proxy.invalidate('zones');
    await assert.rejects(
      () => proxy.get('http://localhost:5005', 'zones'),
      /AggregateError/
    );
  }

  {
    let resolveRequest: any = null;
    let requests = 0;
    const proxy = new SonosStatusProxy({
      request: () => {
        requests += 1;
        return new Promise(resolve => {
          resolveRequest = resolve;
        }) as any;
      },
    });

    const first = proxy.get('http://localhost:5005', 'zones');
    const second = proxy.get('http://localhost:5005', 'zones');
    assert.equal(requests, 1);
    assert(resolveRequest);
    if (!resolveRequest) {
      throw new Error('Expected inflight request resolver');
    }
    (resolveRequest as any)({
      statusCode: 200,
      body: [],
      headers: {'content-type': 'application/json'},
    });

    const [firstResponse, secondResponse] = await Promise.all([first, second]);
    assert.equal(firstResponse.body, '[]');
    assert.equal(secondResponse.body, '[]');
  }
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
