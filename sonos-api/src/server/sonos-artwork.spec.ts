import {strict as assert} from 'assert';

import {
  HomeAssistantBinaryResponse,
  HomeAssistantClientError,
} from './home-assistant-client';
import {haSnapshot, haState} from './home-assistant-test-fixtures';
import {fetchSonosArtwork} from './sonos-artwork';
import {SonosBackendError} from './sonos-contract';

const response = (
  body: Uint8Array,
  contentType = 'image/png',
  contentLength?: number,
  options: {
    chunkSizes?: number[];
    leaveOpen?: boolean;
    onCancel?: () => void;
    onArrayBuffer?: () => void;
    ok?: boolean;
    status?: number;
  } = {}
): HomeAssistantBinaryResponse => {
  let offset = 0;
  let chunkIndex = 0;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (offset >= body.byteLength) {
        if (options.leaveOpen) return new Promise<void>(() => undefined);
        controller.close();
        return;
      }
      const requested = options.chunkSizes?.[chunkIndex++] ?? body.byteLength - offset;
      const end = Math.min(body.byteLength, offset + requested);
      controller.enqueue(body.slice(offset, end));
      offset = end;
    },
    cancel() {
      options.onCancel?.();
    },
  });
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    headers: new Headers({
      'content-type': contentType,
      ...(contentLength === undefined ? {} : {'content-length': String(contentLength)}),
    }),
    body: stream,
    async arrayBuffer() {
      options.onArrayBuffer?.();
      throw new Error('artwork must use the bounded response stream');
    },
  };
};

