# NAS share backup and redundancy policies

**Proposed policy, October 25, 2026. No backup job, retention rule, RAID layout or
data has changed.** Every share in the [access model](plan-nas-access-model.md)
has both a storage-redundancy requirement and a B2 policy below. Schedules use
**America/New_York**. Proposed retention is a starting policy to size and qualify,
not permission to purge existing recovery history.

RAID protects availability after a disk failure; versioned B2 backups provide
recovery from loss, deletion or damage. A share can require one, both, or neither
according to what it contains. Share permissions are independent of these choices.

## Per-share policy

| Share | Target storage tier | B2 policy | Scope / current coverage |
| --- | --- | --- | --- |
| `PrivateLibrary` | Protected | Local originals | All private originals; existing HBS selection already includes the current private root |
| `Documents` | Protected | Local originals | All classified personal/shared originals; only two selected `Public` folders are currently covered, so additional folders need explicit inclusion |
| `home` (Ryan) | Protected | Local originals | Ryan's canonical personal directory under `homes`; current existence and B2 selection unverified |
| `home` (Michael) | Protected | Local originals | Michael's canonical personal directory under `homes`; current existence and B2 selection unverified |
| `homes` | Protected | Local originals | Back up the selected canonical user directories once; the administrative parent and per-user views are not additional copies |
| `MediaCache` | Disposable | Rebuild | No B2 copy of replaceable media; back up manifests/ownership receipts as application settings |
| `PlaybackCache` | Disposable | Rebuild | No B2 copy of disposable rclone cache bytes; protect mount configuration/credentials through Settings |
| `RemoteMedia` | Provider-managed | Rebuild | Canonical replaceable media is excluded from B2; this read-only view is not a second backup source |
| `RemoteManage` | Provider-managed | Rebuild | Same canonical data and policy as `RemoteMedia`; a writable alias does not create another backup set |
| `RemoteFiles` | Provider-managed | Remote originals | General files and originals; new protection, not covered by the current NAS HBS selections |
| `Hetzner` | Provider-managed | Mixed by subtree | One canonical account inventory: remote originals protected, replaceable media excluded, already-covered settings replicas deduplicated by source policy |
| `TransferStaging` | Disposable, conditional | Transient | No B2 backup while another verified source exists; a sole copy must be moved into a protected class before it is treated as durable |
| `AppData` | Protected | Settings | Consistent database/configuration exports, service identities and ownership receipts; exclude reproducible caches; audit gaps in existing exports |
| `BackupArchives` | Replica | Settings | Verified encrypted NAS/cloud/Forgejo settings artifacts; current `Usenet/Backups` selection already reaches B2 |
| `HomeAssistantBackups` | Replica | HA archives | Native protected HA archives; new NAS/B2 coverage is required; the native daily job currently stores only on HA |
| `SpaceBlackTimeMachine` | Replica | Laptop history | Preserve existing HBS/B2 coverage of the current laptop backup chain |

All existing local NAS shares currently inherit the **same RAID-5 group**.
The Disposable and Replica tiers permit future lower redundancy; they do not
describe a change already made. Remote shares inherit Hetzner's storage design,
not the RAID level of a NAS cache or mountpoint.
Rebuild eligibility requires a verified replacement source. Irreplaceable media
uses an originals policy regardless of which application or library displays it.

For personal homes, Local originals means the same nightly 02:00 versioned HBS
policy and proposed 30 daily/12 monthly recovery points below. Preserve domain
SIDs, ACLs, ownership and extended attributes, and test restoration of one user's
synthetic private file with the other user denied. Do not assume existing HBS
selections include homes. Inventory local/domain duplicate homes and service
homes before selecting canonical roots; preserve unique files in either identity's
old home until migration and B2 restore pass. Service-home configuration or keys
belong in the relevant Settings export, with plaintext kept out of backup logs.
QTS stores enabled homes on the selected backing volume, so these user views share
its RAID and snapshot policy. Separate B2 source selections do not alter that.

## Storage tiers and eventual placement

