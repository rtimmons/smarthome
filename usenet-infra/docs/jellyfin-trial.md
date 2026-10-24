# Jellyfin NAS trial

Jellyfin runs alongside Plex at `http://192.168.1.66:8096/`. Use the separate
Jellyfin account, whose private login is saved in
`usenet-infra/secrets/jellyfin/operator.json` on the maintainer's checkout.
The private library is neither mounted nor indexed. Seerr continues to use its
existing Plex login and availability source.

## Deployment boundaries

The official Jellyfin 12.3 image is pinned by digest in
`compose/jellyfin/compose.yaml`. Its separate Compose project is
`usenet-jellyfin-trial`; persistent state is under
`/share/Container/usenet/jellyfin-trial`. The four libraries match the general
Plex library scopes: Movies and TV Shows, each with NAS and Remote sources.
All five source mounts are read-only, exclude staging, and refuse automatic
creation of missing host paths. The existing canonical reader remains read-only.

The container is limited to one CPU and 1 GiB RAM. Its root filesystem is
read-only, privilege escalation is disabled, and all capabilities are dropped
except `DAC_READ_SEARCH`: QNAP ACLs otherwise hide the local media directories.
It runs as root with group 100 because QTS exposes the Intel render device with
mode 0600. This grants access within its explicit mounts; it receives no Docker
socket, host network, host root, credentials directory, or private media mount.
No host ACLs or device permissions were changed.

VA-API uses `/dev/dri/renderD128`; H.264 and HEVC decoding/encoding are supported
by the installed driver. AV1 hardware decoding and HDR tone mapping are not
enabled. Successful driver discovery alone does not establish every playback
combination. Large scans compete for NAS resources, even with these limits.

The wizard was configured through NAS-local API calls before publishing the
LAN listener. Remote access, automatic port mapping, content deletion and public
sharing are disabled. No router forwarding or cloud firewall opening was added.
Hourly library scans cover the remote filesystem, where file watches are not
reliable. Chapter thumbnails, trickplay, keyframe extraction, audio normalization
and media-segment scan schedules are disabled for this resource-limited trial.
Metadata is stored separately from the read-only media.

```sh
just usenet jellyfin-status
just usenet configure-jellyfin
just usenet jellyfin-stop
```

Reconciliation requires an already-completed wizard, the exact saved LAN bind,
and the mounted read-only remote filesystem. It updates only Jellyfin, retaining
the previous Compose file. Stopping retains all application state and does not
affect Plex, Seerr, downloads, imports or the remote mount. For an image rollback,
restore the corresponding application-state checkpoint as well as the prior
image; never run an older image against a newly migrated database.

A fresh installation requires private account creation and review of the saved
library/settings policy before LAN publication. The reconciliation recipe
intentionally does not invent a password or expose an unfinished wizard.

## Request and import pipeline

In Jellyfin Web, select **Request movies & TV** in the top navigation bar
(or the navigation menu on narrower screens).
This opens the existing Seerr portal; sign in with the existing Plex account,
search for a movie or show, and choose **Request** (select the intended seasons
for TV). The portal retains its existing permissions and request history.
Jellyfin credentials are separate and cannot sign in to this Plex-mode portal.
The link uses Jellyfin's supported `menuLinks` web configuration, mounted
read-only from `web-config.json`; it survives container recreation. Refresh the
browser after deployment. Native TV clients may not expose web menu links;
use the portal from a phone or browser in that case. Both addresses require
access to the home network. No API keys are embedded in the web configuration.

The existing complete pipeline also supplies Jellyfin:

```text
Seerr -> Radarr/Sonarr -> Prowlarr -> indexers
                   -> SABnzbd -> canonical Storage Box library
                             -> NAS read-only mount -> Plex + Jellyfin
```

Seerr supports Jellyfin library scans, availability and user authentication.
The installed Seerr instance selects one primary media-server mode and currently
uses Plex. Adding a second player does not require migrating requests or changing
acquisition. A portal migration needs separate verification of existing users,
requests, availability and the Plex-specific recovery monitor; it is not part of
this parallel player trial.

