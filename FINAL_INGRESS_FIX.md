# Final Ingress Fix - Double Slash Issue

## Problem

The dashboard was creating URLs with **double slashes** when accessed through Home Assistant ingress, resulting in **502 Bad Gateway** errors:

```
http://homeassistant.local:8123/api/hassio_ingress/{token}//sonos/Living/state
                                                          ^^
                                                     Double slash!
```

## Root Cause

The URL building logic in `music-controller.js` was:

```javascript
args = [this.root].concat(args);
var url = args.join('/');
```

When `root` was set to `'.'`:
- `['.', 'sonos', 'Living', 'state'].join('/')` = `'./sonos/Living/state'`
- Browser resolves relative to current path: `/api/hassio_ingress/{token}/`
- Result: `/api/hassio_ingress/{token}//sonos/Living/state` (double slash!)

When `root` was set to `''` (empty string):
- `['', 'sonos', 'Living', 'state'].join('/')` = `'/sonos/Living/state'`
- Leading `/` makes it absolute to domain root (wrong path!)

## Solution

**Two-part fix:**

### 1. Modified URL building logic in `music-controller.js`

Changed the request method to only include root if it's not empty:

```javascript
// Before
args = [this.root].concat(args);
var url = args.join('/');

// After
var url = this.root ? [this.root].concat(args).join('/') : args.join('/');
```

### 2. Set root to empty string in `app.js`

```javascript
this.musicController = new MusicController({
    requester: this,
    root: '', // Empty root
    app: this,
    pubsub: this.pubsub,
});
```

## How It Works Now

With `root: ''` and the updated logic:

```javascript
// root is empty, so:
var url = args.join('/');  // ['sonos', 'Living', 'state'].join('/')
// Result: 'sonos/Living/state'
```

This creates a **relative URL without leading slash**, which resolves correctly:

**Through ingress:**
- Page: `http://homeassistant.local:8123/api/hassio_ingress/{token}/`
- URL: `sonos/Living/state` (no leading slash)
- Resolves to: `http://homeassistant.local:8123/api/hassio_ingress/{token}/sonos/Living/state` ✓

**Direct access:**
- Page: `http://localhost:3000/`
- URL: `sonos/Living/state`
- Resolves to: `http://localhost:3000/sonos/Living/state` ✓

## Files Modified

1. **ExpressServer/src/public/js/music-controller.js** (line 15)
   - Updated URL building to skip empty root values

2. **ExpressServer/src/public/js/app.js** (lines 15, 23, 31)
   - Changed `root: '.'` to `root: ''`
   - Applied to MusicController, LightController, and BlindControllerI2C

## Testing

Access the dashboard through Home Assistant ingress and check the browser Network tab:

**Before (broken):**
```
GET /api/hassio_ingress/{token}//sonos/zones
Status: 502 Bad Gateway
```

**After (fixed):**
```
GET /api/hassio_ingress/{token}/sonos/zones
Status: 200 OK
```

No more double slashes, no more 502 errors!

## Complete Routing Flow

```
User clicks VolumeUp in Dashboard UI
          ↓
Browser makes request: sonos/Living/groupVolume/+2
          ↓
Resolves to: /api/hassio_ingress/{token}/sonos/Living/groupVolume/+2
          ↓
Home Assistant ingress proxy forwards to:
  http://local-grid-dashboard:3000/sonos/Living/groupVolume/+2
          ↓
Grid Dashboard proxies to:
  http://local-sonos-api:5006/sonos/Living/groupVolume/+2
          ↓
Sonos API proxies to:
  http://local-node-sonos-http-api:5005/Living/groupVolume/+2
          ↓
Node Sonos HTTP API executes Sonos command
          ↓
Success! Volume increased by 2
```

## Summary

The dashboard state refresh now works correctly through Home Assistant ingress. All API calls use relative URLs (without leading slashes) that resolve properly to the ingress path, avoiding both the double slash issue and the domain root problem.
