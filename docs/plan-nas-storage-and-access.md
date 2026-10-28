# NAS storage migration — start here

This is the single entry point and execution queue for NAS storage migration.
Updated October 27, 2026. **Next: move `/share/FromDrobo/loljk` into the new
`PrivatePlexLibrary` share on the NAS, preferably by a same-filesystem rename.**
The move is planned, not completed. Wiki's named-share migration is complete.

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
- Video Station and Multimedia Console are removed. Their leftover Multimedia
  share still needs supported retirement; do not reinstall the apps.
- All local volumes currently share one RAID-5 failure boundary. Creating a share
  does not change redundancy. Physical storage redesign is outside this work.

## FromDrobo data migration

### Next checkpoint: PrivatePlexLibrary

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

### Bounded preparation

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

### Move and verify

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

After this move, choose one bounded service checkpoint from the inventory.
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

Retire Multimedia through supported QTS controls after checking its remaining
samples/system metadata and dependencies. Retain only explicit required platform
exceptions: minimal Public, Container/package paths and homes where needed.
Record each exception's owner, consumer, protection and review trigger.
`Scratch` → `System` remains a later display-label change, not a data move or
permission to recreate the volume. Preserve all stable bindings and snapshots.

## Migration ledger and next actions

| Checkpoint | Status / next action |
| --- | --- |
| Wiki identity and named share | Complete; `f8c7fd4`, followed by SOPS access-check simplification `738901e`; see its completion ledger |
| PrivatePlexLibrary | Next; bounded on-NAS rename plan above, temporary backup exclusion authorized, no live change made by this doc refactor |
| Private-library B2 replacement | After move: initial sync from the new root, verify recovery, then retire only superseded data as specified in the protection policy |
| Unattended app backups | Verify the next eligible NAS/cloud/Forgejo captures and offsite restores, including wiki mapping and a current native QTS export |
| Disk/power/snapshot work | Still unresolved; separate diagnosis before stress tests or broader storage redesign |
| Remaining service and household migrations | Select individually after the private-library checkpoint; household dumping grounds stay deferred |

At each checkpoint record the source/destination, actual principal and references,
what changed, bounded checks, rollback inputs and next action. Separate observed
configuration, proposals and effective-access tests. Use existing `just` recipes,
dedicated credentials and Safari for QNAP UI work. Preserve unrelated checkout
edits, `msg`, recovery history and encrypted private evidence.