The installed Radarr and Sonarr expose a `MediaBrowser` (Emby-compatible)
connection with API key, library-update and path-mapping fields. This can notify
Jellyfin after imports and renames. Their `/library` paths differ from Jellyfin's
`/media/movies-remote` and `/media/tv-remote` paths, so a future event connection
must map those paths and test a real imported item. The cloud-to-NAS route and
firewall also need explicit verification for port 8096. No untested event
connection is enabled; the hourly scan is the deployed discovery mechanism.

Jellyfin does not search NZB indexers or acquire releases. Prowlarr remains the
indexer owner, Radarr/Sonarr remain acquisition/import owners, and SAB remains
the downloader. No extra all-in-one installer or duplicate acquisition stack is
needed. RSS polling, watchlist acquisition, automatic upgrades, request scope,
quality policy, reserves and manual pauses remain unchanged.

## Moonfin requests

Moonbase 2.4.0.0 is installed from the official Moonfin plugin catalog, with
the release checksum verified. The downloaded archive's SHA-256 is
`2dadff3d8f4f797e18b394bf9825173f9bc2f49022d6a0220ef5fb6eb4fbd35b`.
Moonfin Web is served at `http://192.168.1.66:8096/Moonfin/Web/`; clients use
the same Jellyfin account and server address as the stock client.
Settings sync and Seerr are enabled. The plugin proxies Seerr over the existing
private route, keeping session cookies on the NAS. No Seerr API key is sent to
clients and no new firewall port is opened. Optional chart fetching, studio-logo
fetching, WebRTC discovery and the replacement recommendation provider are off.

The user approved local Seerr login for a dedicated Moonfin account; existing
Plex login and availability remain. Its permissions are exactly REQUEST plus
AUTO_APPROVE (160), allowing explicit requests without administration, advanced
routing, watchlist acquisition or separate 4K-copy access. Credentials are in
ignored `usenet-infra/secrets/moonfin/seerr.json`, mode 0600. Cloud escrow under
`config/seerr/moonfin-operator` is included in Seerr's settings backup scope.

The session is bound to the existing Jellyfin operator account, so clients using
that account can reuse it. In Moonfin Roku, enable **Settings → Moonfin Plugin →
Enable Plugin**, then **Seerr → Enable Seerr**. If a new sign-in is needed, use
**Local**, not Jellyfin, with the dedicated Seerr credentials. Roku installation,
control access and on-device playback were deferred by the user; do not describe
them as agent-verified. The stock Jellyfin Roku app does not gain these controls.

Moonbase 2.4.0 caches missing permissions as zero from Seerr's local-login
response even though authenticated `auth/me` reports the correct rights. Run
`just usenet moonfin-login` to reconnect and reconcile that cached metadata.
The helper requires the pinned active plugin, binds both user IDs, accepts only
the dedicated 160 permission mask, preserves the session cookie, and rejects
concurrent file changes. It does not change Seerr permissions. Credentials and
session data never appear in its output. Re-review this workaround when updating
Moonbase; direct client re-login may require running the helper again.

