# Scheduled configuration backups

**October 8: recurring off-host NAS settings coverage is deployed and verified.**
Final `cloud-20261008T192037Z.tar.age` also passed off-host readback and
independent restore: 785 files, five databases, 44 journals and both nested
Filex bundles, including the corrected operator login escrow.
The user selected settings only. The scheduled NAS job now uploads encrypted
QNAP and Plex settings to a separate Storage Box subaccount confined to
`catalog/.backups/nas-settings`. Every upload is downloaded again and its
SHA-256 compared before success is recorded. Independent restores passed for
66 QNAP settings files and three Plex files; both Plex database snapshots opened.
NAS originals, artwork and installation binaries are excluded by choice.
Media and staging are excluded from this settings-only scope.


Enabled September 11, 2026. Schedules run on the cloud host and NAS; deleting or
turning off the Mac does not stop them. NAS-loss coverage is settings only.
These backups exclude media, unfinished download payloads, Plex artwork, and the
Plex installation binaries. Media remains on the canonical Storage Box.

| Host | Schedule | Protected state | Destination |
| --- | --- | --- | --- |
| Cloud | systemd `usenet-backup.timer`, hourly retry; skip when a success is less than 23 hours old | SAB, Prowlarr, Radarr, Sonarr, catalog state, deployment scripts/configuration | Encrypted locally, copied to `catalog/.backups/cloud` on the existing Storage Box, independently downloaded and compared |
| NAS | `usenet-backups` container cron at minute 7 each hour; same daily freshness gate | QNAP Usenet configuration and Plex preferences plus two databases | `/share/Usenet/Backups/automatic` plus independently verified encrypted off-host copies |
| NAS | Part of the NAS job | Already encrypted cloud archives | Pulled with the existing server-enforced read-only account into `automatic/cloud` and checked against SHA-256 receipts |

The recurring NAS schedule uploads Plex and QNAP configuration to the confined
backup account. The canonical media reader remains server-enforced read-only. Encryption
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
snapshots are never pruned. Storage Box cloud and NAS settings ciphertext is currently retained
indefinitely; monitor its small daily growth. NAS snapshot capture retries short catalog refresh conflicts for up to one minute
without interrupting transfers; longer activity defers until the next hour.
The NAS status health check fails
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

## Read-only follow-up

Use the committed [verified archive receipt](../recovery/drills/scheduled-backups-20260911.json)
as the initial evidence, then inspect current freshness. On the cloud, the status
receipt is `/srv/usenet/backups/scheduled/cloud-status.json`; inspect the timer
with the repository's dedicated connection wrapper:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra --command ./scripts/cloud-command systemctl status usenet-backup.timer --no-pager
```

On the NAS, inspect `usenet-backups` container health and
`/share/Usenet/Backups/automatic/nas-status.json` using the dedicated NAS identity
and pinned host from the private inputs. The container's existing healthcheck
runs `scheduled-backup.py nas --check`, which emits only health/freshness fields.
Do not dump private environments or Plex preferences to inspect status. Scheduled
retries are automatic; a failed/freshness check is a reason to diagnose the
recorded run, not to resume queued downloads or interrupt a transfer.

The deployed backup helper includes `state/native-items` ownership and integrity
receipts. Independent verification of `qnap-20260913T041100Z.tar.age` passed with
scope `qnap-config`, 56 files and no media. The 1,357-byte native receipt matched
SHA-256 `50f8cd3e5fb3a5b4c444770fe6ee9845e900e534ab62409e53f5677da064aa61`.
See the [capture and archive verification receipt](../recovery/drills/native-receipt-backup-20260913.json).
This closes capture of the new receipt; it does not prove restoration onto a
replacement destination or whole-NAS recovery. Original bound snapshots remain
immutable, and ordinary freshness checks still apply.


## Confined NAS backup account recovery

The separate `terraform/nas-backup` root manages only the backup subaccount,
with `prevent_destroy`; never use the canonical storage root to recreate it.
Its local state and private inputs are ignored. Existing account ID 331416 is
recoverable by importing it into this root if local state is lost; inspect the
provider account first, rather than creating a duplicate. The account is
`u666991-sub2` at `u666991-sub2.your-storagebox.de`, SSH port 23.

The scheduler reads `/source/usenet/config/backup/offhost/rclone.conf`, dedicated
`id_ed25519` and pinned `known_hosts` from its read-only source mount. These
three mode-0600 files are included in the encrypted QNAP settings archive.
The local bootstrap copies live under ignored `secrets/nas-backup`. Recovery
requires the existing administrator decryption identity, then those restored
connection files; no administrator private key is installed on the NAS.

Preserve `qnap_backup_offhost_required: true` in private inventory and redeploy
only `ansible/qnap-backups.yml` when needed. It sets `NAS_OFFHOST_REQUIRED=true`;
missing connection settings or a failed upload/readback makes the job fail.
The freshness check requires two remotely verified settings archives.
The backup account can list only its confined backup directory, and a parent
path probe to the canonical library was refused. It cannot replace the separate
read-only media credential. Remote retention is currently indefinite; local
90-day/minimum-seven retention remains unchanged. This is recoverable settings
coverage, not a tested replacement NAS boot or protection of private originals.
