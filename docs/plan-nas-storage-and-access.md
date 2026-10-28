# NAS storage migration — start here

This is the single entry point and execution queue for NAS storage migration.
Updated October 28, 2026. **The private-library path cutover is complete:**
`PrivatePlexLibrary` is registered on the NAS and existing Plex library ID 1
uses its new physical root. Discovery, bounded streaming and AD Ryan synthetic
SMB read/write checks passed. The replacement HBS job now selects the new root;
legacy `Backup 1` still excludes it. The replacement seed started at 15:27 Eastern; retain the old B2 copy.
Next: complete the seed and verify recovery. Wiki's named-share migration is complete.

## Cold-agent continuation

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
2. Refresh read-only NAS health, HBS activity/selections and Time Machine recovery
   status. The stopped-job observations below are dated: legacy `Backup 1` still
   has an enabled daily 02:00 Eastern schedule and can restart automatically.
   Replacement `B2 QuDedup 20261027` is manually scheduled, running since 15:27
   Eastern, capped at 10 MiB/s; the follow-up monitor is paused. Preserve the run
   and do not restart the automation implicitly.
3. Coordinate with **Fix TimeMachine backup failures** and **Diagnose slow b2
   backups** before HBS edits or resumption. This migration chat was explicitly
   authorized to message both. Verify the current recovery decision rather than
   treating a passed Time Machine Verify Backups result as a completed restore.
   The user subsequently accepted the known SATA risk for the new-root seed.
4. Verify completion of the running new-root backup for `/share/PrivatePlexLibrary`, resolving
   to `/share/CACHEDEV2_DATA/PrivatePlexLibrary`. Confirm the exact HBS destination,
   source selection, retention and scheduling against the saved checkpoint.
   Keep the four other selected roots and existing 10 MiB/s limits unless the
   user authorizes a change. The new-root seed started at 15:27 Eastern.
5. After complete coverage, restore a bounded private data/metadata sample to
   an isolated NAS destination and verify it independently without emitting media
   identifiers. A settings-only restore or a seed excluding this dataset cannot
   qualify retirement. Keep the old mixed B2 history until private originals,
   Time Machine and every other required source satisfy the protection policy;
   deletion requires its own exact-target approval.

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
checkpoint. Preserve the stopped replacement backup and the legacy schedule caveat in both backup chats.

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

**Next service checkpoint: `forgejo`.** The user requested continuing share work
while the B2 seed runs. The user subsequently corrected the proposed share grants:
use dedicated `svc-forgejo`, with no explicit ordinary `badmin` RW grant. Establish
and verify that nonadministrative runtime identity **at the current path first**;
then relocate the complete `/share/Container/home-git` recovery unit to the named
service share in a separate checkpoint. Discover the actual assigned UID/GID;
do not rename shared `usenet-deploy` or assume its UID is dedicated to Forgejo.
The runtime gets only its service state, with no backup-share or B2 grant and no
ordinary human/guest SMB grants. Preserve a separately scoped capture reader and
archive writer; verify capture after changing ownership before moving paths.
QTS administrator recovery authority is distinct from an explicit share RW grant.

Independent offsite restore verification passed all 151 archived entries, SQLite
integrity and both repository checks on October 28. An isolated NAS rehearsal
started healthy with no network or published ports and was then stopped. Its
transfer emitted a base64 warning, so startup is not proof of an exact transfer;
the independently verified local restore is retained. Private receipts and a
prepared, unapplied path patch are in `build/forgejo-share-20261028/`. The user created `svc-forgejo` through QTS; its assigned UID/GID is `1006:100`,
with only the `everyone` group and all QTS application/network-service grants
unchecked. The production identity checkpoint passed at 16:18 Eastern: 147
state entries changed owner with inode, size, mtime, mode and xattrs preserved;
Forgejo is healthy as `1006:100` with all capabilities dropped. A synthetic runtime
write passed and archive-directory access was denied. The path remains unchanged.
The fresh pre-change archive independently passed all 151 entries, SQLite and
both repository checks. The post-identity archive also independently passed all 151 entries, SQLite
integrity and both repository checks.

Capture uses a separate short-lived UID 0/GID 100 helper, no network, only
`DAC_OVERRIDE`, read-only service source and a writable Forgejo archive mount.
This is an explicit interim privileged-capture exception pending the dedicated
`svc-forgejo-backup` checkpoint, not a runtime archive grant. The nonroot capability
probe returned zero effective capabilities on this NAS, so it was not used.
Identity rollback metadata and prior scripts are retained privately under the
service root's `identity-checkpoint-20261028`; do not replay them after path changes
without resolving the current root. QTS has now created the empty `forgejo` share on Scratch, with no per-user
SMB grants, guest denied, mandatory SMB encryption and ABE/ABSE enabled. QTS
retains its standard root/administrators access; there is no explicit `badmin`
user grant. Its newly created filesystem root is still mode 0777 with permissive
default ACLs: restrict that empty root before moving service data into it.
The physical path move is the next separate checkpoint. Preserve QTS-created
`@Recycle` and `@Recently-Snapshot`; rename the complete service contents into
the prepared root on the same filesystem, preserving each entry's inode/metadata.
Both persistent and active cron currently point to the original service path.

Refresh capture/cron status and qualify recovery under the new identity, then
enumerate deployment, cron, backup and container path consumers. Save ownership
and permission preimages for the identity checkpoint and exact path rollback for
the later move. Do not move `Usenet/Backups` or its
Forgejo archive subtree while the seed reads them. Preserve both repositories,
LFS, attachments, database, configuration and keys together. A brief Forgejo-only
stop is required for its eventual consistent cutover; prepare exact rollback and
supported share grants before requesting any action-time access approval.

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
| Private-library B2 replacement | New root saved in replacement job; legacy still excludes it. Replacement seed running since 15:27 Eastern with user acceptance of known SATA risk. Retain old history until complete coverage and independent recovery verification |
| Multimedia legacy share | Retired through QTS with data deletion unchecked; backing directory retained; see the 102-byte inventory discrepancy above |
| Unattended app backups | Verify the next eligible NAS/cloud/Forgejo captures and offsite restores, including wiki mapping and a current native QTS export |
| Disk/power/snapshot work | Still unresolved; separate diagnosis before stress tests or broader storage redesign |
| Remaining service and household migrations | Select individually after the private-library checkpoint; household dumping grounds stay deferred |

At each checkpoint record the source/destination, actual principal and references,
what changed, bounded checks, rollback inputs and next action. Separate observed
configuration, proposals and effective-access tests. Use existing `just` recipes,
dedicated credentials and Safari for QNAP UI work. Preserve unrelated checkout
edits, `msg`, recovery history and encrypted private evidence.
