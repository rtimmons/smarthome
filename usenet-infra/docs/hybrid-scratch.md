# Bounded acquisition scratch

The split layout now uses the approved [300 GB repair volume](repair-spool.md)
for compressed downloads and the upgraded BX21 Storage Box for unpacked output.
Native Arr import uses hardlinks within one container mount. The CX43 VM size,
canonical paths and Plex roots are unchanged. The former root-disk spool is
retained as migration evidence; it is no longer the active download destination.

| Stage | Filesystem and budget |
| --- | --- |
| Download and repair | Volume `/srv/usenet/repair/incomplete`, bound at SAB's unchanged `/data/incomplete`; remaining download bytes **plus one full advertised release for PAR2 replacement**, 5 GiB margin and 30 GiB reserve. |
| Unpack | Existing remote `.acquisition-staging/complete`, outside Movies/TV; 1.25 times advertised release size plus 5 GiB margin and 30 GiB reserve. |
| Native import | A hardlink from staging into Movies/TV, with independent canonical SHA-256 before the staging link is removed. The canonical file remains allocated. |

Both budgets, inodes, mounts, application roots and native hardlink settings must
pass before one item is admitted. The controller waits for verified cleanup
before admitting another. SAB's two `30G` floors remain enabled. This is capacity
admission with expansion margins, not a hard quota for arbitrary archives.

The native containers mount the whole remote library at `/storage`. A container
startup script makes the existing `/library` path an alias to `/storage/Movies`
or `/storage/TV`; no database path or media directory is relocated. Remote cart
sources and native completed-path mappings use `/storage/.acquisition-staging`.
The normal `copyUsingHardlinks` setting is required. Deployment checks real hard
links as each container's application user by changing a tiny probe through one
name and reading the other, since SSHFS inode numbers can differ for aliases.
Native import still owns naming, history and file records. Independent SHA-256
verification and durable source-unlink intent still gate successful cleanup.

## Native hardlink capacity validation

Radarr 6.3's native candidate check reserves the entire file again even when
`copyUsingHardlinks` is enabled. The cart adapter accepts only the exact
`Not enough free space` rejection for a Radarr source in the verified hybrid
layout. It leaves global Arr settings and both SAB floors unchanged.

Before preparing and again before submitting, it requires the canonical mount,
matching source metadata through the common mount, native hardlinks enabled,
no source-date mutation and at least the larger of 30 GiB or Arr's configured
reserve. It creates a unique temporary hardlink to that exact source within writable
staging, requires the POSIX link operation to succeed and verifies unchanged
source/destination metadata, then removes only the probe. SSHFS synthesizes link
counts, so those attributes are not used as proof. Independent server-side inode
and link-count evidence is required for live acceptance of the actual import.
The importer retains read-only access to the canonical view; the verified hybrid
layout gives native Arr one common mount for both paths. Failed probes, local sources, Sonarr candidates and any additional
rejection remain held. The journal retains the capacity/link proof. Native Arr
still performs the real import, followed by independent SHA-256 and exact cleanup.

