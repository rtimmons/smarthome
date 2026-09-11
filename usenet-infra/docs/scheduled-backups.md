# Scheduled configuration backups

Enabled September 11, 2026. Schedules run on the cloud host and NAS; deleting or
turning off the Mac does not stop them. NAS-loss protection is explicitly deferred.
These backups exclude media, unfinished download payloads, Plex artwork, and the
Plex installation binaries. Media remains on the canonical Storage Box.

| Host | Schedule | Protected state | Destination |
| --- | --- | --- | --- |
| Cloud | systemd `usenet-backup.timer`, hourly retry; skip when a success is less than 23 hours old | SAB, Prowlarr, Radarr, Sonarr, catalog state, deployment scripts/configuration | Encrypted locally, copied to `catalog/.backups/cloud` on the existing Storage Box, independently downloaded and compared |
| NAS | `usenet-backups` container cron at minute 7 each hour; same daily freshness gate | QNAP Usenet configuration and Plex preferences plus two databases | `/share/Usenet/Backups/automatic` on the NAS |
| NAS | Part of the NAS job | Already encrypted cloud archives | Pulled with the existing server-enforced read-only account into `automatic/cloud` and checked against SHA-256 receipts |

Plex and QNAP configuration are **not uploaded** to the Storage Box. Encryption
uses the existing public `qnap-admin` or `cloud-admin` recipients. Their private
keys are already recoverable from the original SOPS vault. No private recovery
master or administrator key is installed on either host for the schedule.

Cloud backups require an idle or fully paused SAB queue and no post-processing.
They never resume or delete queued jobs to satisfy that condition. An active
queue delays capture until the next hourly attempt. Database snapshots use
SQLite's online backup API, with source consistency checks. Plex captures only
`Preferences.xml`, `com.plexapp.plugins.library.db` and its blobs database, without
restarting Plex. Artwork can be regenerated; this is not a full Plex package copy.

NAS/local retention keeps at least seven generations and removes only this
scheduler's checksum-matching archives older than 90 days. Original master
snapshots are never pruned. Storage Box cloud ciphertext is currently retained
indefinitely; monitor its small daily growth. The NAS status health check fails
on a failed run or when its last success is older than 36 hours. Status receipts
are on disk; no external notification service has been configured.

The first cloud, QNAP and Plex archives were retrieved from the NAS and decrypted
using administrator identities restored in the separate clean-clone drill.
Every payload matched its manifest; cloud/QNAP validators passed, and both Plex
SQLite snapshots opened successfully. This does not claim a full Plex server
startup restore or Apple TV/Roku playback test.

Deploy with `just configure-scheduled-backups` inside `usenet-infra`. The two
playbooks are `ansible/scheduled-backups.yml` and `ansible/qnap-backups.yml`.
Private NAS inventory retains:

```yaml
qnap_data_root: /share/FromDrobo
qnap_catalog_cache_dir: /share/FromDrobo/Movies
qnap_backup_root: /share/Usenet/Backups/automatic
qnap_plex_root: /share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server
```

After recovery, restore these current overrides before deploying older inventory.
Original SOPS-bound inventory and original recovery receipts remain immutable.
