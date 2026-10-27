# NAS share backup and redundancy policies

**October 27 recovery checkpoint:** the [service/backup ledger](nas-service-inventory-2026-10-27.md#backup-producers-uploaders-and-archive-policy)
finds current NAS three-scope ciphertext verification. Subsequent
[backup repairs](../usenet-infra/docs/backup-repair-2026-10-27.md) restored cloud
capture and Forgejo scheduling. Both fresh Hetzner archives independently
verified on October 27, with the Filex inner bundle included in the cloud stream;
subsequent unattended captures still need observation. The latest protected HA
archive includes Core, 27 apps and
SSL locally, with no backup network mount and no `/share`. The concurrent HBS
QuDedup seed is not yet qualified recovery; preserve its separate follow-up.
Current app-owned capture snapshots do not clear the retained-snapshot gate.

**Wiki recovery supplement, October 27:** the [wiki checkpoint](nas-service-inventory-2026-10-27.md#wiki-preparation-and-recovery-checkpoint)
preserved both published releases and their pointers off NAS, verified their
encrypted round trip, and rebuilt from independently restored source bundles for
both repositories. Exact inputs and receipts remain private. This supports wiki
rollback; it does not add recurring HTML capture, B2 delivery, replacement-host
bootstrap or disk/power/snapshot qualification. The later account/read-grant
checkpoint also preserved exact pre-grant ACLs and both release pointers off NAS;
only group read entries changed. The approved runtime switch to 1005:1000 now has
a separate encrypted off-NAS checkpoint of current/retained pointers, exact ACLs,
account mapping, updated private inventory and both source bundles; decryption
and all hashes verified. The unchanged publication payloads remain in the earlier
archive. These controller copies do not establish B2 delivery.

A normal settings capture/restore containing the new account and runtime mapping
still needs verification. The native QTS payload comes from a weekly snapshot;
check its source date and account/group contents, not just the outer archive's
freshness. Rebuild must restore the local mapping and enable the qualified reader
ACL step; mode bits alone did not permit the new runtime to read old inputs.

The later [wiki verification follow-up](nas-service-inventory-2026-10-27.md#wiki-backup-and-network-verification-follow-up)
confirmed that the latest scheduled off-host archives predate the account and
runtime change. A current native export and the preserved wiki recovery inputs
now have a separate encrypted Hetzner checkpoint with successful download,
decryption, payload hashes and account/group verification. This closes the
manual off-host preservation gap; it does not establish unattended capture,
replacement-NAS startup or new B2 delivery. Normal schedules, retention and HBS
remain unchanged. Do not force the weekly native script: it rotates old history.

**Open future action:** complete the [unattended-capture and cron-persistence checklist](../usenet-infra/docs/backup-repair-2026-10-27.md#future-actions-unattended-recovery-qualification)
after the next eligible normal runs. Qualify new source captures and off-host
restores, record NAS replication separately, and leave the HBS seed with its
existing follow-up. This recovery qualification can run alongside offline wiki
preparation; it does not authorize a production data move.

**Proposed policy, October 25, 2026. No per-share backup policy, retention rule,
RAID layout or application data location has changed through this plan.** Current observations are recorded in the
[October 25 read-only preflight](nas-preflight-2026-10-25.md), including separately
documented backup maintenance. Every share in the [access model](plan-nas-access-model.md)
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
| `Documents` | Protected | Local originals | Explicitly classified shared originals; no current Public payload assigned here; new roots need explicit inclusion |
| `home` (Ryan) | Protected | Local originals | Canonical AD home, including both Ryan-owned Public folders after cutover; personal root unqualified and homes absent from current HBS selection |
| `home` (Michael) | Protected | Local originals | Canonical AD home; personal root unqualified and homes absent from current HBS selection |
| `homes` | Protected | Local originals | Back up the selected canonical user directories once; the administrative parent and per-user views are not additional copies |
| `MediaCache` | Disposable | Rebuild | No B2 copy of replaceable media; back up manifests/ownership receipts as application settings |
| `PlaybackCache` | Disposable | Rebuild | No B2 copy of disposable rclone cache bytes; protect `remote-reader` configuration through Application recovery |
| `RemoteMedia` | Provider-managed | Rebuild | Canonical replaceable media is excluded from B2; this read-only view is not a second backup source |
| `RemoteManage` | Provider-managed | Rebuild | Same canonical data and policy as `RemoteMedia`; a writable alias does not create another backup set |
| `RemoteFiles` | Provider-managed | Remote originals | General files and originals; new protection, not covered by the current NAS HBS selections |
| `Hetzner` | Provider-managed | Mixed by subtree | One canonical account inventory: remote originals protected, replaceable media excluded, already-covered settings replicas deduplicated by source policy |
| `TransferStaging` | Disposable, conditional | Transient | No B2 backup while another verified source exists; a sole copy must be moved into a protected class before it is treated as durable |
| `forgejo` | Protected | Forgejo recovery | Entire consistent application recovery set, including Git objects; existing encrypted Forgejo archives already sit in the B2-selected parent |
| `forgejo-backups` | Replica | Forgejo recovery | Upload these archives to B2 once; preserve old history and existing confined Hetzner copy |
| `jellyfin` | Protected | Application recovery | Consistent export to `infrastructure-backups`; exclude only proven-rebuildable cache/transcodes; qualify recurring coverage |
| `media-control` | Protected | Application recovery | Preserve ownership receipts and journals in consistent exports; media bytes remain in their separate shares |
| `filex` | Protected | Application recovery | Export required configuration/keys; keep transfer payload policy separate |
| `dns` | Protected | Application recovery | Capture resolver/discovery recovery inputs together; preserve subfolder ownership and startup dependencies |
| `wiki` | Disposable, conditional | Rebuild | Rebuild only after independent source/build-input recovery is verified; unique configuration must enter Application recovery |
| `remote-reader` | Protected | Application recovery | Export configuration/credentials; exclude FUSE mounts and `PlaybackCache` from capture |
| `remote-maintainer` | Protected | Application recovery | New dataset when gateway is provisioned; encrypted export to `infrastructure-backups` |
| `hetzner-gateway` | Protected | Application recovery | New dataset when provisioned; secrets stay off the exported Storage Box filesystem |
| `backup-control` | Protected | Application recovery | Capture recovery inputs through an independent encrypted export; exclude output archives, locks and rebuildable scratch; keys escrowed independently |
| `infrastructure-backups` | Replica | Application recovery | Split from existing `Usenet/Backups/automatic`; include consistent Jellyfin/media/Filex/DNS exports and supported QTS/Plex/HBS exports; qualify gaps |
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
synthetic private file with the other user denied. The October 25 HBS source list
excludes homes. The service is enabled on Scratch and must remain enabled for
deployment SSH recovery; human AD homes and isolation still need qualification.
Inventory local/domain duplicate homes and service
homes before selecting canonical roots; preserve unique files in either identity's
old home until migration and B2 restore pass. Service-home configuration or keys
belong in the relevant application recovery export, with plaintext kept out of backup logs.
QTS stores enabled homes on the selected backing volume, so these user views share
its RAID and snapshot policy. Separate B2 source selections do not alter that.

### Required platform roots

The [legacy-share retirement phase](plan-nas-storage-and-access.md#legacy-share-retirement-and-system-label)
keeps a separate exception register for required QNAP roots. Their omission from
the target dataset catalog is not a backup exclusion. Each retained data-bearing
exception needs its owner, exact source/export, backing volume, assigned policy,
job/credential scope and restore evidence; use the existing schedules and
retention definitions below.

| Retained object / data | Redundancy and B2 handling |
| --- | --- |
| Minimal `Public` root | Keep current RAID 5. No payload backup is needed only after proving it has no unique data; capture its share/ACL definition in Application recovery. Required configuration/state uses that policy; any original still required there uses Local originals. |
| Conditional `Multimedia` exception | Keep current RAID 5. Unique originals use Local originals; required application state uses Application recovery. Rebuild applies only to explicitly proven replaceable bytes; its name does not establish disposability. |
| Native package/required Container paths | Keep current RAID 5; supported consistent exports use Application recovery through `infrastructure-backups`. Enumerate any excluded or unsupported recovery inputs as gaps. |
| `System` volume, formerly `Scratch` | Retain the same volume/RAID/snapshots. Relabeling does not create a B2 source or a whole-volume image backup; protect each dataset and required QTS/package recovery input through its assigned policy. |

Unclassified contents block final retirement/acceptance. Preserve existing backup
coverage while classifying them; verify protection of newly discovered originals
before moving or pruning anything. Do not drop the existing Public selections
until destination protection and old/new-path restore have passed. Avoid duplicate
backups through retained aliases; capture every authoritative source once.
Both current Public data folders belong to Ryan. Select his qualified canonical
home under Local originals before retiring their old sources; do not silently
reclassify them as shared documents or replaceable downloads. Multimedia has no
current HBS selection; classify its remaining contents before retirement.

The October 25 UI showed no retained snapshots on Scratch or either laptop
volume; GPvQNAP has one September 2024 snapshot and no schedule. Qualify recurring
snapshot policy and current recovery points before migration; an HBS capture
option alone does not provide retained volume rollback. UPS support is disabled.
The follow-up found scheduled RAID scrubbing disabled and repeated disk-2
link/I/O errors in retained logs through October 24, despite Good disk summaries.
These findings block production data migration, stress tests and redundancy
reduction pending recovery review and diagnosis; do not enable a scrub merely
to establish a dated result. Preserve the older slot-1/4 error evidence too.

The QNAP media apps were [retired on October 25](nas-media-retirement-2026-10-25.md)
after a verified encrypted copy of application state to the controller's durable
private backups. That one-time archive is not recurring B2 coverage or a live
restore qualification. Samples/system metadata remain unclassified and must not
be treated as disposable merely because the app index was empty. Complete their
protection/classification before share retirement. Container Station's protected-share registration
confirms the required Container exception; retain and protect that package scope.

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
| Forgejo recovery | Keep the existing daily capture/freshness gate (hourly due-check); upload after each successful verified capture, with daily B2 catch-up at 03:00 | Stop/capture/start Forgejo using its qualified job; encrypt the entire recovery set into `forgejo-backups`; a separate uploader sends those archives to B2. Preserve the existing verified Hetzner copy. | Proposed B2 30 daily recovery points plus 12 monthly points; keep pre-change checkpoints and old history through acceptance |
| Application recovery | Capture each required application at least daily and before material changes; upload after each completed export; daily B2 catch-up at 03:00 | Application-aware producers export enumerated durable state/configuration into encrypted streams in `infrastructure-backups`; separate versioned HBS upload to B2. Keep the existing NAS/cloud activity gates and off-host readback. | Proposed B2 30 daily recovery points plus 12 monthly points; preserve pre-change checkpoints through acceptance |
| HA archives | After the native daily archive is complete and verified at its destination; daily catch-up at 08:00 | HA produces the protected archive; copy its original encrypted bytes to `HomeAssistantBackups`, then a dedicated archive job copies to B2. Native HA currently retains three local automatic copies. | 30 daily recovery points plus 12 monthly points, independent of HA's local three-copy retention |
| Laptop history | Nightly at 02:00; serialize with the originals job | HBS backup of a consistent NAS snapshot of the Time Machine bundle; qualify capture while the Mac is idle and demonstrate restoring from the B2 copy | Preserve the existing latest-30-backup-version policy initially; do not assume this means 30 calendar days |
| Rebuild | No scheduled backup of reproducible payloads | Recreate media/cache from the verified canonical source, or wiki publication from independently recoverable Git/build inputs; durable configuration/receipts use Application recovery | None for reproducible bytes |
| Transient | No scheduled backup | Keep the source until the transfer destination and its protection are verified; promote sole-copy originals to Local or Remote originals | None for staging bytes |
| Mixed by subtree | Inherit Remote originals, Forgejo recovery or Application recovery; Rebuild for explicitly replaceable media | One reviewed canonical source map, never a recursive backup of every mounted alias | Inherit the selected subtree policy |

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

Application recovery producers must use native database backup, a supported consistent
snapshot, or an explicitly scheduled stop/capture/start. Copying live SQLite or
AD files is not an accepted replacement. Preserve the existing jobs' activity
gates and recovery identities. No daily catch-up may silently reuse an
unfinished archive or mark missing producer output as fresh.

### Named service datasets and recovery units

`forgejo` is authoritative application data, including Git repositories, LFS,
attachments, the database, configuration and keys. Protect the complete consistent
set, not merely settings or a clone of each repository. The existing job stops
Forgejo for capture, checks SQLite and encrypts the archive; preserve that method
and independently verify repository integrity, application login, user/repository
IDs, OIDC links and attachment access during isolated restoration. See the
[Forgejo recovery contract](../git-host/README.md#encrypted-off-host-backups).

The active `forgejo` share and `forgejo-backups` reference the same recovery
pipeline, not two independent B2 source copies. Likewise, named infrastructure
shares feed their selected encrypted streams in `infrastructure-backups`. Do not
recursively upload live databases as a second substitute backup. Grouping these
streams is acceptable only while their retention, recovery operators and B2 policy
match; source freshness, capture consistency and writer ACLs remain per stream.

Native QTS/Plex/HBS state remains at supported package paths on protected storage.
Its supported exports use Application recovery even though the source is not a
new share. Preserve these explicit non-share sources in the capture inventory.
`backup-control` holds per-job inputs and status, not archive payloads. Include
its necessary control/credential inputs in an independently recoverable encrypted
export, keep recovery keys in separate escrow, and exclude output archives,
transient locks and scratch so capture never recursively backs up itself.

Keep `forgejo-backups` on the existing RAID initially. Its current producer retains
at least seven generations and all archives younger than 90 days locally, with
indefinite existing Hetzner retention. Those are separate from proposed B2
30-daily/12-monthly retention; preserve them until a reviewed retention change.
Neither separate local shares nor different jobs create independent disk-failure
protection. A Replica tier reduction still requires the B2 restore/source gates.

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
  the HBS Monday 16:00 quick check and first-of-month 17:00 content check
  recorded by the October 27 backup maintenance (superseding 06:00)
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
| Forgejo capture / `svc-forgejo-backup` | `forgejo-backup-source-reader`, bounded `forgejo-capture-control`; writes `forgejo-backups` through `archive-writer(forgejo)` | None; emits verified encrypted archives for the separate uploader |
| NAS/application capture / `svc-settings-backup` | `infrastructure-backup-source-reader`; writes assigned `infrastructure-backups` streams through `archive-writer(infrastructure)` | None; preserves the existing separately confined Hetzner upload/readback |
| Forgejo archive upload / `svc-archive-b2` | `archive-readers(forgejo)` on `forgejo-backups`; no live Forgejo grant | `b2-backup-writer(forgejo)` |
| Infrastructure archive upload / `svc-archive-b2` | `archive-readers(infrastructure)` on `infrastructure-backups`; no live service-source grant | `b2-backup-writer(infrastructure)` |
| HA archive replica / `svc-ha-backup-replica` | `ha-backup-readers` | `b2-backup-writer(home-assistant)` |
| Remote originals / `svc-hetzner-backup` | `hetzner-account-readers` through a read-only source view | `b2-backup-writer(remote-originals)` |
| Recovery operator | Explicit isolated-restore role and separately held decryption material | `b2-restore-readers(scope)`; no routine prune authority |

The new names are proposed job identities, not deployed accounts. HBS remains
one trusted package process: different job selections and B2 keys do not by
themselves create OS-level isolation between HBS jobs. Source identities get no
write permission merely because the destination job needs to upload or prune.
Each destination role is restricted to its own repository/prefix; it is not an
AD role automatically understood by Backblaze.
The uploader's two jobs use separate destination scopes/credentials and shared
bandwidth scheduling. The archive shares are separate from application runtimes;
no ordinary service gets access to its backup share or to another job's B2 key.
Keep current HBS archive coverage until replacement jobs, source mappings and
historical/new-path restoration pass; new role names do not change today's jobs.

Account names follow the [`svc-` policy and migration](plan-nas-access-model.md#service-account-migration).
Before each identity cutover, export its old/new realm, UID/GID/SID, job references,
source ACLs, destination key references and decryption-key custody privately.
Update consumers and fresh encrypted recovery exports, then test source access,
destination upload/readback and an isolated restore under the accepted mapping.
Keep historical keys and identity mappings needed to restore old ownership; a
rename must not create a new empty backup history or change retention. Preserve
provider-issued logins, bucket/repository IDs and immutable recovery snapshots;
prefix editable credential labels only where supported. Retire a superseded job
credential only after its replacement passes a normal cycle and rollback is
documented; a pure account/label rename keeps the still-required credential.

## Backup continuity during data migration

The [FromDrobo migration](plan-nas-storage-and-access.md#fromdrobo-data-migration),
[service/archive migration](plan-nas-storage-and-access.md#service-data-and-archive-migration)
and [Public/Multimedia retirement](plan-nas-storage-and-access.md#legacy-share-retirement-and-system-label)
must carry their backup source maps with them. Before a protected root changes, retain
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

Final cleanup reconciles the live source inventory with the new roots and every
required QNAP exception, checks failure notifications, and records a restore-path
translation for old archives. The `Scratch` → `System` label change must leave
source paths, schedules, retention and snapshot identity unchanged; compare the
job selections before/after rather than recreating jobs to match a display label.
Recheck retained or recreated default shares after the planned restart and relevant
QTS/package updates or restores, so new data or inherited grants cannot bypass the
accepted access and protection policies.

## Recorded baseline and implementation gates

The [scheduled-backup runbook](../usenet-infra/docs/scheduled-backups.md) records
the **October 19** HBS configuration, freshly re-read on **October 25** with HBS
26.4.6.205: daily 02:00, latest 30 versions with no extra monthly retention, snapshots
and ACL/xattr preservation, the 10 MiB/s upload cap, and the existing integrity
schedule. Its scope is the private root, two Public folders, NAS settings archives
and the current Time Machine share; homes and Multimedia are absent. Client-side
encryption remains off. The runbook's dated bucket evidence says Object Lock is
off and the bucket keeps all object versions while HBS manages its own catalog;
bucket policy was not re-read in this preflight.

Separate October 25 maintenance documented a Good HBS Quick Check, successful
email transport independently confirmed in the inbox, and an isolated B2 restore
of seven encrypted Forgejo archive/receipt files with byte comparison. Private
originals with ACLs/xattrs, Time Machine recovery and actual backup-failure event
delivery remain unqualified. The read-only preflight also found existing NAS and
Forgejo producer receipts reporting successful remote ciphertext verification;
it did not run a backup or restore. See the dated report for exact times and scope.

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
