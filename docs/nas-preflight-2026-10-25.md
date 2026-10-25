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

The later October 25 follow-up adds retained event/kernel history and native
app dependency/source inspection. **Disk 2 has recurring link errors, and the
RAID scrub schedule is disabled.** These findings supersede the earlier
inference from the `auto_data_scrubbing` flag; a Good summary is not migration
clearance. Production data moves and stress tests remain gated on disk diagnosis
and verified recovery coverage.

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
date or result of the last scrub. The follow-up verified that the **RAID Scrubbing
Schedule is off** in QTS Global Settings. Its disabled fields show weekly/Sunday
00:00; these are not an active schedule. The earlier `auto_data_scrubbing=1`
reading did not establish scheduled scrubbing. No scrub record was found in the
retained event database; the last completed scrub remains unknown.

QTS reported every disk's health and I/O history as **Good**:

| Slot / nominal size | Temperature | Power-on hours | Existing SMART evidence |
| --- | --- | --- | --- |
| 1 / 4 TB | 46°C | 42,820 | Reallocated blocks/events, offline-uncorrectable and SATA error counters zero; pending-sector attribute not displayed; last self-test shown as Not tested |
| 2 / 4 TB | 44°C | 1,726 | Reallocated, pending and offline-uncorrectable counters zero; SATA error counter **13**; event log confirms rapid test October 19, started 11:50:36 and completed without error at 11:52:37 |
| 3 / 4 TB | 47°C | 18,553 | Reallocated, reported-uncorrectable, command-timeout, pending, offline-uncorrectable and CRC counters zero; last self-test shown as Not tested |
| 4 / 3 TB | 49°C | 59,102 | Reallocated, pending, offline-uncorrectable and SATA counters zero; last self-test shown as Not tested |

The SATA counter is not by itself a diagnosis; the retained history below now
establishes repeated errors on disk 2's connection path. Its counter and the
number of logged resets measure different things. The three absent self-test
records and missing drive-internal error/self-test logs remain health gates.
Do not start a scrub, extended test or migration merely to fill these gaps before
reviewing current recovery coverage and the disk-2 fault. No tests ran here.

### Retained disk and RAID history

Read-only queries used a private local copy of `/mnt/HDA_ROOT/.logs/event.log`
(SQLite quick check passed) and filtered reads of `kmsg` plus its two retained
compressed rotations. The event copy contains 19,909 rows dated July 17, 2022
through October 25, 2026. This is retained evidence, not proof of uninterrupted
logging or a complete drive lifetime. No raw logs, WWNs or serials are committed.

| Date / scope | Retained finding | Interpretation / follow-up |
| --- | --- | --- |
| Disk slot 2, June 28 and August 5, 2026 | Bad-block scan reported five bad blocks; abnormal SMART events also recorded | Predates the August replacement; do not attribute these to the current drive |
| Disk slot 2, August 14–15 | Replacement recorded August 14 at 15:55; RAID rebuild completed August 15 at 00:12:42 | Confirms a replacement/rebuild boundary; current WD model and private identity mapping distinguish it from the retired disk |
| Slots 1–4, August 19 | Bad-block scans started around 11:17 and finished by 21:09; completion records have no bad-block warning | Later point-in-time scans, not RAID scrubs or ongoing health guarantees |
| Disk slot 2, October 18, 20 and 23 | Three read I/O warning events marked `ILLEGAL REQUEST`, sense 0x5/0x21/0x4 | Recent errors on the current disk's path; the successful October 19 rapid test does not clear subsequent faults |
| `ata2`, August 14–October 24 | **26 SATA link resets** across retained kernel logs; handshake/unrecovered-data flags and failed queued reads/writes; latest reset October 24 at 03:12:10 | Current sysfs mapping ties `ata2` to `sdb`, the disk-2 WD device; investigate before migration or stress tests |
| Other historical slots | Slot 1 unrecovered read/medium errors in August–November 2025; slot 4 an unrecovered read/medium error during the August 14, 2026 rebuild | Reconcile physical identity/history and current diagnostics; do not erase these concerns because today's summary is Good |
| RAID scrubs | No matching retained event; UI scheduler off; no scrub command in host crontab | No dated completed scrub can be claimed; agree a future schedule after the disk/readiness gate |

The newest retained link-error episode precedes the October 25 firmware update
and reboot. The short post-update observation is **not** evidence of resolution.
The records do not isolate the drive, bay/backplane/connection, power or controller
as the cause, and do not establish lost application data. Preserve current
diagnostics privately, obtain supported full SMART/error logs, review verified
originals recovery, then plan diagnosis and any physical intervention in its own
maintenance window. Do not reseat disks or force a rebuild during preflight.

