# NAS storage migration — start here

This is the single entry point and execution queue for NAS storage migration.
Updated November 13, 2026. **The private-library path cutover is complete.**
`PrivatePlexLibrary` is registered on the NAS and existing Plex library ID 1
uses its new physical root. Discovery, bounded streaming and AD Ryan synthetic
SMB read/write checks passed. The replacement HBS job now selects the new root;
legacy `Backup 1` excludes it. The QuDedup seed finished November 3 and a
bounded private-library restore passed November 10.
Wiki's named-share migration is complete.
Forgejo now uses its named share and dedicated runtime identity; see the
[service checkpoint](#service-data-and-archive-migration) for verification and remaining backup work.

## Cold-agent continuation

**November 13, production B2 verified.** QuDedup completed two daily
backups, passed HBS Quick Check and restored a settings sample. Backblaze
confirmed deletion of the legacy `Backup 1.qdff` folder. Time Machine recovery
remains unverified. See the
[retirement verification](../usenet-infra/docs/scheduled-backups.md#november-13-retirement-verification).

**November 13, native QTS export repaired.** The firmware's weekly job was
restored to active cron and produced a fresh settings export at 13:23 Eastern.
All three encrypted NAS settings archives passed Hetzner readback. An
independent download and decrypt verified the new QTS export and both HBS
databases.
See the [repair and verification](../usenet-infra/docs/scheduled-backups.md#november-13-native-qts-export-repair).

**November 11, daily B2 schedule transferred.** `B2 QuDedup 20261027`
is scheduled daily at 02:00 Eastern and `Backup 1` is manual. The user
allowed skipping the Time Machine restore for the schedule transfer and
initially retained the old B2 history. The [backup runbook](../usenet-infra/docs/scheduled-backups.md#november-11-daily-schedule-cutover)
records the sample verification, live schedule readback and pending recovery work.

**November 9, QTS share batch complete:** All 14 approved empty shares were
saved and verified against the [prestage checklist](nas-qts-prestage.md). The
11 restricted local account forms are ready for the operator's password entry
and submission. Follow with account disablement, UID and privilege readback,
and a fresh native QTS settings export. No service cutover accompanied the
share creation. HBS seed completion is observed; production recovery is open.

**October 29, next account checkpoint prepared:** Filex and the restricted
backup-account checkpoint are committed as `e9f2703`. The next candidate is
`svc-discovery`, limited to the DNS scanner's existing configuration and state
binds; the resolver retains its current identity. No discovery account or live
identity change has been made.

The scanner's `Timeout` was traced to validation of an unknown descendant under
an exact public certificate alias. Upstream DNS owns those public descendants.
A later bounded probe passed after the upstream result was cached. The repair
limited negative tests to the owned namespace while retaining exact A/AAAA,
local and public control queries, and delegated AD checks.
The deployed repair also included optional scanner-only UID/GID support. No
override was selected at the October 29 checkpoint.

The user approved the scanner-only stop, private credential-bearing checkpoint
and repair. The quiesced checkpoint independently verified all 35 files (38
entries, 401,711 bytes), and the original scanner resumed. At 16:20:58 Eastern,
the scanner reported successful full verification, 74 records and a healthy
container after repair deployment at the existing UID. Independent settled-state
acceptance also passed:
pending journals absent, recent full verification, unchanged credentials and
manual/AD policy, exact original mounts, UID 1004:GID 100, group 100 only,
zero effective capabilities and the original security restrictions. The NAS
resolver remained healthy with the same container ID and start time.
The QTS account form was prepared for review. Account creation and permission
changes remained pending at this checkpoint.
Preserve learned state and any pending journal; qualify scanner health before
changing its identity. Never stop either resolver for this checkpoint.
Evidence is retained privately in `build/dns-discovery-20261029/`, including
`pre-repair-checkpoint/` and the post-repair verification receipt. Root tests,
all 37 DNS tests and wiki checks passed. The 592 infrastructure unit tests passed
(12 skipped), and the current-source secret scan passed. The full infrastructure
recipe still reports the documented historical secret-scan findings.

The captured scanner bind roots contain 31 objects: two mode-0777 directories,
28 mode-0600 files and one mode-0666 worker lock, all 1004:100. Both directories
also carry broad default ACLs. Ownership alone would leave directory replacement
access exposed. Before runtime cutover, prepare a separate approved permission
checkpoint for these two roots: access mode 0700 and default-ACL mask/other zero,
preserving named ACL entries. Keep the scanner stopped between owner change and
permission hardening. Refresh the manifest after stopping; reject unexpected
entries, symlinks and multiply linked files. Preserve exact rollback metadata,
content and non-ACL xattrs; access/default ACL changes must be recorded as
intentional changes, not claimed as unchanged metadata. Resolver and runtime
deployment-parent ownership stay unchanged. No such hardening has run yet.

**October 29, 16:12 Eastern hardware refresh:** new `ata2` interface-fatal/reset
bursts map approximately to 14:16 and 15:33; the former includes three explicit
`sdb` read I/O errors. Links recovered, and RAID remains 4/4, degraded zero,
sync idle. The fault remains unresolved. Replacement HBS is still Running
(approximately 796.85 GB processed); legacy backup finished at 16:03:17.
Both complete job configurations are unchanged from the 12:29 baseline.
No storage move or stress test is authorized by these observations.

**October 29, 12:29 Eastern read-only refresh:** the replacement seed remains
Running, with approximately 690 GB processed of 4.68 TB (decimal). Legacy
`Backup 1` restarted on its enabled 02:00 schedule and is also Running. Both
jobs retain their saved source selections, destinations and 10 MiB/s limits.
Neither run was stopped or edited. Seed completion and production recovery
remain unqualified; retain old B2 history.

The current kernel log contains a newer `ata2` failed-read/failed-write and
link-reset burst, approximately October 28 at 22:23 Eastern, after the previously
documented 04:22 burst. The link recovered and the data RAID still reports 4/4
members, degraded zero and sync idle. Those observations do not clear the fault.
Do not begin further storage moves or stress tests on this evidence. The existing
seed was authorized with known SATA risk; no broader hardware acceptance is implied.
The related backup chats' latest handoffs still leave Time Machine restoration
and post-verification error checks open; their monitor remains paused.
Private evidence: `build/nas-seed-health-20261029/seed-health-output.txt`
(remote return code zero). The SATA wall-clock estimate uses current time minus
uptime; it is not a direct event timestamp or a complete historical log.

**October 29 application-backup check:** Forgejo's latest verified success is
still the October 28 manual capture, completed at 16:35:54 Eastern (151 files).
With the 23-hour gate and minute-23 cron, the first eligible slot is October 29
at 16:23 Eastern, provided no intervening capture resets the clock. Persistent
cron has the correct new path; reading the active admin spool was denied and
the backup log was empty. No unattended new-path capture is qualified yet.

NAS status/logs record a successful October 28 capture at 16:11:11 Eastern,
with all three scopes verified off-host; the current worker mounts `/share/wiki`
read-only and its cron is running. Cloud status/journal record success at
17:03:46 Eastern, verified ciphertext, an active timer and subsequent freshness
skips. These checks establish capture/status and scheduler evidence, not a new
independent restore or complete unattended qualification. The native QTS export
inside that capture dates from October 25 at 15:47:54 Eastern and predates the
later account/share changes. The November 13 checkpoint above records the
subsequent repair. Private evidence is retained in
`build/nas-unattended-20261029/`.

The dedicated capture-account scope is now documented in the
[checkpoint proposal](forgejo-backup-account-checkpoint.md). Source review found
that the existing uploader also writes status/receipts and prunes local archives,
and installation assumes archive owner UID 1004. The account switch must resolve
that handoff and durable source-read permissions; simply changing the worker UID
would not satisfy the target role model. Later this day, the user approved and
created restricted `svc-forgejo-backup` (1007:100) through QTS; application/share
denials and filesystem denial of source/archive access were independently checked.
Worker activation and its permission changes remain pending; see the checkpoint.

**Prior handoff — October 28, after Forgejo verification and publication:**
Forgejo's identity and named-share checkpoints are complete, committed separately
as `011ced1` and `4ceb02f`. It runs healthy as `svc-forgejo` (`1006:100`) at
`/share/forgejo`. The final new-path archive independently passed all 151 file
checks, SQLite integrity and both repository checks. Full repository tests passed;
the updated runbook was published as wiki release `20261028T203752Z-129Aie`.
Do not repeat account creation, ownership changes or the share move. The
[service checkpoint](#service-data-and-archive-migration) owns exact boundaries,
rollback references and the temporary privileged-capture exception.

**Next Forgejo work:** qualify an unattended capture at the new path, then scope
the dedicated `svc-forgejo-backup` account. Cron runs at minute 23 each hour but
skips capture until the latest verified success is at least 23 hours old; a manual
backup resets that clock and does not prove scheduler execution. Inspect current
status and cron evidence before forcing another capture. The dedicated capture
principal needs read-only service access, archive write access and bounded
Forgejo lifecycle control; keep offsite credentials with the separate uploader
and grant no archive access to the runtime. Preserve the existing archive path
while the B2 seed runs. No unattended-capture qualification or backup-account
cutover is claimed yet, and no new monitor was enabled.

At the final read-only HBS inspection, the replacement seed was still Running
with the same five sources, destination and 10 MiB/s limit; legacy `Backup 1`
was Stopped. These are dated observations, not a fresh status check. The seed
completion and recovery sequence below remains open.

**October 28, 15:26 Eastern continuation:** saved `PrivatePlexLibrary` as the
fifth source of `B2 QuDedup 20261027` through Safari/HBS. Independent full job
comparison found only `backup.source` changed; legacy `Backup 1` is unchanged.
Destination remains `RynapQNAP` → `/B2 QuDedup 20261027.qdff`, with 30 versions,
snapshots, ACL/xattrs, manual scheduling and 10 MiB/s preserved. Both backup
chats cleared the source edit; Time Machine restore validation remains open.
The user then explicitly directed proceeding despite SATA problems. The seed
started through HBS at **15:27:48 Eastern**; independent read-only job history
confirms Running. No completed seed or production restore is claimed.

Read-only health checks at 15:18–15:19 Eastern found data RAID 4/4, degraded zero,
sync idle and the expected new-root inode. The latest matching kernel SATA reset
maps to the already documented 04:22 burst; no later matching error was observed
in the current kernel log. This does not resolve the hardware fault. The user
accepted proceeding with this seed despite that risk; this is not hardware-health
clearance. Legacy 02:00 scheduling is still enabled, and the follow-up monitor
remains paused. The sequence below now resumes at seed completion and recovery verification.

The move and access changes are accepted, including Ryan's successful Mac
connection. **Do not repeat the rename, recreate the share/library, or replay
private mutation scripts.** The preparation/move procedure below is retained as
execution history and rollback context, not the next task.

1. Read root and `usenet-infra/AGENTS.md`, then the protection-policy exception
   and the backup runbook's **October 28 migration handoff** section. On a fresh
   checkout run `just checkout-prepare`; private evidence remains outside Git
   through the `build/` compatibility link. Preserve unrelated changes and `msg`.
2. Refresh read-only NAS health, HBS activity, source selections and Time Machine
   recovery status. The November 11 checkpoint above gives the current schedule.
   The replacement seed began October 28 at 10 MiB/s and finished November 3.
   Keep the follow-up monitor paused.
3. Coordinate with **Fix TimeMachine backup failures** and **Diagnose slow b2
   backups** before HBS edits or resumption. This migration chat was explicitly
   authorized to message both. Verify the current recovery decision rather than
   treating a passed Time Machine Verify Backups result as a completed restore.
   The user subsequently accepted the known SATA risk for the new-root seed.
4. Reconcile the completed run with the exact destination, source selection,
   retention and scheduling in the saved checkpoint. The intended new root is
   `/share/PrivatePlexLibrary`, resolving to
   `/share/CACHEDEV2_DATA/PrivatePlexLibrary`.
   Keep the four other selected roots and existing 10 MiB/s limits unless the
   user authorizes a change. The new-root seed started at 15:27 Eastern.
5. The November 10 bounded private-library sample passed independent data and
   metadata checks in an isolated NAS directory. The November 13 checkpoint
   records the user's decision on the old mixed B2 history and the remaining
   Time Machine recovery check.

Private evidence is in `build/private-library-migration-20261028/cutover/`:
`hbs-before-output.txt`, `hbs-after-both-output.txt`, `rename-output.txt`,
`share-after-output.txt`, Plex pre/post receipts, `add-ad-root-acl-output.txt`,
and `ad-smb-acceptance.json`. These include sensitive operational details; never
stage them. `share-after-output.txt` is the original ACL preimage, while the
additive ACL receipt records the final approved root/default entries. The
existing `build/backup-diagnosis-20261027/nas-runner.py` captures remote results
privately; inspect its reported remote return code because the runner itself
can exit zero on remote failure. Use the repository's dedicated NAS environment,
identities and pinned host keys, and Safari for supported QTS/HBS edits.

Remaining filesystem work is separate: broad original ACL entries were preserved,
not hardened. Only AD Ryan's root/default entries were added; descendant access
was not recursively changed or comprehensively tested. Do not silently tighten
permissions as part of backup setup. The last published wiki release for access
acceptance was `20261028T153306Z-xC31Rl`. The backup-start handoff was published
in release `20261028T193420Z-Z1J3Ac`; Multimedia retirement is recorded below.

## Read only what the next change needs

| Document | Owns |
| --- | --- |
| This plan | Current decisions, next move, sequencing, acceptance and rollback |
| [Access model](plan-nas-access-model.md) | Target share catalog, accounts, roles and expected denials |
| [Data protection](plan-nas-data-protection.md) | Recovery policies and the private-library backup pause/re-seed/retirement sequence |
| [Service inventory](nas-service-inventory-2026-10-27.md) | Dated runtime, mount, writer and backup observations; reconcile only affected consumers |
| [Wiki completion ledger](nas-wiki-share-migration-2026-10-27.md) | Completed wiki migration and recovery evidence |
| [Storage preflight](nas-preflight-2026-10-25.md) | Unresolved hardware, power and snapshot findings |
| [Media-app retirement](nas-media-retirement-2026-10-25.md) | Completed package removal and remaining share retirement |

Use the [NAS/Plex runbook](../usenet-infra/docs/nas-plex-layout.md) and
[backup runbook](../usenet-infra/docs/scheduled-backups.md) for operations.
Dated inventories are evidence, not another active work queue. Older timelines
and superseded proposals remain in Git history rather than this plan.

## Decisions and current status

- Keep the deployed Samba AD on HA, Authelia and QNAP domain architecture.
  Preserve identities, account/library IDs, keys and recovery logins.
- Use flat named service shares and separate archive shares; no AppData umbrella.
  Account/ownership changes and path moves are separate checkpoints.
- Ryan maintains private media; Ryan and Michael maintain general media.
  Native Plex may retain its supported runtime identity; multiple libraries do
  not require multiple NAS runtime accounts. Viewer permissions are separate.
- Wiki is at `/share/wiki`, running as `svc-wiki` 1005:1000. Independent recovery,
  backup mount mapping and access checks passed. Unattended backup qualification
  remains a follow-up, not a prerequisite for the private-library move.
- Video Station and Multimedia Console are removed. The leftover Multimedia
  share was retired through QTS on October 28; do not reinstall the apps.
- All local volumes currently share one RAID-5 failure boundary. Creating a share
  does not change redundancy. Physical storage redesign is outside this work.

## FromDrobo data migration

### Current checkpoint: PrivatePlexLibrary

**Scope:** only the private library's physical root, named share, required Plex
path references and affected backup selections. Do not migrate the rest of
FromDrobo, create a second Plex library, or rename runtime accounts in this step.
The chosen name supersedes the earlier proposal `PrivateLibrary`.

The user states this data is static and already backed up on B2, and accepts
turning off backups of this dataset during migration. **Move first; re-seed
from the new location later.** Completing the ongoing replacement backup seed,
new snapshots, a new full restore drill or disk/power remediation is not a
prerequisite for this specifically authorized bounded move. The unresolved
storage findings remain real; this exception does not clear them for other
migrations, scrubs, rebuilds or pool changes. Stop if fresh evidence shows an
active I/O failure, unavailable source or a different operation than planned.

### Completed move procedure: bounded preparation

1. Resolve the source's real directory, filesystem/device and mount boundaries.
   The earlier mapping is GPvQNAP / `/share/CACHEDEV2_DATA`; verify it rather than
   assuming it. Select an absent destination directory on that same filesystem,
   normally `/share/CACHEDEV2_DATA/PrivatePlexLibrary`. Use shallow metadata and
   existing size summaries, not a whole-library checksum scan.
2. Save private copies of the source root ACL/ownership, QTS share configuration,
   Plex library ID 1 paths and privacy grants, and affected deployment inputs.
   Identify current NAS Plex and any HA/container consumer of this exact subtree;
   do not assume the broad `hass` FromDrobo mount is unrelated. No media titles,
   filenames, thumbnails or raw token-bearing exports belong in Git.
3. Inspect both legacy and replacement HBS jobs, their active runs and retention
   actions. Record the existing B2 backup/catalog/key references. Use the
   [temporary backup exception](plan-nas-data-protection.md#private-library-migration-exception)
   to exclude this dataset, preserving the existing B2 recovery copy. No new seed
   or full download is required before the move.
4. Confirm QTS can register the new share against the intended existing directory
   on the same volume. Plan a brief private-library interruption if needed and
   quiesce affected readers/writers and scans. Avoid stopping unrelated services;
   a whole Plex-server stop affects general viewers and needs a concrete window.

### October 28 cutover — completed path change

The user explicitly authorized proceeding despite Time Machine corruption and,
separately, the new `ata2` read-error/link-reset burst around 04:22 Eastern.
The link recovered; RAID reported 4/4 members, degraded zero, sync idle before
the move. This accepts the bounded rename risk, not a storage-health clearance.
Both backup chats released HBS editing for this migration. Time Machine recovery
remains separate, with restore/error checks still pending at handoff.

- Excluded only the private source from both HBS jobs after stopping the running
  legacy `Backup 1` at 10:42 Eastern. The replacement was already stopped.
  Exact before/after job comparisons changed only source selections and UI state;
  destinations, retention, schedules and 10 MiB/s caps were preserved. Four other
  sources remain selected. Both jobs are stopped at handoff; legacy daily 02:00
  scheduling remains enabled, replacement remains manual. Coordinate resumption
  with the Time Machine owner; do not resume the replacement seed automatically.
- Used NAS-side `renameat2(RENAME_NOREPLACE)` to move the old physical root to
  `/share/CACHEDEV2_DATA/PrivatePlexLibrary`. Device `64525`, inode `38600710`,
  UID/GID `1000:100`, mode `0777` and root/default ACLs were preserved. Old path
  is absent, with no compatibility alias; no copying or recursive metadata edit.
- Registered the existing directory through QTS on GPvQNAP. The user explicitly
  approved RW for existing local `badmin` and local `ryantimmons`, guest denial,
  no unrelated-user grant, and access-based share/folder visibility. QTS retains
  native root/administrator exceptions. A separately approved follow-up added
  AD Ryan RW and an additive root/default ACL grant, verified below. Broad
  existing filesystem ACLs remain a separate review and do not provide private host-process isolation.
- Updated existing Plex library ID 1 through its API. Library identity, settings,
  privacy preferences and other library roots are unchanged. Filesystem and
  scheduled scan triggers were briefly paused and restored; auto-trash remains
  off. Requested a normal private-library refresh to discover moved file paths.
- A refreshed sample under the new root served 65,536 bytes with HTTP 206 wholly
  on the NAS. This proves a bounded Plex file read, not client codec playback or
  whole-library recovery. Discovery subsequently finished; all
  5,522 private media-part records use the new root, with none on the old root.
- The managed general profile still sees exactly IDs 2/3/4/5 and gets HTTP 403
  for ID 1. AD Michael is denied at authenticated SMB tree connect. `svc-wiki`
  is denied at session setup, which is not a per-share authenticated test.
- The initial local-only share grant denied AD Ryan, explaining the Mac's
  no-such-share result. The user explicitly approved AD Ryan RW on the share,
  then an additive read/write/traverse entry on only its root/default ACLs.
  Encrypted SMB3 synthetic create, byte-matching readback and delete now pass
  for AD Ryan; AD Michael remains denied. No existing media was read for this
  SMB test; existing descendant access and client playback are not qualified by it.
  The user subsequently confirmed the Mac connection worked with the AD grant.
- QTS's share editor initially rewrote the root/default ACLs despite recursive
  updates being unchecked. Restored the exact preimage, then added only the
  approved AD Ryan entries with a NAS-local helper. Every existing ACL entry,
  owner, mode and inode was preserved; no recursive ACL edits were made.
- Live HA Plex roots and NAS container binds do not select the private subtree.
  General media roots and broad FromDrobo deployment inputs remain unchanged.

Raw preimages, job snapshots, ACLs, Plex observations and mutation receipts belong
in ignored `build/private-library-migration-20261027/` and
`build/private-library-migration-20261028/`, not Git. No old B2 history was deleted.
Replacement seed completion without this dataset cannot authorize retirement.

Documentation validation passed (`just wiki-check`). An earlier root `just test`
failed the unrelated printer preview-latency assertion: 111.9 ms against a
100 ms budget. The final pre-commit rerun passed the complete root suite,
including all 225 printer tests and all container checks, without printer
source changes. Its log is retained privately as `cutover/commit-tests.log`.

**Resume here:** follow the cold-agent continuation above for the new-root seed
and bounded data/metadata restore. Filesystem ACL tightening is a separate
checkpoint. Preserve the running replacement seed and the legacy schedule caveat.

### Completed move procedure: move and verify

1. Keep ownership/account changes separate. Perform an explicit **NAS-side
   same-filesystem directory rename** to the absent destination; use an operation
   that fails on cross-device moves rather than silently falling back to copy.
   Register `PrivatePlexLibrary` through supported QTS controls against that
   directory. If registration cannot use this layout, reverse the rename and
   resolve that specific constraint before substituting a different method.
2. Preserve the moved tree's metadata. Set the new share's explicit grants from
   the access model; do not blindly apply QTS ACL changes to every descendant.
   Record inherited/broad filesystem grants separately: a new SMB share alone
   does not remove access through host processes or alternate mounts. Keep any
   required ACL tightening as its own reviewed checkpoint.
3. Update the existing Plex library ID 1 root and every discovered consumer of
   the old path. Preserve library metadata, watched state and viewer grants.
   Keep automatic trash emptying disabled; do not empty trash or recreate the
   library to resolve a transient missing path. Update durable deployment inputs
   so a later deploy cannot restore the obsolete path.
4. Verify the renamed directory retains its device/inode, resolves through the
   new share, and is no longer exposed at the old FromDrobo path. Check Plex
   discovery/playback with a bounded sample, Ryan's intended access, denial to
   general viewers and unrelated SMB users, and local bind/host access separately.
   Confirm general libraries and unaffected backups remain operational.
5. Record completion, remaining ACL exceptions and backup exclusions in the
   ledger below. Do not wait for a new B2 initial sync to accept the path move.

No media payload should pass through localhost or be copied back over the LAN.
Do not use Finder copy, recursive rsync or a copy-and-delete fallback for this
same-filesystem move. If the paths are actually on different filesystems, stop
and choose a NAS-local alternative explicitly; a share is not itself a filesystem.
Do not leave a permanent old-path alias that bypasses the private share boundary.

### Rollback

Before accepting new writes, quiesce the affected consumers, reverse the rename
on the NAS and restore the saved path/share configuration. Reconcile any later
writes before rollback. Restore old-path backup selections only after the source
is back and the job is safe to resume. Removing a failed share definition must
not delete its backing data. Retain the existing B2 history throughout.

## Service-data and archive migration

**Forgejo named-share cutover completed October 28, 16:31 Eastern.** The
complete service recovery unit now lives at `/share/forgejo`, physically
`/share/CACHEDEV1_DATA/forgejo`. The runtime uses dedicated QTS-local
`svc-forgejo` (`1006:100`), with only the `everyone` group, no capabilities,
and no archive mount or backup/cloud grant. QTS application/network-service
grants are unchecked. There is no explicit `badmin` user RW grant or ordinary
human/guest SMB grant; QTS retains its standard root/administrators recovery
access. SMB encryption is mandatory and ABE/ABSE are enabled.

Identity and path changes were separate checkpoints. At 16:18 Eastern, 147
state entries changed owner with inode, size, mtime, mode and xattrs preserved;
health and synthetic runtime-write/archive-denial checks passed at the old path.
Fresh pre-identity and post-identity archives independently passed all 151 file
checks, SQLite integrity and both repository checks. An isolated startup under
1006:100 also passed database/cache health with no network or published ports.
Its earlier transfer emitted a base64 warning, so startup is not an exact transfer
proof; the separately downloaded and verified archives remain the trusted copies.

QTS created its root at mode 0777. Before moving data, the empty root was restricted
to deployment owner 1004:100, mode 0700, with default group/mask/other permissions
zero; its original ACL/xattr preimage was saved. The runtime owns `data` and
`config`, while the deployment operator maintains the service definition/helpers.
QTS-created `@Recycle` and `@Recently-Snapshot` were retained. All 17 service
entries moved by same-filesystem rename with inode, owner/group and mode preserved.
The deployment-account rename attempt was denied by NAS permissions; automatic
rollback restored the old paths and healthy service before a bounded root helper
completed the move. No recursive data ACL change accompanied the path move.

Deployment, capture and both cron tables now use `/share/forgejo`; management and
capture refuse an absent or mismatched QTS share mapping. The archive destination
remains `/share/Usenet/Backups/automatic/forgejo`. Do not move that archive subtree
or change HBS selections while the replacement seed reads it. Post-move checks
verified runtime writes, zero effective capabilities, retained
metadata on all moved entries, absence of old-path payload and clear locks. Both
cron tables have exactly one new-path job and unchanged unrelated entries; wiki
UID 1005 and unrelated UID 65534 cannot read service data. The final new-path
backup at 16:34 Eastern was independently downloaded and
decrypted: all 151 entries, SQLite integrity and both repositories passed. Restored
Compose and all three helper scripts match current source. Forgejo remained
healthy after capture/restart. Manual backups do not qualify an unattended run.

Capture uses a separate short-lived UID 0/GID 100 helper, no network, only
`DAC_OVERRIDE`, read-only service source and a writable Forgejo archive mount.
This interim privileged-capture exception remains pending the separately scoped
`svc-forgejo-backup` checkpoint. A nonroot capability probe returned zero effective
capabilities on this NAS, so it was not used. Do not rename shared `usenet-deploy`
while other runtimes still depend on it.

Private evidence is under `build/forgejo-share-20261028/`; the earlier prepared
path patch is superseded. The service root retains `identity-checkpoint-20261028`,
`path-checkpoint-20261028` and separate cron preimages. Do not replay old scripts:
resolve the current root first. For path rollback, acquire both migration/backup
locks, stop only Forgejo, reverse the recorded service-entry renames, restore the
old-path helper scripts, reconcile only Forgejo's entries in each cron table,
and recreate Forgejo at the old path with UID 1006:100. Preserve later writes,
QTS metadata, archive history and all unrelated cron entries. Identity rollback
is a separate operation using its saved owner/mode/xattr metadata; never silently
combine it with path rollback.

Next: qualify an unattended capture at the new path and separately scope the
dedicated capture account. Continue the private-library seed completion/restore
checks above; the old mixed B2 history stays retained. The
[dedicated capture-account checkpoint](forgejo-backup-account-checkpoint.md)
records restricted account creation and scopes the pending worker activation.

**October 29 Filex account cutover completed, verified 13:13 Eastern:**
The user created QTS-local `svc-filex` (1008:100, only `everyone`) with the
prepared network/application restrictions and no share grants. The NAS SFTP
runtime now uses that identity. Paths, SFTP login `filex-staging`, host/client
keys, image and cloud configuration are unchanged. The cloud queue and SFTP
connections were zero immediately before the stop. Current NAS keys, `.env` and
Compose matched an independently decrypted retained offsite checkpoint, with
all 469 manifest hashes verified, before the identity change.

Exactly 24 entries changed owner: staging root plus 20 descendants, and key root
plus two keys. Device/inode, group, mode, size, mtime, xattrs and key hashes were
verified unchanged. Deployment root remains 1004:100 mode 0700. The new runtime
is healthy, has zero effective capabilities and NoNewPrivs, a read-only root,
read-only key bind and the same staging-only writable bind. Pinned-host SFTP
synthetic create, write, byte-matching reads, rename and cleanup passed. This is
bounded client acceptance, not a whole-staging content scan or authenticated SMB
privacy test. No newer SATA event appeared; the complete historical burst ends
with `EH complete` at uptime 282681.567948. The initial guard stopped before any
mutation because it had selected the slightly earlier link-up message.

Private inventory now sets `qnap_filex_runtime_account: svc-filex`; preserve it.
`just usenet configure-filex-nas` reconciles only the NAS endpoint. Named-account
mode requires preprovisioned access and preserves key permissions. Root
`just test` passed; infrastructure checks passed except documented historical
secret-scan findings, while current-source scanning passed. Evidence and scripts
are under ignored `build/filex-identity-20261029/`; the NAS rollback preimage is
`/share/Container/usenet/filex-sftp/identity-checkpoint-20261029`.

For rollback, stop only SFTP after an idle check, reconcile later writes, restore
only the enumerated owners and saved `.env`, remove only the private runtime
account override, then restart and test the old identity. The strict metadata
helper refuses later differences; synthetic acceptance itself changes staging
root mtime, so reconcile that known change rather than blindly replaying it.
Keep every checkpoint and the new account until rollback is accepted. This
checkpoint does not move a share, alter HBS or activate the Forgejo backup worker.

For each bounded service checkpoint, use the inventory to identify consumers.
Preserve Forgejo as a complete recovery unit: database, repositories, LFS,
attachments, configuration and keys. Keep capture producers, archive uploaders,
runtime principals and directory-lookup accounts distinct. Do not rename
`usenet-deploy` while runtimes still share its UID or login dependencies.

Future FromDrobo work separates selective media, playback cache, transfer
staging and remote views. A Hetzner FUSE mount is a remote namespace, not local
payload to copy. Writable remote-media and full-account roles remain in the
access model; selecting human full-account members is still open.

## Legacy-share retirement and System label

Defer household-file sorting, Public, personal homes and unclassified FromDrobo
contents. The two known Public folders belong to Ryan, not shared Documents;
qualify his canonical home and protection before moving them. Preserve enabled
homes and the deployment SSH home/key dependency.

Multimedia share retirement completed October 28 while the replacement B2 seed
continued running. Read-only checks found no HBS source, container bind or Plex
library-root reference. QTS removed only its share definition with **Also delete
the data unchecked**. The physical `/share/CACHEDEV1_DATA/Multimedia` directory
remains, with unchanged device/inode, owner and mode. Aggregate file inventory
changed from eight files / 2,053,473 bytes to seven / 2,053,371 bytes during QTS
removal; the missing 102-byte file was not individually identified. No file-content
identity or byte-for-byte preservation claim is made. Preserve the remaining
files; no payload deletion was requested. The share configuration preimage and
sanitized checks are retained privately in `build/multimedia-retirement-20261028/`.
Rollback is supported QTS registration of that existing directory using the saved
share settings, subject to approval of restored access. Review after QTS/package
updates for automatic recreation; the removed apps must stay absent.

Retain only explicit required platform
exceptions: minimal Public, Container/package paths and homes where needed.
Record each exception's owner, consumer, protection and review trigger.
`Scratch` → `System` remains a later display-label change, not a data move or
permission to recreate the volume. Preserve all stable bindings and snapshots.

## Migration ledger and next actions

| Checkpoint | Status / next action |
| --- | --- |
| Wiki identity and named share | Complete; `f8c7fd4`, followed by SOPS access-check simplification `738901e`; see its completion ledger |
| PrivatePlexLibrary | Path/share/Plex cutover complete; bounded stream and general-profile denial pass; discovery and AD Ryan synthetic SMB read/write passed; existing descendant access remains unqualified |
| Private-library B2 replacement | QuDedup seed and bounded restore passed. Daily coverage transferred November 11. Backblaze confirmed legacy folder deletion November 13. Time Machine recovery remains unverified |
| QTS batch preparation | [14 empty shares saved and verified](nas-qts-prestage.md); 11 restricted account forms ready for the operator's password entry and submission |
| Multimedia legacy share | Retired through QTS with data deletion unchecked; backing directory retained; see the 102-byte inventory discrepancy above |
| Unattended app backups | Check the next weekly QTS export and continue qualifying scheduled NAS/cloud/Forgejo recovery |
| Disk/power/snapshot work | Still unresolved; separate diagnosis before stress tests or broader storage redesign |
| Remaining service and household migrations | Select individually after the private-library checkpoint; household dumping grounds stay deferred |

At each checkpoint record the source/destination, actual principal and references,
what changed, bounded checks, rollback inputs and next action. Separate observed
configuration, proposals and effective-access tests. Use existing `just` recipes,
dedicated credentials and Safari for QNAP UI work. Preserve unrelated checkout
edits, `msg`, recovery history and encrypted private evidence.
