# Usenet, NAS and Plex agent guide

Read the [current plan and closure criteria](../plan.md), then [native media](docs/native-media.md),
[NAS/Plex layout](docs/nas-plex-layout.md) and [scheduled backups](docs/scheduled-backups.md).
Use [operations](docs/operations.md) for additional commands and
[validation](docs/validation.md) for accepted behavior and remaining evidence.

## Media privacy in commits

Never commit real media titles, release names, filenames, title-derived field
names, or identifying external catalog links/IDs from live operations. Use neutral
aliases such as `media-001` and descriptive keys such as
`failed_download_allocated_bytes` in receipts, documentation, tests derived from
live data, and commit messages. Keep exact operational filenames and alias
mappings in ignored private evidence and runtime journals. Review the entire staged
diff for these identifiers before committing; a generic secret scan does not
establish media privacy. Synthetic tests may use clearly invented fixture names.

Redacted receipt paths are aliases, not executable paths. Resolve actual paths
through exact native job/file IDs privately before operating on files. Historical
operational hashes remain dated evidence about the original inputs, not hashes
of subsequently redacted documents. Preserve private bound recovery snapshots
unchanged. Do not commit the private replacement map used for a privacy rewrite.

## Access and validation

- Use root `just usenet-*` recipes or `just --justfile usenet-infra/Justfile
  --working-directory usenet-infra ...`. Native/catalog recipes retain their
  unprefixed names at the root (`just native-status`, `just native-pull`).
  The private `.env` and ignored Ansible
  inventory select dedicated cloud/NAS identities and verified host keys.
  Do not substitute SSH-agent credentials or print tokens/configuration secrets.
- Run the infrastructure `just test` recipe for implementation changes. It
  includes unit tests, shell/YAML checks, deployment syntax and a secret scan.
  The full scan currently fails on two documented historical RSA keys; report
  that result separately from passing tests. Do not add exceptions or rewrite
  history to make it green. `scripts/secret-scan --no-history` explicitly checks
  current sources/index only. See `docs/security-findings.md`.
- Runtime status must be checked before changing storage or restarting services.
  Preserve active transfers and manual SAB pauses. Scope restarts to the affected
  Usenet services; do not restart the NAS, Plex or unrelated containers by default.

## File ownership and recovery

- Radarr/Sonarr automatic search, RSS and native completed imports are enabled.
  `/library` is a real Storage Box SSHFS library, with completed scratch mounted
  at `/data/complete`. Preserve mount-dependent systemd startup and mode-0000
  unmounted directory protection. Never enable the retired publisher timer.
- Five legacy movies have server-side hard links into native movie directories;
  original catalog objects/manifests remain intact. Do not edit shared file bytes
  in place. Native upgrades replace files normally.
- The Storage Box is canonical; the NAS reader credential is server-enforced
  read-only. NAS copies remain selective. Prefer native Arr/Plex features for
  import and scanning; OliveTin is only the transitional copy/removal interface.
- The deployed NAS cache is `/share/FromDrobo/Movies`; application state remains
  `/share/Container/usenet`. Private inventory must retain `qnap_data_root:
  /share/FromDrobo` and `qnap_catalog_cache_dir: /share/FromDrobo/Movies` after an
  older recovery snapshot is restored. Do not silently redeploy the old cache path.
- Prefer same-volume renames, verify device/inode and destination absence, and
  preserve rollback settings. Do not recursively copy, hash or change permissions
  on the existing collection merely to reorganize paths. Manifest-managed file
  names must stay consistent with their verification records.
- The original SOPS-bound snapshot/inventory is immutable and its clean-clone
  secrets/state milestone passed. Do not regenerate keys or repeat purchases/setup.
  Whole-machine replacement drills remain separate. Scheduled backups allow an
  idle or fully paused SAB queue but reject post-processing. Never delete/resume
  jobs just to satisfy backup checks. NAS-loss protection is explicitly deferred.

- Checkout-local preservation and independent restore passed at the checkpoint
  recorded in the recovery ledger. Follow
  [checkout recovery](docs/checkout-recovery.md) and recheck current files, Git
  history/settings and published source before declaring a later checkout safe.
  Preserve the untracked `msg`. Do not delete the checkout as part of a handoff
  update or imply NAS-loss protection. Original bound evidence stays immutable.

## Plex privacy and playback

- Plex runs on the QNAP. `loljk` is the existing private library; preserve its
  files, library ID and root. Do not browse or emit its thumbnails/content while
  inspecting settings. General libraries must never include the share root.
- Managed profile `Movies & TV` is granted exactly `Movies (NAS)`, `TV Shows (NAS)`,
  `Movies (Remote)` and `TV Shows (Remote)` (IDs 2/3/4/5); private `loljk` is ID 1.
  Preserve its exclusion from home/global search and verify actual profile grants,
  not only presentation settings. Owner PIN/client startup
  configuration requires private user/device setup; do not invent a PIN.
- Plex watches local changes, performs partial scans and scans hourly; automatic
  trash emptying is disabled. Do not empty trash to resolve an unavailable mount.
- Native TV sorting, the read-only remote mount and native selective-copy actions
  are deployed. Actual Apple TV/Roku playback remains deferred. Do not claim file indexing proves playback
  or that a configured profile proves safe startup on every client.

## Current operations and closure