This addresses the pinned upstream [free-space specification](https://github.com/Radarr/Radarr/blob/v6.3.0.10514/src/NzbDrone.Core/MediaFiles/MovieImport/Specifications/FreeSpaceSpecification.cs);
it does not disable free-space checks globally or authorize library deletion.

## Repair-space failure recovery

PAR2 can rename a damaged file and allocate a complete replacement beside it.
The September 20 admission correction includes that second allocation before
admitting new work. A release that no longer fits waits; do not lower either
reserve or release it manually to bypass the check. An existing reservation is
preserved during recovery rather than reclassified as a new admission.

For the user-approved retained admission, repair ran in a disposable, resource-
limited container against a read-only local source and a new isolated remote
scratch directory. Both parity verification and independent full SHA-256 passed.
`scripts/verified-block-repair.py` then compared the complete files, durably saved
before/after blocks and the original full hash, changed only bounded differing
blocks, and verified the entire local result. The helper rejects shared files,
symlinks, changed inputs and excessive repair volume. Its tested `restore`
function can reconstruct the exact original bytes while the original scratch
identity/path is retained. Recovery receipts document later renames and native
lifecycle changes; do not apply rollback blindly to a canonical/shared file.

Recovery holds the capacity lock and keeps SAB globally paused. Native retry is
allowed only after local verification and a private history/admin snapshot.
Only the newly generated remote repair output may then be reclaimed, against
its exact inventory and verified local replacement. The native replacement job
ID is reconciled into the same reservation with its original admission time;
all other paused requests and held records remain untouched. Recovery writes
must preserve the controller state file’s `usenet` ownership and mode 0600;
verify the normal service identity can read/update it before resuming. The reservation
sets `preserve_failed_payload: true`: a subsequent failure pauses for review
instead of entering ordinary failed-payload reclamation. Normal successful
import/cleanup clears the reservation, so later admissions keep their usual
policy. A durable retry
intent/response prevents blind replay if a request's result is uncertain.

Do not globally resume a failed admitted job before this reconciliation: the
ordinary failed-download recycling path intentionally reclaims failed payloads.
That path must not delete the preserved repair. This recovery procedure does not
authorize editing shared canonical bytes, lowering floors or resetting admission
state. Exact operational evidence stays private under the runtime recovery tree.

## Rejected download cleanup

The explicit `config/catalog/held-payload-policy.json` opts into disposal of
recoverable cart inputs rejected for catalog ambiguity or movie identity
mismatch. The importer only disposes a `source_verified` job with proven current
cart provenance, unchanged exact file inventory, matching completed SAB identity,
no Arr ownership and no prepared/submitted import. Activation exclusions and
historical unmanaged files remain protected. Sources shared by two nonterminal
journals are retained for reconciliation rather than being deleted twice.

Each file receives a durable deletion intent before unlink and a removal receipt
afterward. Interrupted deletion resumes from that intent. Source hashes, identity
holds and SAB history remain; the receipt says `redownload_required`. Discarding
an unusable input is never counted as a successful import. Retrying its old import
is refused; resolve the identity and reacquire the saved request instead of
repeatedly downloading the same rejected release. Earlier individually requeued
requests retain their existing holds. A changed source or failed cleanup is
recorded as an error instead of being silently deleted.

## Deployment and recovery

`just --justfile usenet-infra/Justfile --working-directory usenet-infra
configure-hybrid-scratch` installs the reviewed helpers, stops the two timers
without interrupting active work, and enables the authorized disposal policy.
The one-time migration requires idle workers, no admitted request and every
queued request paused at zero progress. It pauses SAB globally, stops only
SAB/Arr, copies and hashes bounded `__ADMIN__` metadata to the local spool,
preserves the remote originals, changes the incomplete bind and recreates the
affected containers. A private phase receipt prevents blind replay after a
partial migration. Exact request IDs, bytes and categories must match afterward.
Both unmounted fallback paths retain their root-owned mode-0000 protection.

After native hardlink and mount verification, the recipe writes the version-2
staging marker, restores SAB's prior global pause, and captures a guarded encrypted
configuration backup before starting the timers. Independently restore that
archive into an empty private directory to verify new helpers, markers, Compose
override, migration and disposal records. Backup capture alone does not prove a
replacement-host restore. Mount units remain reproducible from the repository.

Rollback requires idle/reconciled work and stopped timers/SAB/Arr. Preserve any
new local incomplete metadata or payload progress before restoring a remote
incomplete binding; the old remote metadata is only a historical snapshot.
Restore the version-1 remote marker and earlier discovery mounts together, remove
only this deployment's native completed-path mappings, and verify paths/queue
before resuming. Never overwrite a newer queue with initial metadata, delete
canonical hardlinks, or start containers against unmounted fallback directories.

Completed movies consume permanent library space. Automatic scratch cleanup
cannot make that space unlimited. A true final-library capacity shortage requires
more canonical storage or an explicit library retention policy; it must never
silently delete completed movies. The split budget keeps this distinct from
recoverable failed inputs and unnecessary temporary copies.
