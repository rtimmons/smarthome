const env = process.env;
const configuredLedgridUrl = env.LEDGRID_URL?.replace(/\/+$/, '');
const defaultLedgridUrl = 'http://ledgridwall5.home.arpa:5000';

const parsePort = (value: string | undefined, fallback: number): number => {
    const parsed = value ? Number(value) : NaN;
    return Number.isFinite(parsed) ? parsed : fallback;
};

export const appConfig = {
    sonosUrl: env.SONOS_BASE_URL || env.SONOS_URL || 'http://localhost:5006',
    // Supervisor retains saved options when an add-on's manifest default changes.
    ledgridUrl: !configuredLedgridUrl || configuredLedgridUrl === 'http://192.168.1.98:5000'
        ? defaultLedgridUrl
        : configuredLedgridUrl,
    webhookBase:
        env.HASS_WEBHOOK_BASE || 'http://smarterhome.local:8123/api/webhook',
    coreApiBase: 'http://supervisor/core/api',
    port: parsePort(env.PORT || env.APP_PORT, 3000),
};
