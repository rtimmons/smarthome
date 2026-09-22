# Scheduled configuration backups

**September 22 Filex coverage added.** Root-owned Filex configuration, database
and verification receipts are captured into encrypted bundles included by the
cloud schedule. Operator bootstrap keys have separately verified encrypted
escrow. NAS archives now include Filex SFTP settings and server identity.
See [capture scope and recovery](filex-recovery.md). Staging and media are
excluded; this supersedes older statements that Filex configuration is outside
coverage. NAS-loss protection still depends on the pending backup-scope choice.


**September 22: post-update state independently restored.**
`cloud-20260922T191826Z.tar.age` captures the deployed Radarr/Sonarr/Prowlarr
versions and guards. Remote ciphertext readback, local hash comparison,
decryption and isolated restore passed: **726 files, four databases, 44 journals
and 59 live hash matches**. All six mount/service unit hashes remain unchanged
from the September 21 reconstruction check. The three stopped rollback databases
also pass integrity checks and remain preserved on the cloud. See the
[deployment and backup receipt](../recovery/drills/app-maintenance-20260922.json).
This refresh closes the post-maintenance checkpoint requested below; Filex and
replacement-host recovery remain separate, and original snapshots are unchanged.

**September 21: accepted native state independently restored.**
`cloud-20260921T155229Z.tar.age` passed remote ciphertext readback, local hash
comparison, decryption and isolated restore of **726 files and four databases**.
All 59 selected live configuration/helper/journal hashes match, including all
44 journals and the active native/verified acceptance receipts. Six live unit
definitions reconstruct exactly from source plus the restored volume identity;
the repair binding override and live dependencies also pass. See the
[receipt](../recovery/drills/native-state-restore-20260921.json).
This supersedes the accepted-state capture gap below. Repeat after the prepared
application maintenance is approved and deployed. No replacement-host startup
or Filex recovery is claimed. `/etc` units are reconstructed, and local private
Terraform/inventory overrides must be preserved separately; neither is a raw
member of this cloud archive. Original bound snapshots remain unchanged.

September 20, 22:05 UTC: read-only status inspection found cloud success at
19:01:42 UTC and NAS success at 04:07:26 UTC, both within the 36-hour freshness
limit. The cloud timer is active and its last service result succeeded. The
cloud capture predates the accepted native checkpoint at 20:18 UTC; it cannot
establish capture of that final state. No archive was decrypted/restored during
this audit. The next independent checkpoint must verify native ownership and
acceptance receipts, repair-spool/mount configuration, current helpers and all
44 preserved journals along with the databases. Filex state remains outside
existing backup coverage. See the [audit receipt](../recovery/drills/health-audit-20260920.json)
and [remaining work](../../plan.md#remaining-work-and-explicit-deferrals).

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


## Cart importer checkpoint

The remote-staging deployment and subsequent postprocessing correction were
installed after the archive below. New configuration/state falls within the
existing allowlist, but fresh independent capture/restore verification is still
outstanding. It must verify `config/catalog/remote-scratch.json`,
`state/catalog/remote-scratch-setup.json`, the migration/controller/importer helpers,
the Compose override and new journals. Systemd mount/dependency units come from
the committed repository; restore them before starting SAB against the restored
remote marker. Preserve active media work while the host-owned backup timer runs.

Latest verified capture: `cloud-20260917T143828Z.tar.age` independently decrypted
and restored all 671 entries and four databases, including 28 importer journals
(22 completed), both user-approved held-payload disposition journals, unchanged
activation, then-current helpers and matching controller state. This supersedes the
older count below; no replacement-host restore is claimed.
[Progress receipt](../recovery/drills/cart-queue-progress-20260917.json).

**Verified September 17, 2026:** the installed scheduler captured
`cloud-20260917T042530Z.tar.age` under its normal locks and quiet-state guard.
Independent local decryption and isolated restore verified all 660 manifest
entries and four SQLite snapshots. The immutable activation marker and all four
current cart/capacity helpers matched live state and repository source. Controller
state, importer status and all 21 journals were captured, including 17 completed
journals that matched the live snapshot. This closes current extension capture;
repeat after later accepted completions change state. It does not establish a
replacement-host restore or whole-NAS recovery.
[Receipt](../recovery/drills/cart-capacity-checkpoint-20260917.json).

The earlier September 17 02:02 archive also decrypted successfully (645 files and
four databases), but contained older helpers and only 12 journals. It was not used
to claim current coverage. Original bound recovery snapshots remain immutable.

The importer was activated September 14 at 01:38:39 UTC. Its marker, journals and
status are under the already included `state/catalog` tree, and worker/adapters
are under `libexec`. Coverage by an allowlist is not proof of capture. The
02:58 UTC handoff check found the most recent scheduled cloud success at September
13, 22:05:43 UTC, before activation. That historical coverage gap is closed by the
September 17 verification above; repeat after new accepted jobs add journals.

First inspect current status and worker/SAB activity using the existing wrappers.
A new scheduled archive may already exist. If one is needed, invoke the installed
scheduler with its service environment; do not redeploy backup support merely to
capture state:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra --command ./scripts/cloud-command sudo -n -u usenet /bin/sh -c 'set -a; . /srv/usenet/config/catalog.env; export BACKUP_AGE=/srv/usenet/libexec/age BACKUP_OUTPUT=/srv/usenet/backups/scheduled; exec python3 /srv/usenet/libexec/scheduled-backup.py cloud --force'
```

This uses the existing scheduler and catalog locks, enforces idle/fully paused
SAB with no post-processing, and preserves pauses. A busy operation or failed
quiet-state check is a reason to defer, never to cancel media work or disable the
cart feed. Inspect the status after invocation: the scheduler may skip a busy
lock without creating an archive.

After successful encrypted upload/readback, retrieve the exact archive privately
with the dedicated cloud wrapper and use `scripts/config-backup-local verify`
with the existing administrator identity. To establish exact member coverage,
restore into a new empty ignored directory using the same helper's `restore`
action, inspect its manifest and compare the activation marker and installed
worker/adapters to the captured versions. Keep decrypted state, paths containing
media identities and raw manifests private. Record only neutral scope, timestamps,
counts and integrity results in the public receipt. Ciphertext readback alone does
not prove decryption or inclusion of the new files. Do not restore this inspection
copy over running state, or replace original bound snapshots.
