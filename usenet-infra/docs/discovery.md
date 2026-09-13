# Curated discovery

Radarr and Sonarr were selected and deployed on September 11, 2026. The live
policy checks, indexer/client wiring, metadata feeds and encrypted NAS backup
pass. A request portal and automatic list subscriptions are deferred.

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
  checks newly posted releases every 15 minutes for monitored movies/episodes.
  Previously added unmonitored titles stay unmonitored; enabling these features
  does not run a backlog search. Interactive Search remains available when you
  want to choose a particular release. The existing SAB category is `prowlarr`.
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

Reviewed September 11 against official documentation and exact release source:

| Component | Pin / behavior |
| --- | --- |
| Radarr | `lscr.io/linuxserver/radarr:6.3.0.10514-ls315` |
| Sonarr | `lscr.io/linuxserver/sonarr:4.0.19.2979-ls323` |
| Prowlarr | Existing `2.5.2.5491-ls158`; the shared profile enables interactive search, automatic search and RSS, with full sync to both applications. Its legacy name `Manual discovery only` is retained to preserve existing IDs/bindings. |
| SABnzbd | Existing client/category; no category or provider changes, completed download removal enabled, failed download removal disabled in both clients. |

The container publishers document configuration persistence, ports and runtime
ownership for [Radarr](https://docs.linuxserver.io/images/docker-radarr/) and
[Sonarr](https://docs.linuxserver.io/images/docker-sonarr/). Exact pins were
read from the publishers' GitHub release metadata, not a floating latest tag.

[Prowlarr's official guide](https://wiki.servarr.com/en/prowlarr/quick-start-guide)
documents independent RSS, automatic and interactive flags and warns that its
download clients do not sync to applications. This implementation creates the
two separate SAB clients server-side. It restricts sync to movie/TV categories.

On September 11, the user explicitly enabled automatic search and RSS globally.
Both applications set RSS interval to 15 minutes, enable completed download
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

For an intentional deployment, `just usenet-configure-discovery` runs the
dedicated Ansible playbook. It manages the mount-dependent discovery project,
configures and reads back policy, updates cloud backup support, then publishes
the authenticated proxy paths. Repeating it preserves API keys and metadata.
It rejects unreviewed versions, additional Prowlarr applications, foreign
download clients/library roots and automatic list subscriptions.

The cloud backup allowlist now captures `config/radarr`, `config/sonarr` and
`compose/discovery`, verifies SQLite snapshots, and rejects an incomplete
deployed discovery configuration. Cover images, logs, caches and downloaded
media are excluded. Restore configuration with the deployment UID/GID and
run `discovery-config.py configure` and then `inspect` before exposing restored
UIs. Older snapshots predate RSS/search authorization; configuration reconciles
them to the saved policy. Keep restored services isolated during recovery checks
to avoid acquisition before deliberately resuming normal operation. Automatic
retries remain disabled; completed download handling and cleanup are enabled.

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
a 15-minute RSS interval, disabled automatic retry/failed removal, enabled native
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
