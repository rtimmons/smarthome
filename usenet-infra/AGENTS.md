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

- Radarr/Sonarr explicit search and native completed imports are enabled; RSS
  polling stays off under the September 20 native policy.
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
  are deployed. The user confirmed Apple TV and Roku playback and restricted privacy on September 22.
  Record this as user verification, not an agent-run codec/subtitle matrix or proof for every future client.

## Current operations and closure

- **September 22 follow-up checkpoint verified.** User-authorized disposition removed the
  three old zero-progress requests and resolved 14 failure records for seven
  historical held journals. All 44 journals and importer/capacity hold evidence
  remain unchanged; the completed disposition receipt is bound to the original
  native baseline. Cloud health now passes. Do not resurrect discarded requests.
  Selected TV copying, SHA-256 verification, safe repeat and exact-file Plex NAS
  indexing pass. User confirms playback/privacy on both Apple TV and Roku.
  Filex encrypted daily capture and NAS SFTP settings coverage are deployed;
  see [Filex recovery](docs/filex-recovery.md). A real Seerr request completed in
  2160p using an eligible manual alternate after an unrepairable release; import,
  source cleanup, general Plex indexing and Seerr availability passed. Two
  concurrent 50 GiB expansions passed within the existing reserve limits.
  `cloud-20260922T215403Z.tar.age` independently restores 752 files, five databases,
  all 44 journals and both nested Filex bundles; off-host readback passes.
  Final service health checks pass. Follow the current plan for Mac CA trust,
  normal-browser login, NAS backup scope and the proposed USD 1 replacement drill.
  No temporary replacement resources have been created.
  This entry supersedes older preserve-paused-request and unresolved-failure
  instructions below; those dated records remain historical evidence.


- **September 22: Seerr deployed.** The private portal at
  `http://10.77.0.1:15055/` uses the existing Plex owner login and native Arr
  requests. Only Plex libraries 2/3/4/5 are enabled. Preserve local-login and
  new-user-registration restrictions, disabled watchlist acquisition, Ultra-HD
  (2160p preferred, 1080p fallback) defaults and existing RSS-off policy. Both direct carts remain disabled.
  Use `just usenet-seerr-status`; see [Seerr operations](docs/seerr.md).
  The isolated encrypted restore includes Seerr settings/database (732 files,
  five databases, 44 old journals). Browser login page and discovery/native
  connections pass; no actual media request was submitted for this deployment.

- **September 22: approved application maintenance completed.** Radarr
  `6.4.4.10685-ls318`, Sonarr `4.0.20.3014-ls325` and Prowlarr
  `2.6.5.5623-ls161` now match prepared source. Application health has zero
  findings; discovery/native policy and all historical preservation checks pass.
  Cloud health remains nonzero only for 14 retained catalog records. SAB was
  not restarted. Stopped rollback configurations and old images remain private
  under `/srv/usenet/backups/app-maintenance-20260921`; that date is the prepared
  runner's directory, not the deployment date. Never replay its launcher.
  The verification-only Prowlarr command refusal was reconciled without repeating
  deployment. `cloud-20260922T191826Z.tar.age` independently restores 726 files,
  four databases and all 44 journals, with 59 live hash matches. See the
  [receipt](recovery/drills/app-maintenance-20260922.json) and
  [rollback runbook](docs/app-maintenance-20260921.md). TV selection and other
  separate follow-ups remain in the plan; this approval did not select TV media.

- **September 21: accepted-state restore passed; updates prepared only.**
  `cloud-20260921T155229Z.tar.age` independently restored 726 files and four
  databases. All 59 selected live hashes, including 44 journals, match; mount
  definitions reconstruct from source plus the restored volume identity.
  See the [receipt](recovery/drills/native-state-restore-20260921.json).
  Source pins/version guards contain reviewed updates, but live applications
  still run the prior versions: automatic approval review requires explicit
  user approval for the three-container maintenance. Do not mistake prepared
  source for deployed state or replay broad setup. Follow the
  [maintenance runbook](docs/app-maintenance-20260921.md). TV-copy selection is
  also pending. Preserve all holds, local private overrides and original snapshots.