- Cloud SAB's **NZBGeek Cart** feed is enabled with 15-minute polling. Preserve
  this user-authorized cart-only workflow and its Default category; see
  [phone cart downloads](docs/nzbgeek-cart.md). One pre-existing item was held
  during setup; no acquisition was initiated then. On September 14 the user
  selected the two current cart entries: media-004 was individually released and
  completed; media-006 was queued by normal polling and paused at 0% to preserve
  the scratch reserve. Keep media-006 paused until a deliberate capacity/release
  decision. media-004's deliberate native import, independent full SHA-256, Plex
  discovery and exact new-job scratch reclamation passed. It is remote-only and
  unmonitored in Radarr. Preserve its SAB history; do not reacquire it or count
  this manual path as automatic Arr-owned cleanup. Follow the current plan and the
  [acquisition receipt](recovery/drills/cart-acquisition-20260914.json). Existing settings/smoke helpers
  intentionally refuse enabled RSS feeds: do not disable the feed to pass them.

- New cart completions use the [automatic importer](docs/cart-import.md), whose
  activation baseline excludes all pre-existing queued/history jobs and feed
  entries. Preserve `state/catalog/cart-import/armed.json` and its journals. The
  worker uses native copy import without a download ID, independent full SHA-256
  and exact source cleanup; historical scratch, failed jobs and paused media-006
  remain excluded. Use `just usenet-cart-import-status` and cloud health. Stop only
  its timer before code refresh and reconcile in-flight commands; never replay a
  journaled import or enable the retired publisher. Actual fresh automatic
  completion and TV/Plex acceptance still need a future selected item.

- The Downloads status panel is deployed for native and legacy copies.
  `just configure-download-status` inside `usenet-infra` installs its telemetry
  and presentation scripts, holds the shared cache lock through a dashboard-only
  restart, and refuses active transfers. It does not install an absent native
  backend or migrate Plex roots. Keep old-cache provenance-object compatibility
  in `item_source`; otherwise dashboard startup can fail before the first refresh.
  Graph history starts with transfers launched after this update. Read
  [download status](docs/download-status.md) for reproducible coverage and limits:
  the native media-002 copy passed SHA-256 publication, safe repeat, automatic Plex
  indexing, graph/reconnect and completed-state acceptance. Deployment is not
  transactional and has no automatic rollback, and the maintenance lease expires
  after 600 seconds. Do not infer native or Plex acceptance from telemetry tests.
  Implementation and shared-agent edits are complete; the plan defines source
  review and remaining operational acceptance.

- Start with read-only `just usenet-discovery-health`, `just usenet-cloud-health`
  and `just usenet-qnap-health` from the repository root. Do not replay setup,
  account creation or deploy recipes merely to inspect the system. Restore missing
  private inputs through the documented vault/snapshot chain; temporary helpers,
  browser handles and SSH sockets from old sessions are not prerequisites.
- Native selective-copy source and the updated NAS backup helper are deployed;
  a fresh encrypted archive independently verified the published ownership receipt.
  Read the current acceptance state at the top of `plan.md`. Plex library ID 3
  was narrowed to `TV Shows/library` after confirming the old TV root was empty.
  Private inventory and the live runtime enable `qnap_native_tv_copy_enabled`;
  preserve that override after recovery. TV staging is `TV Shows/.staging` within the same bind;
  movie staging remains outside `Movies/video`. Preserve collision/verification
  checks and the shared cache lock; do not copy the whole collection or touch
  Arr scratch. Do not repeat setup or an already completed selected transfer.
- Record a fresh user-selected movie/TV completion through native import, cleanup
  and Plex discovery. Existing-file adoption is not proof of a fresh completion.
- The September 13 [queue reconciliation](recovery/drills/queue-reconciliation-20260913.json)
  classified all nine SAB warnings as historical and matched the four scratch
  files to two archived completed jobs (the fixture and an earlier media download).
  Preserve both groups and retained history; ownership alone does not establish
  canonical integrity or deletion readiness. The five adopted Radarr movies
  still report `importPending` against absent old completed paths. Use normal
  Arr queue views; unknown shared-client records do not prove app ownership.
- The September 14 [disposition investigation](recovery/drills/queue-disposition-20260914.json)
  matched those five old jobs to exact legacy publication/cleanup receipts and
  current canonical metadata. Deliberately retain their visible tracking and
  both scratch groups. Archived media has no established canonical manifest
  match; fixture metadata alone does not prove current integrity. Native Radarr
  ignore persists and no supported narrow undo was established; do not silently
  use it to make the queue look healthy. Investigation is complete; any later
  tracking correction or destructive cleanup remains a separate decision.
- The September 14 [external probe](recovery/drills/nas-exposure-20260914.json)
  passed dated direct TCP/1337 acceptance with current-WAN correlation, a
  successful same-WAN NAS TCP control, no dashboard UPnP mapping and no global
  NAS IPv6. This does not certify alternate static forwarding or proxy paths
  absent. Repeat after relevant networking changes.
- Apple TV/Roku playback, seeking and cold-start privacy are explicitly deferred
  by the user. Resume those checks when device interaction is available.
- Only if a merge is requested, follow the [merge gates](../plan.md#closure-and-merge-criteria): review the full
  branch, validate the reviewed source, acknowledge the two existing historical
  secret findings, and retain the operational deferrals. Delete Usenet refs only
  after the reviewed head is merged and local work is protected. Other feature
  branches with unique commits, dirty worktrees and stashes are separate work.
  NAS-loss protection, broader replacement and optional portals/providers remain
  separate. Update this guide, the plan and affected runbooks together.
- The user directed **no PRs** on September 13. PR #117 was closed without merging.
  Do not reopen it or create a replacement; preserve the branch and local work.
  The [cold session start](../plan.md#cold-session-start) is the next-session entry
  point. The September 13 handoff and September 14 audit documents and receipts
  are committed locally. Unrelated lighting edits and `msg` remain uncommitted.
  No push or merge was requested for session closure.
