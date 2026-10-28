# Usenet, NAS and Plex agent guide

For NAS storage changes, start with the single
[migration entry point](../docs/plan-nas-storage-and-access.md), then read only the
access/protection policies and service runbooks required for that checkpoint.
The next move is the private library to `PrivatePlexLibrary`; the plan records
the user's temporary backup exclusion and NAS-side rename preference.
Do not treat superseded dated gates or the earlier HBS-untouched instruction as
blocking that scoped exception. Other storage work retains its own readiness gates.

## Access and validation

- Use root `just usenet <recipe>` and its private environment/inventory with the
  existing dedicated identities and pinned host keys. Use Safari for QNAP UI.
  Do not substitute SSH-agent credentials or display secrets.
- Read [validation](docs/validation.md) before implementation/deployment work.
  Run the infrastructure `just test` for implementation changes. Report known
  historical secret-scan findings separately; do not waive them or rewrite history.
- Inspect runtime/job activity before storage changes. Preserve active transfers
  and manual SAB pauses. Scope interruptions to the affected operation; do not
  restart the NAS or unrelated services as an audit step.
- Root AGENTS.md owns media privacy, paired-repository checks, signing and Git-lock
  rules. Preserve unrelated edits, staged work, ignored inputs and existing `msg`.
  No PRs; no automatic cleanup of recovery snapshots, credentials or history.

## Migration boundaries

- Prefer an explicit same-filesystem NAS rename after resolving real paths and
  device IDs; fail on cross-device operations instead of silently copying.
  Do not stage NAS payload on the controller or copy it back over the LAN.
- Keep path relocation, account/UID changes and ACL tightening in separate
  checkpoints. Preserve metadata and save exact rollback references. Do not
  recursively copy/hash/chown collections merely to reorganize them.
- Preserve the original SOPS-bound recovery snapshots and separate master keys.
  Use current private inventory after a restore rather than blindly redeploying
  old paths. Required native QTS/package roots remain explicit exceptions.
- The private-library backup exclusion is intentional and temporary. Preserve
  its existing B2 copy; re-seed after the move. A replacement seed that excludes
  this dataset must not trigger deletion of the old mixed backup repository.
  The protection plan owns the complete retirement condition.

## Plex and media operations

- Preserve private Plex library ID 1, its files, metadata, watched state and
  viewer restrictions while changing its path. The managed general profile
  remains limited to library IDs 2/3/4/5. Never put a broad parent/private share
  in a general library. Do not browse or emit private media names or thumbnails.
- Keep automatic trash emptying disabled; do not empty trash to fix a missing
  migration path. Native Plex runtime/package paths may remain supported
  exceptions. Multiple libraries do not imply multiple runtime accounts.
- [Native media](docs/native-media.md) owns acquisition policy and Arr ownership;
  [NAS/Plex layout](docs/nas-plex-layout.md) owns current binds/cache paths;
  [operations](docs/operations.md) owns health and lifecycle recipes.
  Preserve the read-only Storage Box reader, mount-dependent startup, unmounted
  mode-0000 guards, hard-linked objects, receipts, reserves and release limits.
- Do not restore retired publishers/carts, broaden monitored scopes or enqueue
  downloads for validation. Keep Filex quarantine/disabled purge and native
  application authentication; no blanket SSO redirects over native APIs.

## Recovery and retained services

[Scheduled backups](docs/scheduled-backups.md) owns deployed jobs, activity gates,
retention and off-host readback. Native HA archives, app recovery and media
protection are different streams. A settings restore does not prove originals
or whole-NAS recovery. Do not delete/resume acquisition jobs to satisfy a backup.

[Checkout recovery](docs/checkout-recovery.md) owns source/input recovery;
[wiki operations](../docs/operations/wiki.md) owns wiki publication. Wiki sources
must not gain credentials, live APIs, media listings, Docker access or public
exposure. Video Station and Multimedia Console remain retired; remaining share
retirement belongs to the migration plan.
