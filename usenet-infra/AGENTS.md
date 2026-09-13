# Usenet, NAS and Plex agent guide

Read the [current handoff](../plan.md), then [native media](docs/native-media.md),
[NAS/Plex layout](docs/nas-plex-layout.md) and [scheduled backups](docs/scheduled-backups.md).
Use [operations](docs/operations.md) for additional commands. Chronological
notes describe earlier policies; they do not override the current handoff.

## Access and validation

- Use root `just usenet-*` recipes or `just --justfile usenet-infra/Justfile
  --working-directory usenet-infra ...`. The private `.env` and ignored Ansible
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

- Checkout-local preservation and independent restore passed: snapshot
  `20260911T235253Z-9d6bbacf00ac982a` contains 1,319 local files; companion
  `20260912T000901Z-36009465898f2df0` preserves 78 Git refs/reflog history and five
  stashes. The readiness check passed at published `cf13edb`. Follow
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
- Native TV sorting and the read-only remote mount are deployed. Actual Apple TV/Roku
  playback and a convenient NAS copy action for new native-library titles remain. Do not claim file indexing proves playback
  or that a configured profile proves safe startup on every client.

## Resuming unfinished work

- The Downloads status panel is deployed on the existing legacy dashboard.
  `just configure-download-status` inside `usenet-infra` installs its telemetry
  and presentation scripts, holds the shared cache lock through a dashboard-only
  restart, and refuses active transfers. It does not install an absent native
  backend or migrate Plex roots. Keep old-cache provenance-object compatibility
  in `item_source`; otherwise dashboard startup can fail before the first refresh.
  Graph history starts with transfers launched after this update. Read
  [download status](docs/download-status.md) for reproducible coverage and limits:
  the live graph on a new transfer is still unaccepted, deployment is not
  transactional and has no automatic rollback, and the maintenance lease expires
  after 600 seconds. Do not infer native or Plex acceptance from telemetry tests.
  See `plan.md` for current task ownership and release state.

- Start with read-only `just usenet-discovery-health`, `just usenet-cloud-health`
  and `just usenet-qnap-health` from the repository root. Do not replay setup,
  account creation or deploy recipes merely to inspect the system. Restore missing
  private inputs through the documented vault/snapshot chain; temporary helpers,
  browser handles and SSH sockets from old sessions are not prerequisites.
- Native selective-copy source is implemented but not yet deployed/live-accepted.
  Read the current increment at the top of `plan.md`. TV copies default disabled;
  before enabling `qnap_native_tv_copy_enabled`, narrow
  Plex library ID 3 to `TV Shows/library` after confirming no existing series
  outside that child. TV staging is `TV Shows/.staging` within the same bind;
  movie staging remains outside `Movies/video`. Preserve collision/verification
  checks and the shared cache lock; do not copy the whole collection or touch
  Arr scratch. Automatic review rejected the prior combined private cloud
  metadata collection; do not replay it without resolving that approval boundary.
- Record a fresh user-selected movie/TV completion through native import, cleanup
  and Plex discovery. Existing-file adoption is not proof of a fresh completion.
- Then verify real Apple TV/Roku playback, seeking and cold-start privacy with the
  restricted profile; request private user/device interaction only as needed.
- Follow the ordered acceptance criteria in `../plan.md`. NAS-loss protection,
  broader machine replacement, optional portals/providers and default-branch merge
  remain separate. Update this guide, the plan and affected runbooks together.
