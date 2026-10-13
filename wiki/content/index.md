# A field guide to the house

Use this guide to understand the house, find the right application, and decide where to look when something stops working.

## Everyday tasks

| I want to… | Start here |
| --- | --- |
| Change a room’s lighting | [Dashboard and controls](dashboard.md), then [lighting](lighting.md) |
| Play music or change speaker groups | [Audio](audio.md) |
| Check temperature or a camera snapshot | [Climate and cameras](integrations.md) |
| Print a label | [Printing](printing.md) |
| Request or watch something | [Media and storage](media/usenet.md) |
| Troubleshoot a name or connection | [Network](network.md) |
| Deploy, back up, or recover a component | [Maintenance](maintenance.md) |

## Open the right application

- [Home Assistant](http://192.168.1.163:8123/) — use its sidebar for the dashboard and installed apps.
- [Seerr](http://10.77.0.1:15055/) — explicit movie and TV requests, using Plex sign-in.
- [Plex](http://192.168.1.66:32400/web) — choose the appropriate NAS or Remote library.
- [NAS copies](http://192.168.1.66:1337/) — selectively copy canonical media to local storage.

These links retain the applications’ own access controls. A Home Assistant ingress address contains a session identifier: obtain it through the sidebar rather than bookmarking or publishing it here.

## How the pieces connect

```text
Room controls / Grid Dashboard
    ├── Home Assistant → lighting, Z-Wave, ESPHome, Nest
    ├── Sonos API → Home Assistant Sonos integration → speakers
    ├── Printer service → label printer
    └── Snapshot / TinyURL services → cameras and utility links

Seerr → Radarr / Sonarr → SABnzbd → canonical Storage Box
                                      ├── Plex Remote playback
                                      └── selected NAS copies → Plex NAS playback

UniFi connects the devices. Local DNS names the wiki.
The QNAP serves this guide independently of Home Assistant Core.
```

## What this guide knows

[Generated reference tables](wiki-reference:inventory) describe repository configuration, including disabled services and excluded devices. Dated runbooks explain what was observed. A successful build is not evidence that a device is currently online.

The wiki has no live controls, media listings, application credentials, or application API access. If a service fails, begin with the owning component’s read-only checks and preserve the failure evidence.
