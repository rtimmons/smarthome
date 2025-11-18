# Home Assistant Ingress Fix

## Problem

The dashboard UI was unable to refresh state when accessed through Home Assistant ingress because the JavaScript was using absolute URLs based on `window.location.origin`.

**Error:**
```
http://homeassistant.local:8123/sonos/Bedroom/state
[HTTP/1.1 404 Not Found]
```

When accessed through ingress:
- UI is served at: `http://homeassistant.local:8123/api/hassio_ingress/{token}/`
- JavaScript was trying to fetch: `http://homeassistant.local:8123/sonos/...`
- Should fetch: `/api/hassio_ingress/{token}/sonos/...` (relative to current page)

## Solution

Changed the `root` parameter in `ExpressServer/src/public/js/app.js` from `window.location.origin` to `'.'` (current directory) to make all API calls use relative URLs.

**Before:**
```javascript
this.musicController = new MusicController({
    requester: this,
    root: window.location.origin,  // Absolute URL: http://homeassistant.local:8123
    app: this,
    pubsub: this.pubsub,
});
```

**After:**
```javascript
this.musicController = new MusicController({
    requester: this,
    root: '.',  // Current directory - relative to current page path
    app: this,
    pubsub: this.pubsub,
});
```

## How It Works

The MusicController builds URLs by joining the root with the route parts:

```javascript
// In music-controller.js
args = [this.root].concat(['sonos', 'Bedroom', 'state']);
var url = args.join('/');  // './sonos/Bedroom/state'
```

With `root: '.'`, URLs like `./sonos/Bedroom/state` are relative to the current page directory:

- **Direct access** (port 3000): Page at `/` → URL `./sonos/zones` → `http://localhost:3000/sonos/zones`
- **Through ingress**: Page at `/api/hassio_ingress/{token}/` → URL `./sonos/zones` → `http://homeassistant.local:8123/api/hassio_ingress/{token}/sonos/zones`

**Why not use `root: ''` (empty string)?**
- With empty root: `[''].concat(['sonos', 'zones']).join('/')` = `'/sonos/zones'`
- Leading `/` makes it absolute to domain root, not relative to current path
- Results in: `http://homeassistant.local:8123/sonos/zones` (wrong!)

**Why `root: '.'` works:**
- With dot root: `['.'].concat(['sonos', 'zones']).join('/')` = `'./sonos/zones'`
- `./` makes it relative to current directory
- Results in: `http://homeassistant.local:8123/api/hassio_ingress/{token}/sonos/zones` (correct!)

## Testing

### 1. Access Dashboard Through Ingress

Open Home Assistant web interface and click "Grid Dashboard" in the sidebar:
```
http://homeassistant.local:8123
```

### 2. Check Browser Network Tab

Open browser DevTools → Network tab and interact with the dashboard (click VolumeUp, etc.)

You should see API calls to paths like:
```
/api/hassio_ingress/{token}/sonos/Bedroom/groupVolume/+2
```

These should return **200 OK** instead of **404 Not Found**.

### 3. Test State Refresh

The dashboard should automatically refresh Sonos state every few seconds. Check the Network tab for requests to:
```
/api/hassio_ingress/{token}/sonos/Bedroom/state
/api/hassio_ingress/{token}/sonos/zones
```

## Files Modified

- `ExpressServer/src/public/js/app.js` (lines 15, 23, 31)
  - Changed `root: window.location.origin` to `root: '.'`
  - Applied to MusicController, LightController, and BlindControllerI2C

## Complete Routing Chain (with Ingress)

```
User clicks VolumeUp in Dashboard UI (accessed via ingress)
          ↓
Browser makes request:
  /api/hassio_ingress/{token}/sonos/Bedroom/groupVolume/+2
          ↓
Home Assistant ingress proxy forwards to:
  http://local-grid-dashboard:3000/sonos/Bedroom/groupVolume/+2
          ↓
Grid Dashboard add-on proxies to:
  http://local-sonos-api:5006/sonos/Bedroom/groupVolume/+2
          ↓
Sonos API add-on proxies to:
  http://local-node-sonos-http-api:5005/Bedroom/groupVolume/+2
          ↓
Node Sonos HTTP API executes command
          ↓
Response flows back through the chain
```

## Deployment

Already deployed! The fix is now live on your Home Assistant instance.

```bash
# If you need to redeploy:
cd /Users/rtimmons/Projects/smarthome/grid-dashboard
just deploy
```