Official setup: [Moonbase](https://github.com/Moonfin-Client/Plugin),
[Roku Seerr integration](https://github.com/Moonfin-Client/Roku/wiki/Seerr-Setup).

## Trial verification and recovery

### Moonfin request acceptance, October 24

The dedicated Moonfin account submitted one public-domain season through the
Moonbase Seerr proxy. Native search, download and import completed for all 36
episodes; canonical files existed and matched Sonarr's recorded sizes. Plex and
Jellyfin both indexed episodes 1–36 under the correct series identity. Seerr
marked the requested season available and its request fulfilled. Representative
720p Jellyfin browser playback advanced for nearly ten seconds. The request was
also visible in Moonfin's Requests screen. Roku verification remains deferred.

The first candidate had no indexer results; its empty request and empty Sonarr
entry were removed without deleting files. For the successful candidate, the
global Ultra-HD profile correctly rejected the available lower-resolution
releases. Only that new test series was assigned the existing HD-720p profile;
global defaults stayed unchanged and later seasons remained unmonitored.
This proves the connected acquisition pipeline for available content, not that
every request has an eligible release. Jellyfin's initial remote indexing was
slower than Plex's for this season; all 36 episodes became available while the
broader library scan was still finishing. Exact evidence stays private; the
sanitized receipt is `recovery/drills/moonfin-request-20261024.json`.

The comparison uses native Arr file paths and provider IDs as the reference.
It measures physical-file coverage and movie/series/season/episode identity,
not just headline library counts. Multiple episodes can share one file; native
and legacy hardlinks can represent the same movie. Exact paths, titles, IDs,
API snapshots and browser screenshots remain in ignored private evidence.
Plex is a comparison target, not the authority for correcting ambiguous matches.

The trial state directory is outside the existing recurring NAS settings-backup
allowlist. Do not claim scheduled off-host protection for Jellyfin. Preserve a
separate private checkpoint before upgrades or portal migration. Metadata images
and caches are regenerable; account configuration and the database are not.

Official references: [Jellyfin containers](https://jellyfin.org/docs/general/installation/container/),
[Intel acceleration](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/intel/),
[Seerr media servers](https://docs.seerr.dev/using-seerr/settings/mediaserver/),
[Seerr service connections](https://docs.seerr.dev/using-seerr/settings/services/).

## October 23 trial results

After the completed scans and metadata corrections, both servers expose the
same **568 physical media paths** in the selected general libraries. Against
Arr's reference records, both match **59/59 canonical movies** and **502/502
TV episode assignments** correctly. The four local-copy items also match Plex's
identities. Jellyfin displays 62 movie entries, ten series and 501 episode-file
entries across the four libraries; Plex represents multi-episode files as
separate episode entries. Counts alone therefore are not an indexing failure.

The fresh Jellyfin scan correctly matched the canonical movie library. Five
opaque legacy remote copies and two legacy NAS copies needed explicit metadata
identification. Each was bound to exactly one Radarr file by filename and byte
size before assigning its TMDB identity. Five same-identity, same-size remote
legacy/native pairs were grouped with Jellyfin's native version-grouping API.
No files were renamed, rewritten or deleted. This compares a fresh Jellyfin
installation with an established Plex catalog, not two fresh matching engines.

Web login, browsing and a representative 1080p playback passed, with video time
advancing beyond seven seconds. A five-second synthetic 1080p VA-API encode
also passed. A 4K SDR HEVC browser attempt stalled and is **not accepted**;
the FFmpeg logs confirm VA-API decoding and H.264 hardware encoding, but
processing remained below real time (roughly 0.10–0.24×) in this one-CPU, 1-GiB
trial. There were no recorded cgroup memory kills. This does not establish the
cause or the performance of an unrestricted server or a direct-play client.
Apple TV, Roku, HDR tone mapping,
subtitles and simultaneous-stream behavior remain untested. Keep Plex as the
primary player until the desired real clients pass their playback cases.
The initial remote scan performs substantial media probing; no reduced-probe
override was deployed. A later completed scheduled scan took about 80 seconds.

The existing cloud route to the NAS selected the public source address during
this audit. An ordinary Plex connection timed out, while explicitly selecting
the VPN source succeeded. Jellyfin port 8096 timed out with either source; the
existing cloud firewall policy does not include it. The subsequent request-menu
setup repaired the exact Plex-host route with `just usenet configure-seerr-sync`.
Its ordinary Plex connection and native service checks passed; default routing
and the firewall were preserved. No Seerr migration or cloud-to-Jellyfin event
connection was enabled. The portal continues using Plex for availability.

A one-time encrypted settings/database checkpoint was captured with Jellyfin
stopped, then Jellyfin was restarted. Independent decryption and isolated
extraction restored the operator credentials and passed SQLite integrity checks.
The private archive and receipt are under `usenet-infra/build/jellyfin-trial/`;
artwork, logs and cache are excluded. This is a local recovery checkpoint, not
recurring off-host protection or a replacement-NAS startup test.
