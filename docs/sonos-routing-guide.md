# Sonos Add-on Routing Guide

This document explains the complete routing chain for Sonos control through the three Home Assistant add-ons.

## Architecture Overview

```
User clicks VolumeUp in Dashboard UI
          ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Grid Dashboard Add-on (local-grid-dashboard:3000)       │
│    • Frontend: Music.VolumeUp action                        │
│    • JavaScript: musicController.volumeUp()                 │
│    • Builds URL: /sonos/Bedroom/groupVolume/+2             │
│    • Backend: ExpressServer/src/server/sonos.ts            │
│    • Proxies to: http://local-sonos-api:5006/sonos/...     │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Sonos API Add-on (local-sonos-api:5006)                 │
│    • Receives: /sonos/Bedroom/groupVolume/+2               │
│    • Route: /sonos/(.*) regex in sonos-api/src/server/     │
│    • Extracts: Bedroom/groupVolume/+2                      │
│    • Proxies to: http://local-node-sonos-http-api:5005/... │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Node Sonos HTTP API Add-on (local-node-sonos-http-api:5005) │
│    • Receives: /Bedroom/groupVolume/+2                     │
│    • Executes actual Sonos SSDP/UPnP commands             │
│    • Returns response back through the chain               │
└─────────────────────────────────────────────────────────────┘
                  ↓
            Sonos Speakers
```

## Configuration

### 1. Node Sonos HTTP API
**Port:** 5005
**Config:** None required
**Default:** `http://local-node-sonos-http-api:5005`

### 2. Sonos API
**Port:** 5006
**Config:** `sonos_base_url: http://local-node-sonos-http-api:5005`
**Purpose:** Proxies to node-sonos-http-api and adds custom routes like `/up`, `/down`, `/same/:room`

### 3. Grid Dashboard
**Port:** 3000 (ingress)
**Config:** `sonos_base_url: http://local-sonos-api:5006`
**Purpose:** UI for dashboard, proxies Sonos commands to sonos-api

## Hostname Resolution

Home Assistant add-ons communicate using the container hostname format:
- Slug: `node_sonos_http_api` → Hostname: `local-node-sonos-http-api`
- Slug: `sonos_api` → Hostname: `local-sonos-api`
- Slug: `grid_dashboard` → Hostname: `local-grid-dashboard`

**Important:** Local add-ons use the `local-` prefix in their hostnames!

## Testing the Routing Chain

### From Outside Home Assistant (port 5005 is exposed):
```bash
# Direct access to node-sonos-http-api
curl http://homeassistant.local:5005/zones
curl http://homeassistant.local:5005/Bedroom/state
```

### From Inside Home Assistant (SSH into host):
```bash
# Test each layer
ssh root@homeassistant.local

# Layer 3: node-sonos-http-api directly
curl http://local-node-sonos-http-api:5005/zones

# Layer 2: through sonos-api
curl http://local-sonos-api:5006/health
curl http://local-sonos-api:5006/sonos/zones

# Layer 1: through grid-dashboard (full chain)
curl http://local-grid-dashboard:3000/sonos/zones
curl http://local-grid-dashboard:3000/sonos/Bedroom/state
```

## Example: VolumeUp Button Flow

When a user clicks the VolumeUp button in the Grid Dashboard:

1. **Frontend** (`music-controller.js:29-31`):
   ```javascript
   volumeUp() {
       this.request('sonos', '$room', 'groupVolume', '+2');
   }
   ```
   Builds URL: `/sonos/Bedroom/groupVolume/+2`

2. **Grid Dashboard Backend** (`ExpressServer/src/server/sonos.ts:27-38`):
   ```typescript
   const rex: RegExp = /sonos\/(.*)$/;
   app.get(rex, (req: RQ, res: RS) => {
       const rest = match[1]; // "Bedroom/groupVolume/+2"
       return sonosPipe(`sonos/${rest}`, req, res);
   });
   ```
   Proxies to: `http://local-sonos-api:5006/sonos/Bedroom/groupVolume/+2`

3. **Sonos API** (`sonos-api/src/server/sonos.ts:27-37`):
   ```typescript
   const rex: RegExp = /sonos\/(.*)$/;
   app.get(rex, (req: RQ, res: RS) => {
       const rest = match[1]; // "Bedroom/groupVolume/+2"
       return sonosPipe(rest, req, res);
   });
   ```
   Proxies to: `http://local-node-sonos-http-api:5005/Bedroom/groupVolume/+2`

4. **Node Sonos HTTP API**: Executes the actual command to increase Bedroom volume by 2

## Custom Routes

The Sonos API add-on provides these custom convenience routes that are available to the Grid Dashboard:

- `/pause` - Pause playback
- `/play` - Resume playback
- `/tv` - Switch all speakers to TV mode
- `/07` - Play Zero 7 Radio
- `/quiet` - Set group volume to 7
- `/same/:room` - Sync all volumes in a room's zone
- `/down` - Smart volume down (pause if volume <= 3 and playing)
- `/up` - Smart volume up (play if paused, otherwise increase volume)
- `/sonos/*` - Proxy any request to node-sonos-http-api
- `/health` - Health check endpoint

## Deployment

To deploy all three add-ons:

```bash
# 1. Build and deploy node-sonos-http-api
cd node-sonos-http-api
just deploy

# 2. Build and deploy sonos-api
cd ../sonos-api
just deploy

# 3. Build and deploy grid-dashboard
cd ../grid-dashboard
just deploy
```

## Troubleshooting

### Add-on can't resolve hostname
- **Problem:** `getaddrinfo ENOTFOUND node-sonos-http-api`
- **Solution:** Use the full hostname with `local-` prefix (e.g., `local-node-sonos-http-api`)

### Configuration not updating
- **Problem:** Changes to build scripts don't reflect in running add-ons
- **Solution:** Reinstall the add-on to pick up new default config:
  ```bash
  ssh root@homeassistant.local
  ha addons stop local_sonos_api
  ha addons uninstall local_sonos_api
  ha addons reload
  ha addons install local_sonos_api
  ha addons start local_sonos_api
  ```

### Port not accessible
- **Problem:** Can't access add-on on its port from outside
- **Solution:** Ports 5005 is exposed externally. Ports 5006 and 3000 use internal networking only. Grid Dashboard uses ingress for UI access.

## Files Modified

### grid-dashboard/scripts/build_ha_addon.sh
- Changed default `sonos_base_url` from `http://node-sonos-http-api:5005` to `http://local-sonos-api:5006`

### sonos-api/scripts/build_ha_addon.sh
- Changed default `sonos_base_url` to use `http://local-node-sonos-http-api:5005`

### ExpressServer/src/server/sonos.ts
- Updated proxy route to include `/sonos/` prefix when forwarding
- Removed duplicate `/up`, `/down`, `/same/:room` routes (now handled by sonos-api)
