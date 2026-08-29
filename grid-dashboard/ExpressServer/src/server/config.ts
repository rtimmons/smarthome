const env = process.env;

const parsePort = (value: string | undefined, fallback: number): number => {
    const parsed = value ? Number(value) : NaN;
    return Number.isFinite(parsed) ? parsed : fallback;
};

export const appConfig = {
    sonosUrl: env.SONOS_BASE_URL || env.SONOS_URL || 'http://localhost:5006',
    ledgridUrl: env.LEDGRID_URL || 'http://ledwallleft.local:5000',
    webhookBase:
        env.HASS_WEBHOOK_BASE || 'http://smarterhome.local:8123/api/webhook',
    coreApiBase: 'http://supervisor/core/api',
    port: parsePort(env.PORT || env.APP_PORT, 3000),
};
