# NAS read-only preflight — October 25, 2026

This is evidence for the [storage plan](plan-nas-storage-and-access.md),
[access model](plan-nas-access-model.md) and [protection policies](plan-nas-data-protection.md).
Checks used the dedicated NAS SSH identity, existing configuration/status files,
bounded directory metadata and QTS in **Safari**. No data was moved, permissions
changed, accounts renamed, apps stopped/uninstalled, or backup, SMART, scrub or
snapshot operation started by this preflight. No payload contents were opened.
Private probe output stays outside Git; this report omits credentials, disk
serials, media identifiers and payload filenames. Times below are Eastern unless
explicitly UTC. Readings are point-in-time observations, not continuous monitoring.

Separate maintenance work landed during this inspection. Its committed
[backup runbook](../usenet-infra/docs/scheduled-backups.md#october-25-email-delivery-and-b2-sample-restore)
is cited below as separate evidence; its restore and email test were not performed
as part of this read-only task.

## Storage health and recovery boundaries

QTS is now **5.2.11 build 20261023**, superseding the plan's October 24 firmware
baseline. HBS is **26.4.6.205**, Container Station **3.1.2.1742** and native Plex
**1.43.5**. Eleven containers were running; those with health checks were healthy.
The former NAS directory container remains stopped. This does not establish
idle downloads, playback or backups for a future maintenance window.

`md1` is RAID 5 with all four members present, zero degraded members, clean/idle
state and a current mismatch counter of zero. These counters do not prove the
date or result of the last scrub. Automatic-scrub configuration is enabled, but
the exact schedule and dated completion/error history remain unqualified.

QTS reported every disk's health and I/O history as **Good**:

| Slot / nominal size | Temperature | Power-on hours | Existing SMART evidence |
| --- | --- | --- | --- |
| 1 / 4 TB | 46°C | 42,820 | Reallocated blocks/events, offline-uncorrectable and SATA error counters zero; pending-sector attribute not displayed; last self-test shown as Not tested |
| 2 / 4 TB | 44°C | 1,726 | Reallocated, pending and offline-uncorrectable counters zero; SATA error counter **13**; rapid test completed without errors October 19 at 11:50:37 |
| 3 / 4 TB | 47°C | 18,553 | Reallocated, reported-uncorrectable, command-timeout, pending, offline-uncorrectable and CRC counters zero; last self-test shown as Not tested |
| 4 / 3 TB | 49°C | 59,102 | Reallocated, pending, offline-uncorrectable and SATA counters zero; last self-test shown as Not tested |

The nonzero disk-2 interface counter needs a baseline/trend and error-history
review; it is not by itself evidence of a current failing disk. The three absent
self-test records and incomplete error history remain health gates. Schedule
any new tests separately, considering active workloads; none ran here.

Pool 1 is Ready; QTS displays 8.16 TB total, about 3.17 TB unallocated, an 80%
alert threshold, 5% guaranteed snapshot space and about 1.96% snapshot usage
(163.79 GB). These are QTS display units and thin-pool accounting, not additional
space obtained by summing volume free space.

| Volume / current purpose | Free filesystem space observed | Snapshot finding |
| --- | --- | --- |
| `Scratch` / system, Container, Public, Multimedia, homes | 31.98 GiB | No snapshots |
| `GPvQNAP` / FromDrobo and Usenet | About 1.18 TiB | One local snapshot, taken September 7, 2024 at 22:34:07; not replicated; Smart Versioning (Monthly); **No schedule** |
| `SpaceBlackM4TimeMachine` / active laptop chain | About 604 GiB | No snapshots |
| `SpaceGrayTimeMachine` / retired laptop volume | About 1.07 TiB | No snapshots; about 76 MiB used, two visible and one hidden root entries counted |

QTS labels the pool **Partial Protection** and the main snapshot over a year old.
Do not represent this as recurring rollback coverage. HBS's saved snapshot-capture
option is a separate mechanism and does not establish retained volume snapshots.
Do not delete the old snapshot or retired volume to recover space without their
own ownership, reference and recovery checks. A retired-laptop desktop shortcut
also remains; a missing SMB share alone does not prove complete retirement.

UPS support is disabled in saved QTS configuration (`Enable=FALSE`). The saved
five-minute shutdown value is inactive, not a working shutdown policy. Physical
UPS presence, communication, runtime and controlled shutdown behavior remain
unproven. This and snapshot coverage are explicit prerequisites to review before
data migration or disk-layout work.

The current QTS **Manage → Actions → Rename Volume Alias** control is present
for Scratch. No `System` alias appeared among the four volumes. The alias was
not changed; record stable volume identifiers and all bindings before using it.

## Share inventory, ownership and platform dependencies

There are **seven path-bearing SMB shares**: Public, FromDrobo,
SpaceBlackTimeMachine, Multimedia, Container, Usenet and homes. `home` is the
dynamic `%H` view. The `TMBackup` configuration section still returns no path;
its purpose must be resolved before removal.

| Current area | Bounded finding | Accepted destination / remaining gate |
| --- | --- | --- |
| Public database archives | One immediate file, 9,893,510,231 bytes; no immediate subdirectories | **Ryan's private files**, confirmed by the user; canonical Ryan AD home after privacy and backup qualification |
| Public saved files | One immediate file, 788,571,269 bytes; no immediate subdirectories | Same owner and destination; preserve current HBS source/history through acceptance |
| Public system entries | Recycle, snapshot-view and stream metadata; no other unclassified top-level entry found | Inspect retained data/reference requirements privately before declaring the required root empty |
| Multimedia | Samples plus system/recycle/thumbnail metadata; cached size 2.09 MiB | User confirms no use of Video Station or Multimedia Console; retire after native dependency/indexing checks and classification of remaining contents |
| homes | Enabled on Scratch at `/share/CACHEDEV1_DATA/homes`; local badmin and usenet-deploy directories observed | Preserve SSH recovery dependency; qualify separate owner-scoped AD homes before moving personal files |

The two Public folders are **not** shared `Documents` and are not automatically
part of the private Plex library. Their archive contents and recovery value were
not inspected; a database-looking folder name does not establish a current
application backup. Existing broad Public read grants remain unchanged and are
a privacy issue to resolve during the authorized permission cutover.

QTS cached share accounting, mostly last updated around 03:21 on October 25,
reports Public 9.95 GiB, Multimedia 2.09 MiB, Container 8.76 GiB, Usenet 3.95 GiB
and homes about 532 KiB. FromDrobo's cached figure is **6.66 decimal TB**, exceeding
the local volume and including a remote namespace; it cannot size local migration
classes. No whole-collection scan was started. Private originals, replaceable
copies, staging and cache still need separate authoritative size/reserve records.

Multimedia Console **2.11.2** and Video Station **5.8.9** are enabled native
packages on the system volume. No inspected container mount (including the
stopped directory container) binds Public or Multimedia; host crontab has no
references to those roots or homes. This narrows the search but does not prove
native package, indexing, File Station or client dependencies absent. Empty
package-dependency fields are not an uninstall qualification. Check supported
dependency reporting and configured indexing sources before any retirement.

NFS is enabled but `/etc/exports` has zero active entries. FTP is disabled.
AFP, WebDAV, QTS application privileges and current NAS SMB sessions still need
qualification; configuration snippets are not effective-access tests.

## Homes and service identity

`HomeLink=TRUE`; the domain template is `/share/homes/DOMAIN=%D/%U`. The `homes`
SMB parent is restricted to administrative principals, while `home` resolves to
the authenticated owner's path. Bounded checks did not find Ryan's, Michael's,
hass's or the SMARTHOME domain home directories at the tested paths. No SMB login
was made to create them. Map actual SIDs and resolved paths during the pilot.

The existing homes root has permissive local filesystem entries, and the two
observed local homes have modes 0777 and 0755. These are not proof of owner-only
local isolation. Test local traversal as well as SMB, File Station, inheritance,
other-owner denial and service denial before placing Ryan's private originals
there. The plan's owner-home policy remains a target, not a verified property.

The [SSH recovery record](../usenet-infra/docs/qnap-bootstrap.md#october-25-ssh-recovery)
explains that enabling homes restored the existing dedicated deployment SSH key
after maintenance; this preflight confirms that identity works. Do not disable
homes during cleanup or rotate that key to compensate for a home-setting failure.
`usenet-deploy` remains UID 1004/GID 100 in administrators. Preserve its home/key
dependency in the eventual `svc-nas-deploy` migration and keep runtime separation
as a prior phase. No account, credential or numeric ownership changed here.

## Backup findings

Read-only HBS configuration inspection around 16:30 found the existing enabled
backup job with exactly five sources: private originals, the two Public folders,
Usenet/Backups and SpaceBlackTimeMachine. **Neither homes nor Multimedia is
selected.** Sources were normalized to neutral aliases for this report.

The job remains nightly 02:00, FIFO latest 30 versions with no extra monthly
retention, snapshot capture and ACL/xattr preservation enabled, source deletion
disabled, client-side encryption disabled and a 10 MiB/s all-day upload cap.
Quick checks are scheduled Mondays at 06:00; full checks on the first of each
month at 06:00. Failure notification is enabled. The saved per-job server-side
encryption flag does not establish the B2 bucket's default policy; bucket policy
and Object Lock were not re-read here. Preserve the runbook's dated bucket evidence.

Existing producer receipts were read, without executing a new job:

| Recovery stream | Existing success evidence |
| --- | --- |
| NAS settings | October 25 16:16:47; qnap-config, plex-config and nas-system-config all report remote ciphertext verified |
| Forgejo | October 24 19:28:35; encrypted stream reports remote ciphertext verified |
| QTS native configuration artifact | Latest matching artifact modification time October 25 15:47:54, 11,983,716 bytes; ten matching artifacts present; modification time alone is not a restore test |

The separately committed backup runbook records an October 25 HBS Quick Check
**Good**, job status **Success**, QNAP test-email delivery independently observed
in the inbox at 16:28:52, and a successful isolated B2 restore of seven encrypted
Forgejo archive/receipt files with byte-for-byte comparison. This closes the old
generic sample-restore and email-transport unknowns. It does **not** prove private
originals/ACL restoration, a Time Machine recovery, native HA offsite recovery,
archive decryption in that particular B2 test, or delivery of an actual failure
event. No new restore or alert test was initiated by this preflight.

## Remaining gates and next steps

| Gate | Next evidence needed before dependent changes |
| --- | --- |
| Disk/power readiness | Dated scrub result/schedule, full error history and disk-2 counter trend; decide scheduled SMART coverage; physical UPS and shutdown qualification |
| Snapshot recovery | Approve per-volume schedule/retention and reserve budget; qualify current rollback points before migration; leave old history intact |
| Ryan's Public files | Pilot canonical AD home and all-route privacy; add verified Local originals coverage, then migrate the two folders with historical/new-path restore checks |
| Multimedia retirement | Native consumers/indexing and supported package dependency checks; classify Samples and system metadata; remove apps/share only in the approved migration phase |
| Complete namespace inventory | Resolve TMBackup, retired volume/root entries, client bookmarks/mounts, current SMB sessions and remaining protocol/app permissions |
| Migration sizing | Separate local data classes from FUSE/provider bytes using trusted indices and bounded metadata; reserve copy/rollback space |
| Recovery gaps | Private-original sample with ACL/xattr checks, Time Machine sample, recurring off-host HA/Jellyfin coverage, restore credentials and approved retention/encryption/cost |
| Permission/identity acceptance | Synthetic role/owner-home matrix, service UID separation and supported svc-prefix migration; no broad recursive ownership changes |
| Writable Hetzner | Full-account role membership, scoped/direct versus NAS gateway qualification, managed-media reconciliation and independent remote-original backup policy |

The next implementation step is the recovery and synthetic permission pilot,
after resolving the readiness gates it depends on. This inspection does not
authorize a production move, ACL change, app removal, new writable mount, restore
into production, volume deletion or RAID redesign.
