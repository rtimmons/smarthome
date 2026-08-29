import {expect} from 'chai';
import {afterEach, describe, it, vi} from 'vitest';

import {
    requestBinary,
    ResponseBodyTooLargeError,
} from './http';

describe('requestBinary', () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('preserves exact bytes', async () => {
        const bytes = new Uint8Array([0, 255, 17, 128, 3]);
        vi.stubGlobal(
            'fetch',
            vi.fn(async () =>
                new Response(bytes, {
                    status: 200,
                    headers: {'content-type': 'image/png'},
                })
            )
        );

        const response = await requestBinary('http://example.invalid/artwork');

        expect(Array.from(response.body)).to.deep.equal(Array.from(bytes));
        expect(response.headers.get('content-type')).to.equal('image/png');
    });

    it('accepts a streamed body exactly at the byte limit', async () => {
        const bytes = new Uint8Array([0, 255, 17, 128, 3]);
        vi.stubGlobal(
            'fetch',
            vi.fn(async () =>
                new Response(bytes, {
                    status: 200,
                    headers: {'content-length': String(bytes.length)},
                })
            )
        );

        const response = await requestBinary(
            'http://example.invalid/artwork',
            {},
            1000,
            bytes.length
        );

        expect(Array.from(response.body)).to.deep.equal(Array.from(bytes));
    });

    it('rejects a declared response larger than the limit before reading', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () =>
                new Response(new Uint8Array([1]), {
                    status: 200,
                    headers: {'content-length': '11'},
                })
            )
        );

        let error: unknown;
        try {
            await requestBinary('http://example.invalid/artwork', {}, 1000, 10);
        } catch (caught) {
            error = caught;
        }
        expect(error).to.be.instanceOf(ResponseBodyTooLargeError);
    });

    it('rejects a chunked response as soon as the streamed limit is exceeded', async () => {
        const stream = new ReadableStream<Uint8Array>({
            start(controller) {
                controller.enqueue(new Uint8Array([1, 2, 3]));
                controller.enqueue(new Uint8Array([4, 5, 6]));
                controller.close();
            },
        });
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => new Response(stream, {status: 200}))
        );

        let error: unknown;
        try {
            await requestBinary('http://example.invalid/artwork', {}, 1000, 5);
        } catch (caught) {
            error = caught;
        }
        expect(error).to.be.instanceOf(ResponseBodyTooLargeError);
    });
});
