import {expect} from 'chai';
import {afterEach, describe, it, vi} from 'vitest';

import {
    createSonosRouter,
    createSonosProxy,
    SONOS_ARTWORK_MAX_BYTES,
    SONOS_DEPRECATED_ROOT_ROUTES,
    SONOS_INTENT_UPSTREAM_ROUTES,
} from './sonos';

class FakeResponse {
    statusCode = 200;
    body: unknown;
    headers = new Map<string, string>();

    setHeader(name: string, value: string) {
        this.headers.set(name.toLowerCase(), value);
        return this;
    }

    type(value: string) {
        this.setHeader('content-type', value);
        return this;
    }

    status(value: number) {
        this.statusCode = value;
        return this;
    }

    send(value: unknown) {
        this.body = value;
        return this;
    }

    json(value: unknown) {
        this.setHeader('content-type', 'application/json');
        this.body = value;
        return this;
    }
}

afterEach(() => {
    vi.restoreAllMocks();
});

describe('Grid Dashboard Sonos proxy', () => {
    it('preserves the complete retained success and non-2xx contract matrix', async () => {
        type RouteCase = {
            label: string;
            browserMethod: 'GET' | 'POST';
            browserPath: string;
            upstreamPath: string;
            registration: string | 'generic-sonos';
            params?: Record<string, string>;
            body?: unknown;
            successStatus: number;
            freshness: boolean;
            binary?: true;
        };
        const groupAllBody = {
            targetRoom: 'Living Room',
            roomNames: ['Living Room', 'Guest Bathroom'],
        };
        const routes: RouteCase[] = [
            {
                label: 'zones', browserMethod: 'GET', browserPath: '/sonos/zones',
                upstreamPath: '/sonos/zones', registration: 'generic-sonos',
                successStatus: 200, freshness: true,
            },
            {
                label: 'room state', browserMethod: 'GET',
                browserPath: '/sonos/Living%20Room/state',
                upstreamPath: '/sonos/Living%20Room/state', registration: 'generic-sonos',
                successStatus: 200, freshness: true,
            },
            {
                label: 'artwork', browserMethod: 'GET',
                browserPath: '/sonos/Living%20Room/artwork',
                upstreamPath: '/sonos/Living%20Room/artwork', registration: 'generic-sonos',
                successStatus: 200, freshness: true, binary: true,
            },
            ...[
                ['play', '/sonos/Living%20Room/play', 200],
                ['pause', '/sonos/Living%20Room/pause', 200],
                ['play/pause', '/sonos/Living%20Room/playpause', 200],
                ['next', '/sonos/Living%20Room/next', 200],
                ['favorite', '/sonos/Living%20Room/favorite/Zero%207%20Radio', 200],
                ['join', '/sonos/Living%20Room/join/Guest%20Bathroom', 202],
                ['leave', '/sonos/Living%20Room/leave', 202],
                ['group volume', '/sonos/Living%20Room/groupVolume/%2B2', 200],
                ['room volume', '/sonos/Living%20Room/volume/30', 200],
                ['preset', '/sonos/Living%20Room/preset/Living%20Room-tv', 202],
            ].map(([label, path, successStatus]) => ({
                label: String(label),
                browserMethod: 'GET' as const,
                browserPath: String(path),
                upstreamPath: String(path),
                registration: 'generic-sonos' as const,
                successStatus: Number(successStatus),
                freshness: false,
            })),
            {
                label: 'same volume', browserMethod: 'GET', browserPath: '/same/:room',
                upstreamPath: '/same/Guest%20Bathroom', registration: '/same/:room',
                params: {room: 'Guest Bathroom'}, successStatus: 200, freshness: false,
            },
            {
                label: 'smart down', browserMethod: 'GET', browserPath: '/down',
                upstreamPath: '/down', registration: '/down', successStatus: 200,
                freshness: false,
            },
            {
                label: 'smart up', browserMethod: 'GET', browserPath: '/up',
                upstreamPath: '/up', registration: '/up', successStatus: 200,
                freshness: false,
            },
            {
                label: 'join-all intent', browserMethod: 'POST',
                browserPath: '/sonos-intents/group-all',
                upstreamPath: '/intents/sonos/group-all',
                registration: '/sonos-intents/group-all', body: groupAllBody,
                successStatus: 202, freshness: false,
            },
            {
                label: 'intent status', browserMethod: 'GET',
                browserPath: '/sonos-intents/status',
                upstreamPath: '/intents/sonos/status',
                registration: '/sonos-intents/status', successStatus: 200,
                freshness: false,
            },
            ...SONOS_DEPRECATED_ROOT_ROUTES.map(route => ({
                label: `deprecated root ${route}`,
                browserMethod: 'GET' as const,
                browserPath: `/${route}`,
                upstreamPath: `/${route}`,
                registration: `/${route}`,
                successStatus: 200,
                freshness: false,
            })),
        ];
        const requests: Array<{
            url: string;
            options?: RequestInit;
            binary: boolean;
            maximumBytes?: number;
        }> = [];
        let activeRoute: RouteCase | null = null;
        let activeFailure = false;
        const responseHeaders = (contentType: string): Headers => new Headers({
            'content-type': contentType,
            ...(activeRoute?.freshness
                ? {
                    'x-sonos-response-source': 'home_assistant',
                    'x-sonos-response-stale': 'true',
                    'x-sonos-observed-at': '2026-08-28T12:00:00.000Z',
                    'x-sonos-age-ms': '1234',
                }
                : {}),
        });
        const responseBody = (): Buffer => Buffer.from(JSON.stringify(
            activeFailure
                ? {
                    error: `Synthetic ${activeRoute?.label} failure`,
                    code: 'synthetic_failure',
                    retryable: true,
                }
                : {ok: activeRoute?.label}
        ));
        const router: any = createSonosRouter({
            sonosUrl: 'http://sonos-api:5006',
            requestText: async (url, options) => {
                requests.push({url, options, binary: false});
                return {
                    statusCode: activeFailure ? 409 : activeRoute!.successStatus,
                    body: responseBody().toString('utf8'),
                    headers: responseHeaders('application/json; charset=utf-8'),
                };
            },
            requestBinary: async (url, options, _timeout, maximumBytes) => {
                requests.push({url, options, binary: true, maximumBytes});
                return {
                    statusCode: activeFailure ? 409 : activeRoute!.successStatus,
                    body: responseBody(),
                    headers: responseHeaders(
                        activeFailure ? 'application/json; charset=utf-8' : 'image/png'
                    ),
                };
            },
        });
        const exactHandler = (path: string, method: 'get' | 'post') => {
            const layer = router.stack.find((candidate: any) =>
                candidate.route &&
                candidate.route.path === path &&
                candidate.route.methods[method]
            );
            expect(layer, 'registered route ' + method + ' ' + path).to.exist;
            return layer.route.stack[0].handle;
        };
        const sonosHandler = router.stack.find((candidate: any) =>
            candidate.route &&
            candidate.route.path instanceof RegExp &&
            candidate.route.methods.get
        )?.route.stack[0].handle;
        expect(sonosHandler, 'registered generic /sonos route').to.exist;

        const execute = async (route: RouteCase): Promise<FakeResponse> => {
            const response = new FakeResponse();
            if (route.registration === 'generic-sonos') {
                await sonosHandler({path: route.browserPath}, response);
            } else {
                await exactHandler(
                    route.registration,
                    route.browserMethod.toLowerCase() as 'get' | 'post'
                )({params: route.params || {}, body: route.body}, response);
            }
            return response;
        };

        for (const route of routes) {
            for (const failure of [false, true]) {
                activeRoute = route;
                activeFailure = failure;
                const requestCount = requests.length;
                const expectedBody = responseBody();
                const response = await execute(route);
                const request = requests[requestCount];

                expect(request, `${route.label} upstream request`).to.exist;
                expect(requests.length, `${route.label} request count`).to.equal(
                    requestCount + 1
                );
                expect(request.url, `${route.label} encoded upstream path`).to.equal(
                    `http://sonos-api:5006${route.upstreamPath}`
                );
                expect(request.options?.method, `${route.label} upstream method`).to.equal(
                    route.browserMethod
                );
                expect(request.binary, `${route.label} binary requester`).to.equal(
                    Boolean(route.binary)
                );
                if (route.binary) {
                    expect(request.maximumBytes, `${route.label} byte ceiling`).to.equal(
                        SONOS_ARTWORK_MAX_BYTES
                    );
                }
                if (route.body !== undefined) {
                    expect(JSON.parse(String(request.options?.body))).to.deep.equal(route.body);
                } else {
                    expect(request.options?.body, `${route.label} body`).to.equal(undefined);
                }

                expect(response.statusCode, `${route.label} status`).to.equal(
                    failure ? 409 : route.successStatus
                );
                expect(response.headers.get('content-type'), `${route.label} media type`).to.equal(
                    failure || !route.binary
                        ? 'application/json; charset=utf-8'
                        : 'image/png'
                );
                const actualBytes = Buffer.isBuffer(response.body)
                    ? response.body
                    : Buffer.from(String(response.body));
                expect(
                    actualBytes.equals(expectedBody),
                    `${route.label} byte-for-byte ${failure ? 'failure' : 'success'} body`
                ).to.equal(true);
                if (failure) {
                    expect(JSON.parse(actualBytes.toString('utf8'))).to.deep.equal({
                        error: `Synthetic ${route.label} failure`,
                        code: 'synthetic_failure',
                        retryable: true,
                    });
                }
                for (const [name, value] of [
                    ['x-sonos-response-source', 'home_assistant'],
                    ['x-sonos-response-stale', 'true'],
                    ['x-sonos-observed-at', '2026-08-28T12:00:00.000Z'],
                    ['x-sonos-age-ms', '1234'],
                ]) {
                    expect(response.headers.get(name), `${route.label} ${name}`).to.equal(
                        route.freshness ? value : undefined
                    );
                }
                if (route.binary) {
                    expect(response.headers.get('x-content-type-options')).to.equal('nosniff');
                }
            }
        }
    });

    it('passes deprecated roots through for normalized 410 responses with zero writes', async () => {
        const requests: Array<{url: string; options?: RequestInit}> = [];
        const router: any = createSonosRouter({
            sonosUrl: 'http://sonos-api:5006',
            requestText: async (url, options) => {
                requests.push({url, options});
                const route = new URL(url).pathname;
                return {
                    statusCode: 410,
                    body: JSON.stringify({
                        error: `Deprecated Sonos route ${route}`,
                        code: 'deprecated_route',
                    }),
                    headers: new Headers({'content-type': 'application/json'}),
                };
            },
        });

        for (const route of SONOS_DEPRECATED_ROOT_ROUTES) {
            const layer = router.stack.find((candidate: any) =>
                candidate.route &&
                candidate.route.path === `/${route}` &&
                candidate.route.methods.get
            );
            expect(layer, 'registered deprecated route /' + route).to.exist;
            const response = new FakeResponse();
            await layer.route.stack[0].handle({}, response);
            expect(response.statusCode).to.equal(410);
            expect(JSON.parse(String(response.body))).to.deep.include({
                code: 'deprecated_route',
            });
        }

        expect(requests.map(request => ({
            path: new URL(request.url).pathname,
            method: request.options?.method,
            body: request.options?.body,
        }))).to.deep.equal(SONOS_DEPRECATED_ROOT_ROUTES.map(route => ({
            path: `/${route}`,
            method: 'GET',
            body: undefined,
        })));
    });

    it('maps registered browser intent routes to the internal aliases', async () => {
        const requests: Array<{url: string; options?: RequestInit}> = [];
        const router: any = createSonosRouter({
            sonosUrl: 'http://sonos-api:5006',
            requestText: async (url, options) => {
                requests.push({url, options});
                return {
                    statusCode: options?.method === 'POST' ? 202 : 200,
                    body: '{}',
                    headers: new Headers({'content-type': 'application/json'}),
                };
            },
        });
        const routeHandler = (path: string, method: 'get' | 'post') => {
            const layer = router.stack.find((candidate: any) =>
                candidate.route &&
                candidate.route.path === path &&
                candidate.route.methods[method]
            );
            expect(layer, 'registered route ' + method + ' ' + path).to.exist;
            return layer.route.stack[0].handle;
        };
        const payload = {targetRoom: 'Kitchen', roomNames: ['Kitchen']};

        await routeHandler('/sonos-intents/group-all', 'post')(
            {body: payload},
            new FakeResponse()
        );
        await routeHandler('/sonos-intents/status', 'get')(
            {},
            new FakeResponse()
        );

        expect(SONOS_INTENT_UPSTREAM_ROUTES).to.deep.equal({
            groupAll: 'intents/sonos/group-all',
            status: 'intents/sonos/status',
        });
        expect(requests.map(request => ({
            url: request.url,
            method: request.options?.method,
        }))).to.deep.equal([
            {
                url: 'http://sonos-api:5006/intents/sonos/group-all',
                method: 'POST',
            },
            {
                url: 'http://sonos-api:5006/intents/sonos/status',
                method: 'GET',
            },
        ]);
        expect(JSON.parse(String(requests[0].options?.body))).to.deep.equal(
            payload
        );
    });

    it('preserves JSON status, body, content type, and freshness headers', async () => {
        const upstreamUrls: string[] = [];
        const proxy = createSonosProxy({
            sonosUrl: 'http://sonos-api:5006',
            requestText: async url => {
                upstreamUrls.push(url);
                return {
                    statusCode: 206,
                    body: JSON.stringify([{members: []}]),
                    headers: new Headers({
                        'content-type': 'application/json; charset=utf-8',
                        'x-sonos-response-source': 'cache',
                        'x-sonos-response-stale': 'true',
                        'x-sonos-observed-at': '2026-08-28T12:00:00.000Z',
                        'x-sonos-age-ms': '1234',
                    }),
                };
            },
        });
        const response = new FakeResponse();

        await proxy.get('sonos/zones', response as any);

        expect(upstreamUrls).to.deep.equal([
            'http://sonos-api:5006/sonos/zones',
        ]);
        expect(response.statusCode).to.equal(206);
        expect(JSON.parse(String(response.body))).to.deep.equal([
            {members: []},
        ]);
        expect(response.headers.get('content-type')).to.equal(
            'application/json; charset=utf-8'
        );
        expect(response.headers.get('x-sonos-response-source')).to.equal(
            'cache'
        );
        expect(response.headers.get('x-sonos-response-stale')).to.equal('true');
        expect(response.headers.get('x-sonos-age-ms')).to.equal('1234');
    });

    it('preserves encoded rooms and a literal plus volume segment', async () => {
        const upstreamUrls: string[] = [];
        const proxy = createSonosProxy({
            sonosUrl: 'http://sonos-api:5006',
            requestText: async url => {
                upstreamUrls.push(url);
                return {
                    statusCode: 200,
                    body: '{}',
                    headers: new Headers({'content-type': 'application/json'}),
                };
            },
        });

        await proxy.get(
            'sonos/Living%20Room/groupVolume/%2B2',
            new FakeResponse() as any
        );
        await proxy.get(
            'same/Guest%20Bathroom',
            new FakeResponse() as any
        );

        expect(upstreamUrls).to.deep.equal([
            'http://sonos-api:5006/sonos/Living%20Room/groupVolume/%2B2',
            'http://sonos-api:5006/same/Guest%20Bathroom',
        ]);
    });

    it('forwards join-all method and body to the compatibility endpoint', async () => {
        const requests: Array<{url: string; options?: RequestInit}> = [];
        const proxy = createSonosProxy({
            sonosUrl: 'http://sonos-api:5006',
            requestText: async (url, options) => {
                requests.push({url, options});
                return {
                    statusCode: 202,
                    body: JSON.stringify({operation: {id: 'operation-1'}}),
                    headers: new Headers({'content-type': 'application/json'}),
                };
            },
        });
        const payload = {targetRoom: 'Living Room', roomNames: ['Living Room']};
        const response = new FakeResponse();

        await proxy.request(
            'POST',
            'intents/sonos/group-all',
            response as any,
            payload
        );

        expect(response.statusCode).to.equal(202);
        expect(requests[0].url).to.equal(
            'http://sonos-api:5006/intents/sonos/group-all'
        );
        expect(requests[0].options?.method).to.equal('POST');
        expect(JSON.parse(String(requests[0].options?.body))).to.deep.equal(
            payload
        );
    });

    it('preserves artwork bytes and safe response headers', async () => {
        const artwork = Buffer.from([0, 255, 1, 2, 128, 64]);
        const limits: number[] = [];
        const proxy = createSonosProxy({
            sonosUrl: 'http://sonos-api:5006',
            requestBinary: async (_url, _options, _timeout, maximumBytes) => {
                limits.push(Number(maximumBytes));
                return {
                    statusCode: 200,
                    body: artwork,
                    headers: new Headers({
                        'content-type': 'image/png',
                        'cache-control': 'private, max-age=60',
                        etag: 'artwork-version',
                        'x-sonos-response-source': 'live',
                    }),
                };
            },
        });
        const response = new FakeResponse();

        await proxy.get('sonos/Living%20Room/artwork', response as any);

        expect(limits).to.deep.equal([SONOS_ARTWORK_MAX_BYTES]);
        expect(Buffer.isBuffer(response.body)).to.equal(true);
        expect((response.body as Buffer).equals(artwork)).to.equal(true);
        expect(response.headers.get('content-type')).to.equal('image/png');
        expect(response.headers.get('cache-control')).to.equal(
            'private, max-age=60'
        );
        expect(response.headers.get('etag')).to.equal('artwork-version');
        expect(response.headers.get('x-content-type-options')).to.equal(
            'nosniff'
        );
    });

    it('rejects active SVG artwork and normalizes connection failures', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        const svgProxy = createSonosProxy({
            requestBinary: async () => ({
                statusCode: 200,
                body: Buffer.from('<svg/>'),
                headers: new Headers({'content-type': 'image/svg+xml'}),
            }),
        });
        const failureProxy = createSonosProxy({
            requestText: async () => {
                throw new Error('connection refused');
            },
        });
        const svg = new FakeResponse();
        const failed = new FakeResponse();

        await svgProxy.get('sonos/Kitchen/artwork', svg as any);
        await failureProxy.get('sonos/zones', failed as any);

        expect(svg.statusCode).to.equal(502);
        expect(svg.body).to.deep.include({
            error: 'Sonos artwork response was not a safe raster image',
            route: 'sonos/Kitchen/artwork',
        });
        expect(failed.statusCode).to.equal(502);
        expect(failed.body).to.deep.equal({
            error: 'connection refused',
            route: 'sonos/zones',
        });
    });
});
