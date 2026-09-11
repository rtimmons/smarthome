# Curated discovery

Radarr and Sonarr were selected and deployed on September 11, 2026. The live
policy checks, indexer/client wiring, metadata feeds and encrypted NAS backup
pass. A request portal and automatic list subscriptions are deferred.

## Intended use

- Movies: `http://10.77.0.1:19696/radarr/` provides Radarr's movie lookup and
  Discover view (30 trending/popular results verified). Add a chosen title
  without searching and leave it unmonitored.
- TV: `http://10.77.0.1:19696/sonarr/` provides series lookup and a calendar for
  titles you add. Sonarr is not a general recommendation feed. Add a chosen
  series without searching, with monitoring set to None.
- Choose `/library` when adding metadata. This empty local root satisfies the
  applications' library model; it is not the canonical library or NAS cache.
- Use Interactive Search, inspect the release, and deliberately choose its
  download action. The existing SAB category is `prowlarr`.
- Inspect completion in the existing Downloads UI. Deliberate catalog promotion
  and NAS download/removal continue through the existing manifest workflow.

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
| Prowlarr | Existing `2.5.2.5491-ls158`; a dedicated profile enables interactive search and disables RSS/automatic search, with full sync to both applications. |
| SABnzbd | Existing client/category; no category or provider changes, completed/failed download removal disabled in both new clients. |

The container publishers document configuration persistence, ports and runtime
ownership for [Radarr](https://docs.linuxserver.io/images/docker-radarr/) and
[Sonarr](https://docs.linuxserver.io/images/docker-sonarr/). Exact pins were
read from the publishers' GitHub release metadata, not a floating latest tag.

[Prowlarr's official guide](https://wiki.servarr.com/en/prowlarr/quick-start-guide)
documents independent RSS, automatic and interactive flags and warns that its
download clients do not sync to applications. This implementation creates the
two separate SAB clients server-side. It restricts sync to movie/TV categories.

Both applications set RSS interval to zero and disable completed download
handling plus automatic retry, including retries after interactive searches.
These fields were verified in the pinned
[Radarr](https://github.com/Radarr/Radarr/blob/v6.3.0.10514/src/Radarr.Api.V3/Config/DownloadClientConfigResource.cs)
and [Sonarr](https://github.com/Sonarr/Sonarr/blob/v4.0.19.2979/src/Sonarr.Api.V3/Config/DownloadClientConfigResource.cs)
source. See also [Radarr settings](https://wiki.servarr.com/radarr/settings) and
[Sonarr settings](https://wiki.servarr.com/sonarr/settings).

The new containers mount configuration and empty local metadata library roots.
They cannot see SAB download files, canonical catalog storage, writer keys or
the NAS cache. No import list is installed implicitly. The policy health check
fails if an enabled acquisition flag or automatic list addition is introduced.
Administrative users can change settings; this configuration is not a substitute
for keeping the existing per-item approval workflow.

## Operation and recovery

From the repository root:

```sh
just usenet-configure-discovery
just usenet-discovery-health
just usenet-cloud-health
just usenet-discovery-backup
```

The dedicated Ansible playbook starts only the discovery Compose project,
configures and reads back policy, updates cloud backup support, then publishes
the authenticated proxy paths. Repeating it preserves API keys and metadata.
It rejects unreviewed versions, additional Prowlarr applications, foreign
download clients/library roots and automatic list subscriptions.

The cloud backup allowlist now captures `config/radarr`, `config/sonarr` and
`compose/discovery`, verifies SQLite snapshots, and rejects an incomplete
deployed discovery configuration. Cover images, logs, caches and downloaded
media are excluded. Restore configuration with the deployment UID/GID and
run `discovery-config.py inspect` before exposing restored UIs. Keep RSS,
automatic retries and completed download handling disabled throughout recovery.

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

## Acceptance and expected notices

The policy check verifies both exact application versions, two interactive-only
indexers per app, one SAB client each, zero RSS interval, disabled automatic
retry/import/removal, and absence of automatic list subscriptions. It accepts
only the three expected health-check sources: `IndexerRssCheck`,
`IndexerSearchCheck` and `ImportMechanismCheck`. Their red/yellow UI notices
describe deliberate manual-mode choices. Other application warnings/errors fail
the check; do not enable automation just to clear those badges.

The 397-case Usenet suite passed 389 cases with eight opt-in runtime skips; all
13 isolated proxy tests passed separately, including the eight runtime cases.
The only failing validation stage is the previously documented historical-key
scan. Real metadata lookups and the 30-item Discover feed passed without adding
titles or downloading content. Real private paths both reject anonymous access;
the actual password hash is preserved. Visual login could not be checked because
the in-app browser blocked the VPN URL. Open the links in the usual LAN browser
with the existing catalog login.

To stop this layer, stop only `radarr` and `sonarr` in the
`/srv/usenet/compose/discovery` project. Existing Prowlarr search, SAB downloads,
catalog operations and VPN service continue independently. Preserve the two
configuration directories and backups. Do not use a volume-pruning command.