| Tier | Required redundancy / eventual placement | Gate before using it |
| --- | --- | --- |
| Protected | At least one-disk fault tolerance. Keep existing RAID 5 now; choose an appropriate RAID 1/5/6 layout for a future protected pool. | Independent B2 restore and local recovery remain required; redundancy does not replace either. |
| Disposable | Zero redundant disks is acceptable: a separate single-disk volume/device, or reproducible cache storage. | Confirm the authoritative source remains available and test rebuilding the cache. Staging must not hold the only copy. |
| Replica | Keep RAID 5 initially. A separate single disk is an eventual option because this is a recovery copy, not the only live source. | Prove the source still exists, B2 has a recent recoverable copy, decryption keys are available independently, and losing local history is acceptable. |
| Provider-managed | Storage Box uses provider-managed RAID; customer share names cannot select a lower RAID level there. Local cache durability is specified separately. | Independently protect originals; provider RAID and snapshots are not a B2 backup. |

On this QNAP, the physical relationship is **disks → RAID group → pool → volume →
share**. A new share or another thin volume in the existing pool still has the
same redundancy. Different local RAID requirements require different backing
storage, generally separate pools/devices. Four occupied bays and one current
RAID group mean a split needs additional hardware or a separately planned
evacuate/rebuild/restore operation. Do not promise a RAID-5-to-single-disk toggle.
Snapshot scheduling likewise follows the backing volume; shares on one volume
cannot be assumed to have independently isolated snapshot space or history.
[QTS storage layout](https://docs.qnap.com/operating-system/qts/5.1.x/en-us/storing-data-365A536F.html),
[QTS volume/snapshot examples](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/volume-configuration-examples-1A2DDF7C.html),
[Hetzner storage redundancy](https://docs.hetzner.com/storage/storage-box/general/).

## B2 policy definitions

| Policy | When | How / authoritative source | B2 retention target |
| --- | --- | --- | --- |
| Local originals | Nightly at 02:00 | HBS versioned incremental backup from the selected NAS roots, using a stable snapshot where supported; preserve ACLs, ownership and extended attributes | 30 daily recovery points plus 12 monthly points |
| Remote originals | Nightly at 04:00 | Proposed pinned restic job on the cloud host, reading a stable read-only Storage Box snapshot/view; use an explicit writer-quiescence window if a consistent snapshot is unavailable; encrypted repository through B2's S3 API | 30 daily recovery points plus 12 monthly points |
| Settings | After each successful consistent export; daily catch-up at 03:00 | Existing application-aware producers create complete, verified encrypted artifacts; a separate versioned HBS job copies those artifacts from `BackupArchives` to B2 | 30 daily recovery points plus 12 monthly points; preserve pre-change recovery checkpoints through acceptance |
| HA archives | After the native daily archive is complete and verified at its destination; daily catch-up at 08:00 | HA produces the protected archive; copy its original encrypted bytes to `HomeAssistantBackups`, then a dedicated archive job copies to B2. Native HA currently retains three local automatic copies. | 30 daily recovery points plus 12 monthly points, independent of HA's local three-copy retention |
| Laptop history | Nightly at 02:00; serialize with the originals job | HBS backup of a consistent NAS snapshot of the Time Machine bundle; qualify capture while the Mac is idle and demonstrate restoring from the B2 copy | Preserve the existing latest-30-backup-version policy initially; do not assume this means 30 calendar days |
| Rebuild | No scheduled media backup | Recreate from canonical media; application settings/receipts use Settings | None for media bytes |
| Transient | No scheduled backup | Keep the source until the transfer destination and its protection are verified; promote sole-copy originals to Local or Remote originals | None for staging bytes |
| Mixed by subtree | Inherit Remote originals or Settings; Rebuild for explicitly replaceable media | One reviewed canonical source map, never a recursive backup of every mounted alias | Inherit the selected subtree policy |

Schedules are queue/start times, not promises that all transfers finish then.
Serialize heavy NAS jobs and preserve the current **10 MiB/s aggregate HBS upload
cap**; splitting jobs must not multiply it. Remote cloud-to-B2 traffic needs its
own bandwidth/cost budget. Seed jobs may take longer than a nightly window.
Define missed-run catch-up for downtime and daylight-saving clock changes;
a skipped run must not appear as a fresh success.
For daily protected policies, aim for a source recovery point no older than
24 hours in steady state; alert on any failed run and on age exceeding 36 hours.
An upload of a stale export does not reset source freshness. Measured restore
time, including downloading/decrypting large data, must be recorded before a
redundancy reduction; no whole-library restore-time guarantee exists yet.

Settings producers must use native database backup, a supported consistent
snapshot, or an explicitly scheduled stop/capture/start. Copying live SQLite or
AD files is not an accepted replacement. Preserve the existing jobs' activity
gates and recovery identities. Neither daily catch-up time may silently reuse an
unfinished archive or mark missing producer output as fresh.

The 30-daily/12-monthly policy means distinct recovery points with overlap allowed,
not 42 independent full data copies. HBS jobs with different source, retention or
encryption policies must be split and tested; the current single job does not
already implement these per-share policies. Restic retention belongs to its own
repository. Do not apply a restic lifecycle/pruning recipe to the existing HBS
bucket. [HBS job policies](https://docs.qnap.com/application/hybrid-backup-sync/3v21.x/en-us/creating-a-backup-job-753C8301.html),
[restic B2 transport](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#backblaze-b2),
[restic retention](https://restic.readthedocs.io/en/stable/060_forget.html).

### Remote aliases and complete-account coverage

`Hetzner`, `RemoteMedia`, `RemoteManage` and `RemoteFiles` can expose overlapping
objects. Back up each authoritative remote path once. The remote source inventory
must cover the whole account, with explicit exclusions for classified replaceable
media, transient scratch, and backup replicas whose authoritative artifacts have
already passed their own B2 check. New/unclassified remote directories default to
Remote originals until classified; report coverage changes and estimate their
size before the initial full-account seed. Do not silently omit files stored
outside `catalog`, or exclude a settings replica merely because its name looks
like a backup. If its authoritative copy is not protected, back up that artifact.

Full-account users may change or delete remote files, so B2 credentials and
restore secrets must live outside the mounted Storage Box and ordinary source
shares. The backup job uses a read-only source view; separately verify the backend
key's actual authority. A full Hetzner data role receives no B2 credentials or
permission to prune B2 history. Keep B2 restores possible without a working NAS,
HA directory, or Storage Box.

### Encryption, retention and verification

- Target client-side encryption for originals and laptop-history jobs. The
  existing HBS job has it disabled and cannot gain it in place: qualify a new
  encrypted destination/job alongside the old history before retiring anything.
  Preserve existing bucket privacy/SSE-B2; server-side encryption alone does not
  establish this client-side requirement.
- Keep age-encrypted settings and native protected HA archives encrypted in B2.
  Verify HA export bytes and encryption metadata; the UI's decrypted download
  is not automatically equivalent. Encrypt any deliberately unencrypted Talos
  export before including it. Keep its distinct restore contract.
- Scope B2 keys to each destination job/repository, with no bucket/account
  administration. Qualify the read/list/write/delete capabilities actually needed
  for upload, readback and retention; do not call an ordinary RW key append-only.
  Test Object Lock, lifecycle and pruning together before enabling an immutable
  policy; Object Lock is currently disabled on the existing bucket.
- Verify every completed artifact's checksum or backup-catalog result. Continue
  the existing HBS Monday 06:00 quick check and first-of-month 06:00 content check
  until each replacement has an equivalent tested check; budget content-check
  downloads and serialize them with backups. Qualify repository integrity checks
  for the proposed restic job separately.
- Monthly: restore a small private sample from each protected policy into an
  isolated location and verify content, applicable ACLs/ownership/xattrs and
  decryption. Quarterly: exercise a native HA/app restore and a Time Machine
  sample recovery; after a material format/key/path change, repeat the affected
  restore before relying on it. Never print private media identifiers in Git.

## Job owners and access

| Job / target account | Source role | B2 destination role |
| --- | --- | --- |
| HBS originals, homes and laptop jobs / `svc-originals-backup` | `originals-backup-reader`, `home-backup-reader`, bounded per job | `b2-backup-writer(originals)` and `b2-backup-writer(laptop-history)` |
| Settings archive upload / `svc-settings-b2` | `backup-archive-readers` | `b2-backup-writer(settings)` |
| HA archive replica / `svc-ha-backup-replica` | `ha-backup-readers` | `b2-backup-writer(home-assistant)` |
| Remote originals / `svc-hetzner-backup` | `hetzner-account-readers` through a read-only source view | `b2-backup-writer(remote-originals)` |
| Recovery operator | Explicit isolated-restore role and separately held decryption material | `b2-restore-readers(scope)`; no routine prune authority |

The new names are proposed job identities, not deployed accounts. HBS remains
one trusted package process: different job selections and B2 keys do not by
themselves create OS-level isolation between HBS jobs. Source identities get no
write permission merely because the destination job needs to upload or prune.
Each destination role is restricted to its own repository/prefix; it is not an
AD role automatically understood by Backblaze.

Account names follow the [`svc-` policy and migration](plan-nas-access-model.md#service-account-migration).
Before each identity cutover, export its old/new realm, UID/GID/SID, job references,
source ACLs, destination key references and decryption-key custody privately.
Update consumers and fresh encrypted Settings exports, then test source access,
destination upload/readback and an isolated restore under the accepted mapping.
Keep historical keys and identity mappings needed to restore old ownership; a
rename must not create a new empty backup history or change retention. Preserve
provider-issued logins, bucket/repository IDs and immutable recovery snapshots;
prefix editable credential labels only where supported. Retire a superseded job
credential only after its replacement passes a normal cycle and rollback is
documented; a pure account/label rename keeps the still-required credential.

## Backup continuity during data migration

The [FromDrobo migration](plan-nas-storage-and-access.md#fromdrobo-data-migration)
must carry its backup source map with it. Before a protected root changes, retain
a recoverable checkpoint at the old location and record the exact source selection,
exclusions, destination/catalog and encryption key reference. Keep existing B2
history; a path change is not permission to delete old versions or start a fresh
empty recovery chain. Qualify whether HBS can track the relocation or needs a new
job/destination, then budget any full re-upload before cutting over.

At cutover, update the job selection to the new canonical root and prove a newly
created synthetic file reaches B2 and restores with the intended ownership/ACLs.
Check both historical restoration and new-path restoration. Do not count two
share aliases as independent backups or accidentally follow a Hetzner FUSE mount
while backing up local roots. Keep caches and verified transient staging excluded;
retain their configurations, receipts and required source availability.

For a cross-volume copy, keep the old source frozen and intact until verification,
new backup success, restore and household acceptance. A same-volume rename keeps
the original inodes but provides no extra recovery copy; its rollback is a reverse
rename plus saved configuration and a qualified checkpoint. Reconcile post-cutover
writes before either rollback. Record an explicit retirement decision after at
least one normal backup/application cycle; never prune the old source or B2 history
as an automatic cleanup step.

## Recorded baseline and implementation gates

The [scheduled-backup runbook](../usenet-infra/docs/scheduled-backups.md) records
the **October 19** HBS configuration: daily 02:00, latest 30 versions, snapshots
and ACL/xattr preservation, the 10 MiB/s upload cap, and the existing integrity
schedule. Its scope is the private root, two Public folders, NAS settings archives
and the current Time Machine share. Client-side encryption and Object Lock are
off; the bucket keeps all object versions while HBS manages its own 30-version
catalog. B2 sample restoration and failure-email delivery remain unverified.
These settings were not freshly re-read for this policy update.

The October 25 HA check established daily protected **local-only** native backups;
it did not establish B2 delivery. The storage inspection established one RAID-5
failure boundary, not separate redundancy per share.

1. Inventory canonical roots, sizes/change rates and current job exclusions;
   map every share to the policy above. Price retained versions and seed traffic
   before activating new remote coverage or longer retention.
2. Save existing job configuration, encryption/recovery identities, share/ACL
   mappings and B2 catalog locations. Prove an independent sample restore from
   the existing job before altering its source selections.
3. Pilot each new encrypted job in a distinct destination with synthetic data;
   verify upload, intentional source deletion, retained-version restore, pruning,
   notifications and outage recovery. Keep existing history until accepted.
4. Publish per-policy status: last source checkpoint, last B2 completion, source
   bytes/scope, retention/encryption version, last integrity check and last actual
   restore. Missing required coverage must be visible, not a green aggregate.
5. Only then move eligible shares to lower-redundancy backing storage. Preserve
   share identity, ACLs, application references and B2 source selection/history;
   confirm new-file backup and restore after the move before retiring the source.