QTS's documented [storage global settings](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/storage-global-settings-AB743D00.html)
separate the scrub scheduler from RAID resync priority and space reclamation.
Here priority is Resync First (High speed), while reclaim/TRIM is enabled daily
at 02:00. That reclamation schedule is not a scrub schedule. No setting changed.

### Pool, snapshots and power

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
| Multimedia | Samples plus system/recycle/thumbnail metadata; cached size 2.09 MiB | User confirms no use; native source/index/dependency inventory below supports retirement after state/content classification and final cutover checks |
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
references to those roots or homes. The follow-up inspected the native UI and
installed package/startup metadata as well:

| Consumer / function | Read-only finding | Retirement consequence |
| --- | --- | --- |
| Video Station | Enabled, custom application permissions; **zero content sources, zero videos, zero used bytes** in Content Management | No configured media source to migrate; preserve any unique app settings/metadata before removal |
| Multimedia Console index | Enabled, Low priority, Completed; latest displayed update October 25 15:56:08; **zero indexed files** and zero photos/videos/music; thumbnails zero/Not Started | No populated index was observed; do not re-index or remove thumbnails as an audit step |
| Cloud multimedia information | Disabled | Optional cloud-information prompt dismissed; no consent or indexing change submitted |
| Other multimedia apps | Suite reports QuMagie, QNAP AI Core, Music Station and Media Streaming add-on not installed; CAYIN Media Viewer not installed; installed-package inventory also lacks Photo Station and Qsirch | No additional installed multimedia consumer identified in these views |
| Native transcoding / DLNA | Transcoding UI requires installing CAYIN; saved DMS enable flag is 0 | No native transcoding capability established; do not mistake other enabled media-service flags for a working consumer |
| Retained Plex, HBS, Container Station | No direct Multimedia Console/Video Station references in their configured startup scripts; no relevant container binds | Evidence supports separating their retention from the unused QNAP media apps; still verify startup/playback/backup after an actual removal |
| File Station | Installed; no startup script returned by the same metadata query | Retain it and test ordinary browsing/downloads and any used media-preview features at cutover; lack of a script is not a dependency test |
| Container share | QNAP's read-only protected-share registry lists Container Station as its consumer | Keep required Container roots; this is an evidenced package exception |

QNAP documents [per-app content sources and indexing](https://www.qnap.com/en-ca/how-to/tutorial/article/multimedia-console-quick-start-guide)
and the [supported Multimedia removal workflow](https://www.qnap.com/en-us/how-to/faq/article/how-can-i-remove-the-default-shared-folders-on-my-nas).
The installed inventory, empty source/index state and user-confirmed non-use
support retiring Video Station and Multimedia Console in phase 5c. Capture any
unique settings first, remove the unused dependent app before the shared console
where QTS requires it, and inspect the actual dependency confirmation at that
cutover. Stop if it names an unexpected retained consumer. No Remove/Stop action
or uninstall confirmation was invoked here. Samples/system metadata still need
classification before disposing of share contents; retain Public and homes.

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
| Disk/power readiness | Investigate disk-2 link/I/O errors before migration or stress; reconcile older slot-1/4 errors and obtain full drive-internal logs; scrub schedule confirmed off with no retained completion record; plan testing/scrubbing after recovery review; physical UPS/shutdown qualification |
| Snapshot recovery | Approve per-volume schedule/retention and reserve budget; qualify current rollback points before migration; leave old history intact |
| Ryan's Public files | Pilot canonical AD home and all-route privacy; add verified Local originals coverage, then migrate the two folders with historical/new-path restore checks |
| Multimedia retirement | Read-only inventory found no additional installed multimedia consumer and zero Video Station sources/indexed files; preserve unique app state, classify Samples/system metadata, inspect final dependency confirmation and test retained apps during the approved cutover |
| Complete namespace inventory | Resolve TMBackup, retired volume/root entries, client bookmarks/mounts, current SMB sessions and remaining protocol/app permissions |
| Migration sizing | Separate local data classes from FUSE/provider bytes using trusted indices and bounded metadata; reserve copy/rollback space |
| Recovery gaps | Private-original sample with ACL/xattr checks, Time Machine sample, recurring off-host HA/Jellyfin coverage, restore credentials and approved retention/encryption/cost |
| Permission/identity acceptance | Synthetic role/owner-home matrix, service UID separation and supported svc-prefix migration; no broad recursive ownership changes |
| Writable Hetzner | Full-account role membership, scoped/direct versus NAS gateway qualification, managed-media reconciliation and independent remote-original backup policy |

The next implementation step is the recovery and synthetic permission pilot,
after resolving the readiness gates it depends on. This inspection does not
authorize a production move, ACL change, app removal, new writable mount, restore
into production, volume deletion or RAID redesign.
