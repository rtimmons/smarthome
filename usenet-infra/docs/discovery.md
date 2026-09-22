# Curated discovery

Radarr and Sonarr were selected and deployed on September 11, 2026. The live
policy checks, indexer/client wiring, metadata feeds and encrypted NAS backup
pass. [Seerr](seerr.md) now provides browsing and explicit movie/TV requests at
http://10.77.0.1:15055/ with Plex sign-in. Start there for trending/popular content;
the direct Arr workflows below remain available. Automatic list subscriptions
and watchlist downloads remain off.

## Intended use

- Movies: `http://10.77.0.1:19696/radarr/` provides Radarr's movie lookup and
  Discover view (30 trending/popular results verified). Add a chosen title
  with monitoring set to Movie Only and "Start search for missing movie"
  selected to choose and download a matching release immediately. The Discover
  address is `http://10.77.0.1:19696/radarr/add/discover`.
- TV: `http://10.77.0.1:19696/sonarr/` provides series lookup and a calendar for
  titles you add. Sonarr is not a general recommendation feed. Add a chosen
  series with monitoring limited to the episodes/seasons you want; select the
  search-for-missing option to download existing matching episodes.
- Choose `/library` when adding metadata. This is the real canonical Storage Box library,
  mounted separately for movies and TV; it is not the selective NAS cache.
- Automatic Search chooses a release according to your quality profile. RSS
  polling is disabled under the September 20 native policy to preserve seven
  pre-existing monitored missing movies. Use explicit add-and-search or
  Interactive Search for each selected request. SAB categories are `radarr` and
  `sonarr`; Prowlarr supplies indexers but its direct download client is disabled.
- Inspect download queue/history at `http://10.77.0.1:18080/` and import status
  in the Arr Activity view. Completed Download Handling imports successful jobs
  into the library and cleans up completed client downloads. Failed jobs remain
  for review; automatic redownload is disabled. Plex scans the canonical library
  through the read-only NAS mount. Selective native-copy actions are deployed
  on the NAS dashboard; one movie copy and safe repeat passed. A real TV copy
  remains unverified. See [native media](native-media.md).

The same catalog credentials protect both new paths. They share the existing
private listener and VPN selectors; no new public port or gateway change is
needed. The applications use External authentication behind that proxy and
loopback-only Docker ports. API credentials remain on the cloud host.

## Reviewed controls and sources

September 22: the user-approved pinned updates are deployed. All three application
health checks report zero findings, discovery/native policy verifies, and the
post-update encrypted archive independently restores. See the
[maintenance record](app-maintenance-20260921.md) for source comparisons,
validation, preservation and rollback. The following table describes live pins:

| Component | Pin / behavior |
| --- | --- |
| Radarr | `lscr.io/linuxserver/radarr:6.4.4.10685-ls318` |
| Sonarr | `lscr.io/linuxserver/sonarr:4.0.20.3014-ls325` |
| Prowlarr | `2.6.5.5623-ls161`; the shared profile enables interactive search, automatic search and RSS, with full sync to both applications. Its legacy name `Manual discovery only` is retained to preserve existing IDs/bindings; Arr RSS polling remains off under native policy. |
| SABnzbd | Distinct `radarr` / `sonarr` categories, 100 GiB release limit, top-of-queue downloading and pause during postprocessing. Completed removal is enabled; failed removal and automatic retry are disabled. |

