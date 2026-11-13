import type { Request, Response } from 'express';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { appConfig } from './config';
import { ledgrid } from './ledgrid';

const api = `${appConfig.ledgridUrl}/api/v1/automation`;
const status = {
    schema: 'ledgrid.automation-status', schema_version: 1, fresh: true,
    server_session_id: 'web-session', controller_session_id: 'wall-session',
    controller_state_revision: 7, composer_revision: 12,
};
const accepted = {
    schema: 'ledgrid.automation-command', schema_version: 1, state: 'accepted',
    request_id: '12345678-1234-1234-1234-123456789abc', command_id: '1794593801000000001',
};
const completed = {
    ...accepted, state: 'completed', controller_session_id: 'wall-session',
    controller_state_revision: 8, reconciliation: { state: 'completed' },
};

function receiptResponse<T extends typeof accepted>(receipt: T, statusCode = 200) {
    const { command_id, ...fields } = receipt;
    const body = JSON.stringify(fields);
    return new Response(`${body.slice(0, -1)},"command_id":${command_id}}`, { status: statusCode });
}

async function start(animation: string) {
    const res = {
        set: vi.fn(),
        status: vi.fn().mockReturnThis(),
        json: vi.fn(),
    };
    const route = ledgrid.stack.find(layer => layer.route?.path === '/ledgrid/start/:animation');
    await route!.route!.stack[0].handle(
        { params: { animation } } as unknown as Request,
        res as unknown as Response,
        vi.fn()
    );
    return res;
}

describe('LED wall animation route', () => {
    afterEach(() => vi.unstubAllGlobals());

    it.each(['rainbow', 'sparkle', 'tetris'])('plays %s with fresh guards and waits for completion', async animation => {
        const fetch = vi.fn<typeof globalThis.fetch>()
            .mockResolvedValueOnce(Response.json(status))
            .mockResolvedValueOnce(receiptResponse(accepted, 202))
            .mockResolvedValueOnce(receiptResponse(accepted))
            .mockResolvedValueOnce(receiptResponse(completed));
        vi.stubGlobal('fetch', fetch);

        const res = await start(animation);

        const resultUrl = `${api}/commands/${accepted.request_id}?wait_seconds=2`;
        expect(fetch.mock.calls.map(([url]) => url)).toEqual([
            `${api}/status`, `${api}/commands`, resultUrl, resultUrl,
        ]);
        const write = fetch.mock.calls[1][1]!;
        expect(write.method).toBe('POST');
        expect(JSON.parse(write.body as string)).toEqual({
            action: 'play_content', content_id: `animation:python:${animation}:v1`,
            expected_server_session_id: 'web-session', expected_controller_session_id: 'wall-session',
            expected_controller_state_revision: 7, expected_composer_revision: 12,
            expires_at: expect.any(Number),
        });
        expect(res.json).toHaveBeenCalledWith({ success: true, command_id: accepted.command_id });
    });

    it('leaves the wall untouched for an unknown picker or stale status', async () => {
        const fetch = vi.fn().mockResolvedValue(Response.json({ ...status, fresh: false }));
        vi.stubGlobal('fetch', fetch);
        expect((await start('unknown')).status).toHaveBeenCalledWith(400);
        expect(fetch).not.toHaveBeenCalled();

        expect((await start('rainbow')).status).toHaveBeenCalledWith(502);
        expect(fetch).toHaveBeenCalledTimes(1);
    });

    it('surfaces a reconciliation conflict without repeating the write', async () => {
        const fetch = vi.fn<typeof globalThis.fetch>()
            .mockResolvedValueOnce(Response.json(status))
            .mockResolvedValueOnce(receiptResponse(accepted, 202))
            .mockResolvedValueOnce(receiptResponse({
                ...completed, reconciliation: { state: 'conflict', error: 'Composer changed' },
            }));
        vi.stubGlobal('fetch', fetch);

        const res = await start('sparkle');

        expect(res.status).toHaveBeenCalledWith(502);
        expect(res.json).toHaveBeenCalledWith({ error: 'Composer changed' });
        expect(fetch).toHaveBeenCalledTimes(3);
    });

    it('distinguishes command IDs that round to the same JavaScript number', async () => {
        const fetch = vi.fn<typeof globalThis.fetch>()
            .mockResolvedValueOnce(Response.json(status))
            .mockResolvedValueOnce(receiptResponse(accepted, 202))
            .mockResolvedValueOnce(receiptResponse({ ...completed, command_id: '1794593801000000002' }));
        vi.stubGlobal('fetch', fetch);

        expect((await start('rainbow')).json).toHaveBeenCalledWith({
            error: 'LED wall returned a mismatched command receipt',
        });
    });
});
