import {assert} from 'chai';
import {Cache} from "./cache";

describe('Cache', () => {
    const cache = new Cache();
    it('gets a value', async function() {
        assert.equal(null, await cache.get('empty'));
        assert.equal(null, await cache.get('empty', async () => 1));

        assert.equal(2, await cache.get('empty2', async () => 2));
        assert.equal(2, await cache.get('empty2', async () => 3));
    });
});
