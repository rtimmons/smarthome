# Plex on Home Assistant

Established October 26, 2026 as an ongoing household Plex server after user
acceptance. The [initial performance evaluation](plex-ha-trial.md) remains
historical evidence, not the current deployment status. The server is named
**Home Assistant**, available on the LAN at
[Plex Web](http://homeassistant.local:32400/web).
Community app `a0d7b954_plex` 4.1.3 runs PMS 1.43.5.11029-6bf8af3f0.
Automatic startup and watchdog are enabled. Public remote access is disabled;
the explicitly approved LAN endpoints are registered with the Plex account.
`LanNetworksBandwidth=192.168.1.0/255.255.255.0` explicitly classifies the home
subnet as local. This is a bandwidth classification, not an authentication bypass.

## Libraries and access

| Library | Local ID | Source roots |
| --- | --- | --- |
| Movies (hass) (Remote) | 2 | `/media/FromDrobo/Remote/files/library/Movies`, `/media/FromDrobo/Remote/files/objects/video` |
| TV Shows (hass) (Remote) | 3 | `/media/FromDrobo/Remote/files/library/TV` |

The existing `Movies & TV` managed profile is granted exactly these two libraries
on this server. Its NAS grants remain separate. The hidden `Synthetic Diagnostics`
library (local ID 1) is not shared. No general library includes a share root,
private collection or staging directory. Never infer profile access from home
screen visibility alone; verify the account's actual section grants.

The existing HA `FromDrobo` SMB mount supplies the media. Its remote subtree is
the NAS's read-only rclone mount backed by a server-enforced read-only Storage
Box credential. The broad SMB mount itself is writable and was not altered.
Plex media deletion and automatic trash emptying are disabled. Scans run hourly;
filesystem event scanning is disabled for this network source. Initial setup
required indexing; future scans and header/metadata reads can produce network traffic.
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

### Roku first-play delay and thermal evidence — October 26

The user reported a roughly 30-second first-start delay and timeout, followed
by a better retry. The observed session Direct Played 4K HEVC/MKV at about
83 Mbps; it was not a GPU video transcode. Around 17:26–17:29 EDT, metadata
requests took 8.8–15.1 seconds, artwork requests reached 58.5 seconds, and one
upstream artwork fetch timed out. No analysis-version upgrade was established
for this incident. These observations do not isolate a single cause of every
playback delay; high-bitrate remote-media reads also remain relevant.

Subsequent read-only host samples found all four cores near 399 MHz under load,
versus a requested 2.3 GHz and configured 1.6–2.3 GHz range. The `k10temp` CPU
sensor reported 88.5–88.75°C and `amdgpu` 88°C. Host CPU idle was 2%, with
substantial CPU pressure. The generic ACPI readings of 33°C and 10°C did not
represent these CPU/GPU sensor readings. The user confirmed a poorly ventilated
closet. This strongly suggests hardware throttling, but the available host log
did not contain an explicit thermal event; another firmware/power constraint
has not been excluded. Cooler temperatures accompanied by clock recovery would
provide stronger causal evidence. Do not override thermal protection or force
higher clocks as a playback workaround.

At 17:48 EDT, three samples showed CPU temperature 85.4–85.5°C, GPU temperature
85°C and effective clocks of 1.60–2.55 GHz. Ten-second CPU pressure fell to about
1%. The severe clock collapse had cleared in that window, although sustained
thermal headroom remained unqualified.

The short synthetic trials did not establish sustained thermal capacity. Restore
airflow/cooling and verify effective clocks before more transcode load tests.
The device-free probe now captures hardware temperature sensor names/readings
(millidegrees Celsius) and per-core clock readings (kHz) with each host sample.
It remains an observer, not an automatic thermal watchdog.

Plex also classified the Roku's `192.168.1.x` address as WAN because the app uses
a container network. The verified home subnet was added to `LanNetworksBandwidth`
without changing authentication, remote publishing or stopping playback.
An existing session can retain its prior classification. A fresh Roku playback
attempt after cooling is still needed to verify startup improvement and local
classification; the setting readback alone is not playback acceptance.

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

## Possible future NAS retirement

The HA deployment is established; retiring the NAS-hosted general Plex libraries
is a future option, not a scheduled or authorized cutover. Keep both available
until that decision. If the NAS libraries are retired:

- Re-enable the desired media analysis on HA, including loudness and the other
  deliberately disabled features, in both server and library preferences. Update
  `tools/plex-secondary.cjs` so reconfiguration does not turn them off again.
  Plan for remote reads and verify cooling before running the backlog; existing
  NAS analysis does not automatically transfer to the independent HA database.
- Move Jellyfin and its Moonfin plugin/web experience to the HA machine as well.
  Preserve accounts, AD login, watched state, libraries, Moonfin's Seerr linkage
  and recovery data. Verify Roku and other native clients before retiring NAS services.
- Update the Jellyfin/Moonfin DNS and reverse-proxy destinations as appropriate:
  `jellyfin.home.rytim.com`, `jellyfin.home.arpa`, `moonfin.home.arpa`, and affected
  Plex or other service names. Preserve existing public-facing names where useful;
  a proxy upstream change may suffice without changing its DNS record. Keep TLS,
  streaming paths and native-client authentication working.
- Repoint Seerr availability/library synchronization and any Arr notifications,
  recovery checks and saved clients that still target NAS Plex or Jellyfin.
  Verify managed-profile grants and backups/restores on the replacement hosts.

Retiring NAS media-server libraries does not retire NAS storage: HA currently
reads through its SMB share and remote-media mount/cache. Preserve that path
until a separately verified replacement exists. Private NAS content and grants
remain outside the general-library retirement scope. The current NAS Jellyfin
layout is documented in the [Jellyfin/Moonfin runbook](../../usenet-infra/docs/jellyfin-trial.md).

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