- **September 20, 22:05 UTC: health audit complete.** Native ownership and
  historical preservation pass; NAS and Filex health pass. Fourteen catalog
  records map to seven old identity-held journals, including five cleanup
  failures with later completed disposition receipts. All three application
  health responses contain only update notices. Findings remain visible and
  unwaived; do not clear holds or run retired workers to improve health output.
  Cloud/NAS backup status is fresh, but accepted-state independent restore is
  still unverified. Follow the plan's
  [remaining-work table](../plan.md#remaining-work-and-explicit-deferrals);
  old hybrid next-admission acceptance is superseded. See the
  [audit receipt](recovery/drills/health-audit-20260920.json).

- **September 20: storage expansion approved and deployed.** The existing
  Storage Box is BX21; a separate 300 GB volume now backs the incomplete spool.
  Keep private Terraform inputs `storage_box_type = "bx21"` and
  `repair_spool_enabled = true` after restoring older snapshots. Never reapply
  old saved purchase plans, reformat this volume, or replay the old hybrid
  migration. Read the [repair-volume runbook](docs/repair-spool.md) for pinned
  device/mount checks, retained original data and phase-specific recovery.
  The observed capacity envelope passes. The user accepted native Arr cleanup
  and random fresh movie/episode selection; native ownership is accepted and active.
  Fresh imports/cleanup, Plex discovery, an 80 GiB repair and scoped restart passed.
  Direct carts and all three legacy workers are disabled. Do not restart them
  or run their old setup recipes. Native polling remains off to prevent implicit
  backfill of seven pre-existing monitored missing movies; explicit new Arr
  searches remain available. Use
  `just usenet-native-cutover-preflight` for private read-only snapshots and
  allowlisted output. Follow the [cutover runbook](docs/native-cutover.md) and use
  `just usenet-configure-native-ownership` for current policy inspection/refresh.
  Preserve all three held requests and journals. This active native policy
  supersedes every older cart/admission/timer instruction below.

- **September 20: Filex is deployed with verified transfers.** See the current
  [plan](../plan.md), [portal runbook](docs/filex.md) and sanitized acceptance
  receipt. Use `just usenet-filex-status` (service plus private HTTPS health),
  `just usenet-filex-disable`, `just usenet-filex-build` and the isolated deployment
  recipe. Download and NAS staging are dedicated writable roots; Storage Box
  canonical roots and isolated portal scratch are kernel-enforced read-only.
  Use the operator login, never the loopback-only administrator. The reviewed
  backend hashes destinations, records receipts and quarantines moved/deleted
  sources; permanent purge is disabled. Interrupted transfers require explicit
  retry. Do not replace this image with unmodified upstream or expose acquisition
  metadata. Portal state is outside existing backup coverage.
- The user approved recovery of the retained admitted job. Missing metadata was
  restored, its download completed, and remote PAR2 plus SHA-256 verification
  passed after local repair exhausted space. Reversible block repair and native
  retry preserve the reservation, original recovery evidence, held records and
  all other pauses. The retained admission has `preserve_failed_payload: true`,
  so another failure pauses for review without reclamation. Keep controller state
  owned by `usenet` with mode 0600 after any root-run recovery. Follow the current
  plan/private recovery receipts; do not
  repeat a retry whose result is uncertain or let failed-payload reclamation
  delete the preserved repair. The deployed local admission estimate now reserves
  a full repair output. The NAS dashboard refresh fix is deployed and NAS health
  passes. Native SAB completion, Radarr hardlink import, independent canonical
  SHA-256 and exact media-source cleanup passed; six non-media files remain
  retained. Server-side device/inode and link counts prove the actual hardlink.
  The adapter handles only Radarr's duplicate-copy space rejection after a live
  staging hardlink probe and reserve check; do not disable global free-space
  checks or expand the importer's read-only canonical access. All three remaining
  requests have existing identity holds, so the next automatic admission needs
  a new eligible user cart selection. Do not release them merely for acceptance.
  See the sanitized September 20 recovery receipt.

- **September 18, 16:46 UTC: queue repair is incomplete.** Six requests are
  individually paused, global SAB is resumed, no job is admitted/postprocessing,
  and both acquisition/importer timers are **stopped**. There are 34 completed
  journals and five disposal errors. The failed deployment preserved every
  affected source file; applications and existing mounts remain active. Root
  available space is 80.25 GB and remote available space is 214.15 GB. The latest
  [plan handoff](../plan.md) supersedes all older progress reports below.
- `b52537f` added local compressed spooling, remote unpacking, native hardlinks
  through one common Arr mount and guarded rejected-input disposal. Its helpers
  are installed, but deployment failed during disposal before storage migration.
  `c342318` corrects retained admission-proof validation, timer sequencing and
  ordinary-held exit handling; it is committed but **not deployed**. The live
  marker is still version 1 and `hybrid-scratch-setup.json` is absent. No second
  deployment process is running. Follow the plan's fresh preflight, then
  `configure-hybrid-scratch`; do not merely restart timers or blindly replay a
  partial migration. Read [bounded acquisition scratch](docs/hybrid-scratch.md).
- The failure arose from requiring live RSS eligibility despite saved original
  admission proof. The correction checks that proof against the exact retained
  history URL hash and job identity. User-authorized rejected-input disposal
  preserves hashes/history and writes durable per-file intent and redownload
  receipts; it is not a successful import or permission to repeatedly download
  unresolved identities. Shared sources and legacy/canonical media remain
  protected. Expected reclamation has not occurred. No resize/purchase occurred.
- Validation at `c342318` ran 630 cases: 621 passed and nine optional skips;
  compilation, shell/YAML and deployment syntax passed. The full recipe fails
  only on the two documented historical RSA keys. Live hybrid migration,
  application-user hardlink probes, automatic import/cleanup/next admission and
  independent restore remain outstanding. Keep both 30 GiB floors, mount
  protection, activation and exact cleanup journals. Never reset a reservation
  merely because postprocessing temporarily lacks a SQLite history row.
- Backup scheduling remains active. Latest captured cloud archive is
  `cloud-20260918T160347Z.tar.age`; it predates this failed deployment and has not
  been independently restored here. Latest independently restored archive is
  still `cloud-20260917T143828Z.tar.age` (671 files, four databases, 28 journals,
  22 completed). Capture and restore the successful migration before declaring
  current recovery coverage. Private evidence/helper locations and ordered
  continuation are recorded in the plan. TV, later Plex indexing, Arr-owned
  cleanup and deferred device playback remain separate acceptance work.

- Earlier September 17 deployed source was `edf223e` plus `5790fcf`: application-available
  inode checks, native mount/root availability, preserved manual pauses and exact
  paused RSS intake. The capacity service must run during mount outages to pause
  SAB; do not restore mount prerequisites that prevent the guard from running.
  Seven requests ran after the intake correction; five imported and cleaned,
  two hit identity holds. User-approved exact disposal of those two held payloads
  reclaimed 21,940,561,867 bytes and preserved paused replacement requests/history.
  Replacements still need identity resolution. Original four held payloads remain.
- At the earlier 14:38 UTC checkpoint the queue was capacity-blocked: 18 paused entries, no active job,
  80,315,387,904 available bytes, both automation timers active and global SAB
  resumed. CX53 resizing was not applied; source/private inputs stayed CX43.
  Remote staging temporarily cleared that blockage; the September 18 checkpoint
  above records the subsequent stall and interrupted repair.
- `cloud-20260917T143828Z.tar.age` independently restored 671 files, four databases,
  28 importer journals (22 completed) and both exact disposition journals. Helpers,
  activation and controller state matched source/live records at that checkpoint.
  Older handoff counts below are historical. That suite ran 598 cases, with 589
  passes and nine optional skips; syntax/current scan passed and history reports
  the two known RSA keys. Synthetic extended capacity tests are now covered,
  while actual remaining backlog, TV, Arr-owned cleanup and playback are not.
  See the [progress receipt](recovery/drills/cart-queue-progress-20260917.json).

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

- Cloud SAB's **NZBFinder Cart** feed is also enabled with the same 15-minute
  polling and Default category. Its initial scan deliberately held existing cart
  entries; future user selections auto-download. Preserve its protected
  Prowlarr database at mode 0640 or stricter and the container's `UMASK=027`.
  Use `just usenet-nzbfinder-cart inspect` to validate it without exposing its
  saved API/RSS key.

- New cart completions use the [automatic importer](docs/cart-import.md), whose
  activation baseline excludes all pre-existing queued/history jobs and feed
  entries. Preserve `state/catalog/cart-import/armed.json` and its journals. The
  worker uses native copy import without a download ID, independent full SHA-256
  and exact source cleanup; historical scratch, failed jobs and paused media-006
  remain excluded. Use `just usenet-cart-import-status` and cloud health. Stop only
  its timer before code refresh and reconcile in-flight commands; never replay a
  journaled import or enable the retired publisher. Actual fresh automatic
  completion and TV/Plex acceptance still need a future selected item.

- `usenet-capacity-admission.timer` owns paused acquisition for both cart feeds
  and the Default/Prowlarr categories. Keep feed/category priority at `-2`, both
  SAB free-space floors at `30G`, and the global queue resumed; the controller
  releases exactly one fitting owned job. Its durable state is under
  `state/catalog/capacity-admission`. Do not manually resume owned jobs, erase
  holds, lower the reserve or delete `__ADMIN__` from a failed job. Per-item
  importer holds do not stop unrelated backlog work; reserve, concurrency and
  integrity failures deliberately fail closed. Deployment/restart preserves an
  admitted history item and reconciles every nonterminal cart journal before
  admitting more work; do not reset that state to bypass a reconciliation wait.

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
- The static private Usenet field guide is deployed at
  `http://192.168.1.66:8090/`. Edit `wiki/` and use only
  `just usenet-wiki-deploy` from the repository root; the dedicated playbook
  validates an immutable candidate and restores the prior wiki release if its
  smoke check fails. It must not gain live APIs, credentials, media listings,
  Docker-socket access or public exposure. See [the wiki runbook](docs/wiki.md).
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
  point. The privacy rewrite was published and verified on local/remote `usenet`
  at `204df8c`; use rewritten history and never merge the earlier branch back in.
  The current plan and three aligned handoff documents follow that checkpoint.
  The user authorized the repository-local Codex SSH key to sign this handoff;
  command-scoped signing leaves the user's defaults unchanged. Check publication
  separately and preserve the ignored private key.
  Unrelated lighting edits, `msg` and packages stay
  preserved. No merge or branch/checkout deletion is authorized.
- At the September 14 02:57–02:58 UTC handoff check, cloud/discovery/NAS health
  passed with historical SAB warnings; the importer was idle with no accepted
  automatic jobs, SAB had one paused item and ten history records, and no TV
  content was available. The latest cloud archive predates importer activation.
  Finish the [post-activation archive checkpoint](docs/scheduled-backups.md#cart-importer-checkpoint)
  before declaring recovery coverage for the extension. Then follow the plan's
  ordered media acceptance rows using actual new user selections; do not infer
  cart-worker acceptance from its idle activation or from manual import evidence.
