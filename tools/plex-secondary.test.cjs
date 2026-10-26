const test = require('node:test');
const assert = require('node:assert/strict');
const { connection, verifyLibrary, LIBRARIES } = require('./plex-secondary.cjs');

test('existing library validation refuses broader, private, duplicate and incomplete roots', () => {
  const wanted = LIBRARIES[0];
  const actual = { type: wanted.type, agent: wanted.agent, scanner: wanted.scanner,
    Location: wanted.roots.map(path => ({ path })) };
  assert.doesNotThrow(() => verifyLibrary(actual, wanted));
  for (const roots of [['/media/FromDrobo'], ['/media/FromDrobo/private'],
    [wanted.roots[0]], [...wanted.roots, wanted.roots[0]]]) {
    assert.throws(() => verifyLibrary({ ...actual, Location: roots.map(path => ({ path })) }, wanted));
  }
  assert.throws(() => verifyLibrary({ ...actual, agent: 'unexpected-agent' }, wanted));
});

test('secondary API rejects another origin before sending credentials', async () => {
  await assert.rejects(connection('fixture-token')('http://example.invalid/library/sections'), /origin required/);
});

test('unexpected response content never escapes in errors and redirects are refused', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.redirect, 'error');
    return new Response('Sensitive Fixture Title / fixture-token', { status: 200 });
  });
  await assert.rejects(connection('fixture-token')('/library/sections'), {
    message: 'Secondary Plex returned an invalid response',
  });
});
