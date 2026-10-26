# Secondary Plex on Home Assistant

Created October 26, 2026 on branch `trial/plex-home-assistant`, following the
[synthetic performance trial](plex-ha-trial.md). The server is named
**Home Assistant**, available on the LAN at
[Plex Web](http://homeassistant.local:32400/web).
Community app `a0d7b954_plex` 4.1.3 runs PMS 1.43.5.11029-6bf8af3f0.
Automatic startup and watchdog are enabled. Public remote access is disabled;
the explicitly approved LAN endpoints are registered with the Plex account.

## Libraries and access

| Library | Local ID | Source roots |
| --- | --- | --- |
| Movies (hass) (Remote) | 2 | `/media/FromDrobo/Remote/files/library/Movies`, `/media/FromDrobo/Remote/files/objects/video` |
| TV Shows (hass) (Remote) | 3 | `/media/FromDrobo/Remote/files/library/TV` |

The existing `Movies & TV` managed profile is granted exactly these two libraries
on this server. Its NAS grants remain separate. The hidden synthetic trial
library (local ID 1) is not shared. No general library includes a share root,
private collection or staging directory. Never infer profile access from home
screen visibility alone; verify the account's actual section grants.

The existing HA `FromDrobo` SMB mount supplies the media. Its remote subtree is
the NAS's read-only rclone mount backed by a server-enforced read-only Storage
Box credential. The broad SMB mount itself is writable and was not altered.
Plex media deletion and automatic trash emptying are disabled. Scans run hourly;
filesystem event scanning is disabled for this network source. Initial indexing
is still in progress; header/metadata reads can produce network traffic.
A bounded 64 KiB HTTP 206 read through the new server verified media access.
It does not establish client playback, subtitle or 4K/HDR acceptance.

## Transcoding and automation

The Radeon Vega GPU is explicitly selected, with hardware decoding and encoding
enabled. The synthetic H.264 trial verified full VA-API decode/encode at a median
2.5 times real time for one 1080p-to-720p stream. Home Assistant's 50 ms script
probe had p95 58.89 ms versus idle 52.77 ms. No lights were changed; physical
automation response and unsupported codec fallback remain unqualified.

**The current configuration is not a strict one-session total cap.** PMS exposes
separate GPU and CPU limits, both set to one. The legacy `TranscodeCountLimit`
is also one but hidden in this version. A second GPU session was rejected with
HTTP 400 and the first remained active. A deliberate mixed GPU/CPU test admitted
two sessions despite those settings. Hardware acceleration was restored and both
test sessions stopped. Treat one stream as the operating target; do not promise
that Plex will reject every second video transcode. Audio-only conversions and
background optimization are separate from these video engine limits.

Quality is Automatic and the throttle buffer is 60 seconds. No custom session
killer, admission proxy or host resource limit is installed. If Core performance
deteriorates, stop only this Plex app with the dedicated HA SSH identity; never
restart Core, Z-Wave JS or NAS Plex as part of this rollback.

## Analysis reuse

The two servers do not share Plex databases or analysis results. No supported
continuous analysis-sharing mechanism was identified. Plex's documented
[installation migration](https://support.plex.tv/articles/201370363-move-an-install-to-another-system/)
requires stopping the source and copying its server data; it is not live sharing
between independently running servers. Do not mount a live Plex SQLite database
into both servers or clone the NAS's private library and identity into this one.
[Watch-state synchronization](https://support.plex.tv/articles/sync-watch-state-and-ratings/)
concerns watched state and ratings, not audio analysis.

To avoid repeating full-file downloads, loudness, voice activity, music analysis,
intro/credits/ad detection, preview/chapter thumbnails and deep analysis tasks
are disabled globally and, where supported, per library. Basic scanner analysis
and metadata retrieval still occur. Features depending on the disabled analyses
will not be available on this secondary server. The NAS's ongoing loudness
analysis was left untouched. Both servers indirectly use the NAS rclone byte
cache, but that is not analysis-data synchronization.

## Reconfiguration and recovery

`tools/plex-secondary.cjs` confines writes to the HA Plex origin, verifies exact
library roots and reads settings back. From the repository root:

```sh
just plex-secondary status /private/path/to/token-file
just plex-secondary configure /private/path/to/token-file
just plex-secondary libraries /private/path/to/token-file
just plex-secondary-test
```

Keep the credential file private; never put its value on a command line or in
Git. `configure` includes the approved LAN discovery addresses; it does not
manage Supervisor startup or Plex account grants. `libraries` refuses mismatched
existing roots and disables supported per-library analysis settings. The AMD
device-specific cap must be reviewed if hardware changes.

The initial trial-only configuration backup predates these libraries. The NAS's
settings backup does not cover this app. Recurring off-host backup coverage and
restore of the secondary database have not been verified. Preserve server state
when stopping the app; stopping is reversible and leaves NAS service intact.
