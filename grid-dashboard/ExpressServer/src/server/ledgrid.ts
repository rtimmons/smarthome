import { setTimeout as delay } from 'node:timers/promises';
import { Router, type Response } from 'express';
import { appConfig } from './config';
import { requestText } from './http';

const app = Router();
const api = `${appConfig.ledgridUrl}/api/v1/automation`;
const commands = `${api}/commands`;
const animations = new Map([
    ['rainbow', 'animation:python:rainbow:v1'],
    ['sparkle', 'animation:python:sparkle:v1'],
    ['tetris', 'animation:python:tetris:v1'],
]);

type WallCommand =
    | { action: 'play_content'; content_id: string }
    | { action: 'set_device_state'; power: false };

async function requestWall(url: string, options: RequestInit = {}) {
    const response = await requestText(
        url, { ...options, redirect: 'error' }, 5000
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
        const data = response.headers.get('content-type')?.includes('application/json')
            ? JSON.parse(response.body)
            : undefined;
        throw new Error(data?.error || `LED wall returned HTTP ${response.statusCode}`);
    }
    // Wall command IDs are nanosecond timestamps. Preserve the JSON digits for correlation.
    return JSON.parse(response.body, (key, value, context?: { source?: string }) =>
        key === 'command_id' && typeof value === 'number' ? context?.source : value
    );
}

async function controlWall(command: WallCommand, res: Response) {
    res.set('Cache-Control', 'no-store');
    try {
        const status = await requestWall(`${api}/status`);
        if (
            status?.schema !== 'ledgrid.automation-status' ||
            status.schema_version !== 1 || status.fresh !== true ||
            typeof status.server_session_id !== 'string' || !status.server_session_id ||
            typeof status.controller_session_id !== 'string' || !status.controller_session_id ||
            !Number.isSafeInteger(status.controller_state_revision) ||
            (command.action === 'play_content' && !Number.isSafeInteger(status.composer_revision))
        ) {
            throw new Error('LED wall has no fresh controller status');
        }

        // Leave a margin for transit and clock skew within the wall's ten-second limit.
        const expiresAt = Date.now() + 9000;
        const receipt = await requestWall(commands, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...command,
                expected_server_session_id: status.server_session_id,
                expected_controller_session_id: status.controller_session_id,
                expected_controller_state_revision: status.controller_state_revision,
                expires_at: expiresAt / 1000,
                ...(command.action === 'play_content'
                    ? { expected_composer_revision: status.composer_revision }
                    : {}),
            }),
        });
        if (
            receipt?.schema !== 'ledgrid.automation-command' || receipt.schema_version !== 1 ||
            receipt.state !== 'accepted' || typeof receipt.command_id !== 'string' ||
            !/^\d+$/.test(receipt.command_id) ||
            typeof receipt.request_id !== 'string' ||
            !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(receipt.request_id)
        ) {
            throw new Error('LED wall returned an invalid command receipt');
        }

        // A write is sent once. Only poll the matching receipt, which also reconciles Composer.
        const resultUrl = `${commands}/${receipt.request_id}?wait_seconds=2`;
        const signal = AbortSignal.timeout(11000);
        while (!signal.aborted) {
            const result = await requestWall(resultUrl, { signal });
            if (
                result?.schema !== receipt.schema || result.schema_version !== receipt.schema_version ||
                result.request_id !== receipt.request_id || result.command_id !== receipt.command_id
            ) {
                throw new Error('LED wall returned a mismatched command receipt');
            }
            if (result.state === 'accepted') {
                await delay(100);
                continue;
            }
            if (result.state !== 'completed') {
                throw new Error(result.error || 'LED wall command failed');
            }
            if (
                result.controller_session_id !== status.controller_session_id ||
                result.controller_state_revision !== status.controller_state_revision + 1
            ) {
                throw new Error('LED wall acknowledged a different controller revision');
            }
            if (command.action === 'play_content' && result.reconciliation?.state !== 'completed') {
                throw new Error(result.reconciliation?.error || 'LED wall could not update Composer');
            }
            res.json({ success: true, command_id: result.command_id });
            return;
        }
        throw new Error('LED wall command acknowledgement timed out');
    } catch (err) {
        const message = err instanceof Error ? err.message : 'LED wall request failed';
        console.error('LED wall control failed:', message);
        res.status(502).json({ error: message });
    }
}

app.post('/ledgrid/start/:animation', (req, res) => {
    const contentId = animations.get(req.params.animation);
    if (!contentId) {
        res.status(400).json({ error: 'Unknown LED wall animation' });
        return;
    }
    return controlWall({ action: 'play_content', content_id: contentId }, res);
});

app.post('/ledgrid/stop', (_req, res) =>
    controlWall({ action: 'set_device_state', power: false }, res)
);

export const ledgrid = app;