The container publishers document configuration persistence, ports and runtime
ownership for [Radarr](https://docs.linuxserver.io/images/docker-radarr/) and
[Sonarr](https://docs.linuxserver.io/images/docker-sonarr/). Exact pins were
read from the publishers' GitHub release metadata, not a floating latest tag.

[Prowlarr's official guide](https://wiki.servarr.com/en/prowlarr/quick-start-guide)
documents independent RSS, automatic and interactive flags and warns that its
download clients do not sync to applications. This implementation creates the
two separate SAB clients server-side. It restricts sync to movie/TV categories.

Historically, on September 11, the user enabled automatic search and RSS globally.
The September 20 cutover supersedes this: RSS stays off, explicit native search
remains enabled, and both Arr applications retain 30 GiB import reserves with
free-space checks and hardlinks enabled. The earlier configuration follows for
provenance only.
Both applications then set RSS interval to 15 minutes, enable completed download
handling and client cleanup, and disable automatic retry, including retries after
interactive searches.
These fields were verified in the pinned
[Radarr](https://github.com/Radarr/Radarr/blob/v6.3.0.10514/src/Radarr.Api.V3/Config/DownloadClientConfigResource.cs)
and [Sonarr](https://github.com/Sonarr/Sonarr/blob/v4.0.19.2979/src/Sonarr.Api.V3/Config/DownloadClientConfigResource.cs)
source. See also [Radarr settings](https://wiki.servarr.com/radarr/settings) and
[Sonarr settings](https://wiki.servarr.com/sonarr/settings).

Both containers mount configuration, SAB completed files at `/data/complete`,
and their canonical movie/TV library at `/library`. The host owns the synchronous
SSHFS mount and writer credentials; neither container receives writer keys or
the NAS cache. Preserve the mount-dependent systemd startup and fail-closed root. No import list is installed implicitly. The policy health check
verifies the authorized search/RSS settings and rejects automatic list addition.
Administrative users can change settings; this configuration is not a substitute
for choosing which titles and episodes to monitor.

## Operation and recovery

From the repository root:

```sh
just usenet-discovery-health
just usenet-cloud-health
```

For current native configuration, use `just usenet-configure-native-ownership`.
It verifies existing ownership and refreshes helpers without replaying the
cutover. The old discovery configurator refuses a native ownership marker.
Read [native cutover](native-cutover.md) before changing policy or recovering
older configuration; do not restore the historical RSS/category settings over
native jobs. The inspector recognizes the current explicit-request policy and
continues to reject real application warnings/errors.

The cloud backup allowlist captures `config/radarr`, `config/sonarr`, ownership
receipts and `compose/discovery`, with SQLite snapshot checks. Media, cover
images, logs and caches are excluded. Preserve ownership/permissions and keep
restored services isolated until current native policy and storage mounts have
been reconciled. Backup coverage is not a whole-machine restore test.

Current cloud/QNAP/Plex backups are scheduled and verified; see
[scheduled backups](scheduled-backups.md) for scope, latest evidence and retention.
`just usenet-discovery-backup` is the separate manual supplemental capture path.

## Historical supplemental backups

The following receipts predate native imports. Do not restore them over current
services merely to resume work or treat their old policy as the deployed state.

The September 11 clean-clone snapshot predates discovery. Do not describe it as
a backup of the new application state. Preserve its exact vault/inventory;
capture and verify a new encrypted application backup after deployment.

The first post-deployment backup is
`20260911T201003Z-bcb62179eb783aef`: 601 files and four integrity-checked SQLite
databases. Its 13,315,460 bytes were uploaded to the NAS, fetched separately,
compared byte-for-byte and decrypted again. Decryption also passed with the
cloud-admin identity restored by the earlier master-key clone drill.
The [public evidence](../recovery/application-backups/20260911T201003Z-bcb62179eb783aef.json)
records the checksum and NAS path. This is an authenticated archive check,
not a new isolated application-startup drill or full machine replacement.

After restoring the baseline vault and bootstrapping the public tools in a fresh
clone, retrieve this **supplemental cloud-config** snapshot separately:

```sh
just --no-dotenv recovery-store fetch --snapshot 20260911T201003Z-bcb62179eb783aef --destination /absolute/new/discovery-backup
just usenet-backup-verify /absolute/new/discovery-backup/recovery.tar.age
just usenet-backup-restore /absolute/new/discovery-backup/recovery.tar.age /absolute/new/restored-cloud
```

Use the existing cloud-admin identity from the restored vault. This snapshot's
payload is the cloud backup format, so do not pass it to `recovery-verify` or
`recovery-drill`. The baseline snapshot ID remains unchanged. New supplemental
captures use unique directories; ciphertext is retained on the cloud, workstation
and NAS with no automatic deletion. Source-controlled code and public receipts
must be published before relying on a fresh Git clone to recover this increment.

The authorized automatic-search/RSS update is captured in supplemental snapshot
`20260911T210232Z-ae56b33b7f0488c7`, with encrypted NAS upload, fetch, byte comparison
and decryption verified. See its [public receipt](../recovery/application-backups/20260911T210232Z-ae56b33b7f0488c7.json).

## Acceptance and expected notices

The policy check verifies both exact application versions, two indexers per app
with interactive search, automatic search and RSS enabled, one SAB client each,
RSS disabled for explicit native requests, disabled automatic retry/failed removal, enabled native
imports/completed removal, and absence of automatic list subscriptions. The
latest live check reported zero health notices. Error/warning health issues fail
the check; do not restore an exemption for deliberately disabled imports. Configuration waits for indexer
sync and fresh application health checks before verifying policy.

Historical discovery-only validation: the 397-case Usenet suite passed 389 cases with eight opt-in runtime skips; all
13 isolated proxy tests passed separately, including the eight runtime cases.
The only failing validation stage is the previously documented historical-key
scan. Real metadata lookups and the 30-item Discover feed passed without adding
titles or downloading content. Real private paths both reject anonymous access;
the actual password hash is preserved. Visual login could not be checked because
the in-app browser blocked the VPN URL. Open the links in the usual LAN browser
with the existing catalog login.

To stop this layer, stop `usenet-discovery.service`, which owns startup of
`radarr` and `sonarr`; preserve its library-service dependency. Existing Prowlarr search, SAB downloads,
catalog operations and VPN service continue independently. Preserve the two
configuration directories and backups. Do not use a volume-pruning command.

Before native imports were deployed, the automatic-search/RSS change passed 398 Usenet tests (390 passed,
eight opt-in skips), current-source secret scanning, and live policy readback:
two search/RSS indexers per app, RSS interval 15, one SAB client, imports disabled.
