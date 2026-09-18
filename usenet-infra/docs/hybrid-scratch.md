# Bounded acquisition scratch

The split layout keeps compressed downloads on the existing VM and unpacked
output on the existing Storage Box. Native Arr import uses hardlinks within one
container mount. This avoids keeping archives, unpacked output and another full
canonical copy on the same nearly full remote filesystem. Neither VM nor Storage
Box is resized. The original library paths, Plex roots and canonical bytes stay
in place.

| Stage | Filesystem and budget |
| --- | --- |
| Download and repair | Local `/srv/usenet/downloads/incomplete-local-spool`, bound at SAB's unchanged `/data/incomplete`; remaining download bytes plus 5 GiB margin and 30 GiB reserve. |
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