const run = async (): Promise<void> => {
  const kitchen = haState('Kitchen', {
    attributes: {
      entity_picture: '/api/media_player_proxy/media_player.kitchen?token=private-picture-token',
    },
  });
  const snapshot = haSnapshot([kitchen]);
  const paths: string[] = [];
  const artwork = await fetchSonosArtwork({
    async fetchAuthenticatedPath(path: string) {
      paths.push(path);
      return response(new Uint8Array([1, 2, 3]), 'image/png', 3);
    },
  }, snapshot, 'Kitchen', {maxBytes: 3});
  assert.deepEqual(paths, [
    '/api/media_player_proxy/media_player.kitchen?token=private-picture-token',
  ]);
  assert.equal(artwork.contentType, 'image/png');
  assert.deepEqual([...artwork.body], [1, 2, 3]);
  assert.equal(JSON.stringify(artwork).includes('private-picture-token'), false);

  const coordinator = haState('Bathroom', {
    members: ['Bathroom', 'Kitchen'],
    attributes: {
      entity_picture:
        '/api/media_player_proxy/media_player.bathroom?token=coordinator-token',
    },
  });
  const follower = haState('Kitchen', {
    members: ['Bathroom', 'Kitchen'],
    attributes: {
      entity_picture: '/api/media_player_proxy/media_player.kitchen?token=follower-token',
    },
  });
  const groupedPaths: string[] = [];
  const groupedArtwork = await fetchSonosArtwork({
    async fetchAuthenticatedPath(path: string) {
      groupedPaths.push(path);
      return path.includes('media_player.bathroom')
        ? response(new Uint8Array([9, 8, 7]), 'image/png', 3)
        : response(new Uint8Array([4, 5, 6]), 'image/png', 3);
    },
  }, haSnapshot([coordinator, follower]), 'Kitchen');
  assert.deepEqual(groupedPaths, [
    '/api/media_player_proxy/media_player.bathroom?token=coordinator-token',
  ]);
  assert.deepEqual([...groupedArtwork.body], [9, 8, 7],
    'a follower artwork route streams the observed coordinator bytes');

  let missingArtworkFetches = 0;
  const missingArtwork = haState('Kitchen', {
    attributes: {entity_picture: undefined},
  });
  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        missingArtworkFetches += 1;
        throw new Error('must not fetch');
      },
    }, haSnapshot([missingArtwork]), 'Kitchen'),
    (error: unknown) => error instanceof SonosBackendError &&
      error.code === 'artwork_missing' && error.statusCode === 404
  );
  assert.equal(missingArtworkFetches, 0,
    'missing artwork fails before an authenticated Home Assistant request');

  const sensitiveToken = 'synthetic-signed-picture-secret';
  const sensitiveArtwork = haState('Kitchen', {
    attributes: {
      entity_picture:
        `/api/media_player_proxy/media_player.kitchen?token=${sensitiveToken}`,
    },
  });
  const assertSanitizedFetchFailure = async (
    fetchAuthenticatedPath: () => Promise<HomeAssistantBinaryResponse>,
    label: string
  ): Promise<void> => {
    await assert.rejects(
      fetchSonosArtwork({fetchAuthenticatedPath}, haSnapshot([sensitiveArtwork]), 'Kitchen'),
      (error: unknown) => {
        assert.ok(error instanceof SonosBackendError, label);
        assert.equal(error.code, 'artwork_fetch_failed', label);
        assert.equal(error.statusCode, 502, label);
        assert.equal(error.retryable, true, label);
        assert.equal(String(error).includes(sensitiveToken), false, label);
        assert.equal(JSON.stringify(error).includes(sensitiveToken), false, label);
        return true;
      }
    );
  };

  await assertSanitizedFetchFailure(async () => response(
    new Uint8Array(0),
    'text/plain',
    0,
    {ok: false, status: 503}
  ), 'non-success Home Assistant artwork response');

  await assertSanitizedFetchFailure(async () => {
    throw new Error(
      `Home Assistant failed for /api/media_player_proxy/media_player.kitchen?token=${sensitiveToken}`
    );
  }, 'Home Assistant network failure');

  await assertSanitizedFetchFailure(async () => {
    throw new HomeAssistantClientError(
      'timeout',
      `Home Assistant timed out with Bearer ${sensitiveToken}`
    );
  }, 'Home Assistant artwork timeout');

  let exactBoundArrayBufferRead = false;
  const exactBound = await fetchSonosArtwork({
    async fetchAuthenticatedPath() {
      return response(
        new Uint8Array([1, 2, 3, 4, 5]),
        'image/png',
        undefined,
        {chunkSizes: [2, 1, 2], onArrayBuffer: () => { exactBoundArrayBufferRead = true; }}
      );
    },
  }, snapshot, 'Kitchen', {maxBytes: 5});
  assert.deepEqual([...exactBound.body], [1, 2, 3, 4, 5],
    'a chunked body exactly at the byte limit is accepted');
  assert.equal(exactBoundArrayBufferRead, false,
    'the first artwork layer never falls back to an unbounded arrayBuffer read');

  let chunkedOversizeCancelled = false;
  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        return response(
          new Uint8Array([1, 2, 3, 4]),
          'image/png',
          undefined,
          {
            chunkSizes: [2, 1, 1],
            leaveOpen: true,
            onCancel: () => { chunkedOversizeCancelled = true; },
          }
        );
      },
    }, snapshot, 'Kitchen', {maxBytes: 3}),
    /too large/
  );
  assert.equal(chunkedOversizeCancelled, true,
    'a chunked body is cancelled immediately when it crosses the byte limit');

  let declaredOversizeCancelled = false;
  let declaredOversizeArrayBufferRead = false;
  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        return response(new Uint8Array([1]), 'image/png', 4, {
          onCancel: () => { declaredOversizeCancelled = true; },
          onArrayBuffer: () => { declaredOversizeArrayBufferRead = true; },
        });
      },
    }, snapshot, 'Kitchen', {maxBytes: 3}),
    /too large/
  );
  assert.equal(declaredOversizeCancelled, true,
    'oversized content-length cancels the upstream body before aggregation');
  assert.equal(declaredOversizeArrayBufferRead, false,
    'oversized content-length is rejected without an arrayBuffer read');

  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        return response(new Uint8Array([1]), 'image/svg+xml');
      },
    }, snapshot, 'Kitchen'),
    /allowed image type/
  );

  const external = haState('Kitchen', {
    attributes: {entity_picture: 'https://attacker.invalid/image.png'},
  });
  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        throw new Error('must not fetch');
      },
    }, haSnapshot([external]), 'Kitchen'),
    /path is invalid/
  );

  const protocolRelative = haState('Kitchen', {
    attributes: {
      entity_picture: `//attacker.invalid/media_player.kitchen?token=${sensitiveToken}`,
    },
  });
  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        throw new Error('must not fetch');
      },
    }, haSnapshot([protocolRelative]), 'Kitchen'),
    (error: unknown) => error instanceof SonosBackendError &&
      error.code === 'invalid_artwork' &&
      !String(error).includes(sensitiveToken)
  );

  for (const traversalPath of [
    `/api/media_player_proxy/evil/../media_player.kitchen?token=${sensitiveToken}`,
    `/api/media_player_proxy/%2e%2e/media_player.kitchen?token=${sensitiveToken}`,
    `\\api\\media_player_proxy\\media_player.kitchen?token=${sensitiveToken}`,
  ]) {
    let traversalFetches = 0;
    const traversal = haState('Kitchen', {
      attributes: {entity_picture: traversalPath},
    });
    await assert.rejects(
      fetchSonosArtwork({
        async fetchAuthenticatedPath() {
          traversalFetches += 1;
          throw new Error('must not fetch');
        },
      }, haSnapshot([traversal]), 'Kitchen'),
      (error: unknown) => error instanceof SonosBackendError &&
        error.code === 'invalid_artwork' &&
        !String(error).includes(sensitiveToken),
      traversalPath
    );
    assert.equal(traversalFetches, 0, traversalPath);
  }

  const wrongRoom = haState('Kitchen', {
    attributes: {
      entity_picture: '/api/media_player_proxy/media_player.office?token=secret',
    },
  });
  await assert.rejects(
    fetchSonosArtwork({
      async fetchAuthenticatedPath() {
        throw new Error('must not fetch');
      },
    }, haSnapshot([wrongRoom]), 'Kitchen'),
    /does not match/
  );
};

run().catch(error => {
  console.error(error);
  process.exit(1);
});
