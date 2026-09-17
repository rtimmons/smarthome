# Usenet status and closure plan

## Current handoff — September 17, 2026, 14:38 UTC

Capacity guards and corrected paused RSS intake are committed (`edf223e`,
`5790fcf`) and deployed. SAB materializes paused feed arrivals with priority
`Normal`; exact saved RSS provenance now admits those requests without adopting
manual pauses. Seven queued requests subsequently ran: five completed native
imports and independent verification/cleanup, reclaiming **61,260,245,624 bytes**;
two reached catalog identity holds. Serialization stayed at one job through cleanup.

At the user's direction, the exact four files belonging to those two new holds
were rehashed and removed, reclaiming **21,940,561,867 bytes**. Their original SAB
history remains, with one paused replacement request each. Replacements remain
held for identity resolution to avoid repeatedly downloading the same rejected
release. Separate durable disposition journals record that these were discarded
recoverable payloads, not successful imports. The four older identity-held
payloads and historical scratch remain unchanged.

**The queue is capacity-blocked again, so the repair is not closed.** The latest
snapshot has 18 individually paused entries, no active/postprocessing job, a
resumed global queue and **80,315,387,904 available bytes**. Both automation timers
are active. Admission still reserves remaining archive bytes plus 1.25 times the
release size, a 5 GiB margin and 30 GiB free. A largest roughly 80 GB request does
not imply an 80 GB unpacking peak. A CX43→CX53 plan was inspected but **not
applied**; its source/private input changes were reverted. No storage was bought.
The existing Storage Box has about 743 GB free, but remote unpack staging is not
implemented. Its SSHFS mount rejected exclusive rename with EINVAL during a
five-byte disposable probe; preserve verified cleanup semantics if developing
that option. Do not assume this probe deployed a storage change.

A fresh guarded archive, `cloud-20260917T143828Z.tar.age`, independently decrypted
and restored: **671 files, four SQLite databases, 28 importer journals, 22 completed
journals and both disposition journals**. Current helpers, activation marker,
controller state and completed journals matched source/live evidence. Of the 22
completed records, four are existing-target reconciliations and 18 are native
imports. Original recovery snapshots remain immutable.

The full infrastructure suite ran 598 cases: 589 passed and nine optional skips.
Compilation, shell/YAML and deployment syntax passed; full-history scanning still
reports only the two documented historical RSA keys. Current-source scanning
passed. Synthetic inode, mount/application outage, pause/restart, burst and peak
allocation tests are complete; this is not a hard disk quota or arbitrary archive
expansion guarantee. Read-only Plex matching found the earlier 17 completed
records; later selected-directory scans do not yet establish indexing of all five
new imports. TV, Arr-owned cleanup and user-deferred playback remain distinct.

See the [progress receipt](usenet-infra/recovery/drills/cart-queue-progress-20260917.json).
Next work is to make the remaining backlog fit while retaining automatic cleanup,
resolve identity holds without guessing, and verify later Plex indexing. Preserve
the active timers, 30 GiB floors, canonical files and exact recovery journals.
No PR, push, merge, VM resize or server restart was performed. Unrelated lighting
edits, `msg` and packages remain untouched.

## Previous handoff — September 16, 2026

The NAS Usenet wiki is implemented and deployed at
[http://192.168.1.66:8090/](http://192.168.1.66:8090/). The separate
[download-capacity repair](#download-capacity-repair--implemented-extended-validation-remains)
was executed on September 16 after explicit authorization to remove recoverable
payloads. The older zero-space observations below are retained as incident history.

**Capacity recovery and automation, September 16 EDT:** 199 queue entries were
reconciled to 17 unique requests without deleting payload data. An unjournaled
86,272,135,168-byte failed partial was removed; every represented selection
remained queued for reacquisition. A separate 46,369,153,024-byte failed payload
was removed and its exact request was restored as one paused item from its unique
native Prowlarr grab record. The queue has no exact-filename duplicates. Both cart
feeds remain enabled, and both SAB free-space floors are restored to `30G`.

A host-owned capacity controller now runs every 20 seconds. Feed/category priority
registers requests as individually paused, while the controller admits exactly
one fitting job using remaining download bytes, a 1.25x full-release expansion
allowance, a 5 GiB margin and a 30 GiB application-visible reserve. It waits for
native import, independent canonical verification and exact scratch cleanup before
admitting another job. Exact zero-progress duplicates are collapsed without file
deletion. Import holds and exhausted failed retries are isolated per item instead
of freezing unrelated requests. Controller-owned failures reclaim only the exact
failed payload while preserving SAB's admin/NZB state, then use bounded native
history retry. State is durable under `state/catalog/capacity-admission` and cloud
health distinguishes normal capacity waits from fail-closed controller faults.
Configuration refreshes preserve an admitted history item; each controller run
also reconciles every nonterminal cart journal before another acquisition, so a
large backlog cannot strand completed payloads across restart/deployment windows.

Live validation reduced the owned queue from 17 to 8 while preserving one-active-job
serialization, enabled feeds, zero duplicates and the 30 GiB reserve. Restart
reconstruction found completed cart journals orphaned by earlier deployment
windows, held new acquisition, and automatically resumed their import,
verification and cleanup. That pass reached 16 reconciled completions with zero errors and raised
application-visible free space from roughly 74.3 GB to more than 102.6 GB. At the
latest check, exactly one of eight owned requests was admitted, seven were paused,
and one controller-level import hold was isolated; the broader importer journal
retains several private holds for review. Continue observing the automated drain;
do not manually resume jobs.

**Wiki deployment, September 16 EDT / September 17 UTC:** the static field guide
is served by pinned Caddy 2.11.4 in an isolated `usenet-wiki` Compose project.
Preflight found port 8090 free; live validation confirmed the exact
`192.168.1.66:8090` binding, non-root/read-only container, immutable release
mount, healthy status and expected page content. Browser review confirmed the
live page, anchors, diagram and keyboard-readable structure; automated coverage
checks the mobile layout, shortcuts and accessibility contract. A controlled
bad-candidate drill failed its page smoke check, restored the prior release and
left the other NAS containers running; the following deployment was idempotent
and did not recreate the wiki. LAN delivery passed. A connected off-LAN VPN client
was not available, so VPN-path acceptance remains a documented network limitation,
not a wiki deployment failure. [Runbook](usenet-infra/docs/wiki.md),
[receipt](usenet-infra/recovery/drills/wiki-deployment-20260917.json).

**Latest read-only observations, September 16, approximately 23:27 UTC:** cloud
scratch/root had zero available bytes. SAB logged `No space left on device`
while writing incoming NZBs, queue state and database records; seven distinct
cart selections had accumulated 147 zero-progress `Grabbing` entries. Both cart
feeds remained enabled at 15-minute intervals. Cloud health also reported
Prowlarr HTTP 500 and a stale importer heartbeat; the importer service was
repeatedly failing. Recheck these applications after space recovery rather than
assuming every error has the same cause. Storage Box and NAS health remained
reachable, with approximately 925 GB free on the Storage Box.

The completion automation had successfully imported three new cart movies and
recorded **64,588,527,229 bytes reclaimed**; all three were indexed in Plex
Movies (Remote). One journal retained a small sidecar, not its movie payload.
This establishes observed movie import/cleanup/indexing progress; preserve and
review the journals for a durable acceptance receipt and backup checkpoint.
TV and playback acceptance remain open. The disk was instead occupied by roughly
86.3 GB of incomplete/failed media-006 data, 46.4 GB from the retained failed job,
and 17.3 GB of older completed scratch. media-006's historical paused-at-zero
state is no longer current; reconcile its exact live state before intervention.
SAB's live download threshold was `16G`, below the repository's intended `30G`;
the completed-space threshold was `30G`, direct unpack was disabled and downloads
were not paused during post-processing. Configuration drift and peak unpack
requirements need correction; restoring a threshold alone is insufficient.
Do not delete retained scratch, release jobs or purchase capacity to make health
checks pass. Repairs remain separate from wiki deployment.

NAS SSH inspection confirmed x86_64 and no TCP listener on port 8090 at the time
of the check. Recheck before deployment. This was a port/architecture inspection,
not a fresh NAS application-health or remote-client VPN acceptance check.

## Historical handoff — September 14, 2026 (UTC)

The requested automatic Storage Box import and verified cloud cleanup is deployed.
The recovery checkpoint and remaining real-media acceptance below were still
outstanding at this checkpoint; the September 16 wiki request adds new work.
A missing user selection or deferred device test is a prerequisite to record,
not permission to manufacture content or mark that test passed.

**Source checkpoint:** `usenet` and GitHub `origin/usenet` were verified at
`204df8c` after the privacy rewrite. The deployed cart implementation is
`de1f377`; earlier acceptance receipts are in `f50a916`. This handoff update follows
that published checkpoint. At the user's direction, the handoff commit uses the
repository-local Codex SSH key with command-scoped signing settings; the user's
default signing configuration is unchanged. Inspect local `HEAD` and publication
state at the next start. This handoff is an ordinary follow-up commit, not a reason
to repeat the earlier privacy force-push.
The rewrite replaced identifying media names, release filenames, title-derived
keys and external catalog identities in 13 affected commits. Historical scans
passed and only the Usenet branch was updated. Do not merge or restore the old
Usenet history into the rewritten branch. Other branches, stashes, lighting edits,
`msg` and untracked `new-hass-configs/packages/` were preserved. Old private backups,
reflogs or cached GitHub pages can retain prior versions; they were not purged.

**User constraints:** no PRs and no default-branch merge requested. PR #117 is
closed and must stay closed. Commits must contain only neutral media aliases;
exact titles, filenames, catalog identities and alias mappings stay in private
runtime state or ignored evidence. Public receipt paths are aliases, not commands.
Preserve original bound recovery snapshots and the private Plex library. Do not
purchase storage, remove protected downloads or resume the paused selection to
make acceptance checks pass.

**Historical runtime check, September 14, 02:57–02:58 UTC:** cloud, discovery and NAS health
passed, with the same nine historical SAB warnings. The cart worker was `idle`
with zero completed, held or failed journals. SAB had one individually paused job,
ten history records, no post-processing and global pause false. The native library
had six movies (one NAS-local, five remote-only), no TV, and no active/failed NAS
pulls. These are observations to refresh, not guarantees about a later session.
Cloud backup status was healthy; its last success was September 13 at 22:05:43 UTC,
which predates cart-worker activation and does not establish its archive coverage.

**Deployed automation:** NZBGeek Cart polls every 15 minutes; the cart worker checks
new completions every 30 seconds. It performs guarded native Radarr/Sonarr copy
imports, independent full canonical SHA-256, then exact verified cloud-payload
cleanup. It never enrolls the 11 pre-existing queued/history jobs or two known
feed entries captured at activation (September 14, 01:38:39 UTC). Preserve that
baseline, journal phases and existing pauses. Arr-owned completed imports remain
separate; the retired publisher stays disabled. Plex uses its existing discovery
and hourly fallback. NAS copies remain explicitly selected.
[Worker runbook](usenet-infra/docs/cart-import.md),
[activation/preservation receipt](usenet-infra/recovery/drills/cart-import-activation-20260914.json).

**Historical capacity, recorded September 14:** inspection found about 86.4 GB free, 54.2 GB above the
30 GiB reserve. Approximately 46.4 GB is a retained failed download and 17.3 GB is
older completed scratch. The excluded paused selection advertises about 61.4 GB
before unpacking. Automatic cleanup prevents future completed-payload buildup;
it does not resolve that existing oversized job or authorize historical deletion.
These free-space figures are superseded by the September 16 zero-free-space
check; the older file-size breakdown needs fresh read-only verification.

**Validation:** the deployed extension passed 538 infrastructure cases (529 passed,
nine optional skips), compilation, shell/YAML and deployment syntax checks.
Current-source/index secret scanning passed. Full history scanning fails only on
the two documented historical RSA keys; do not report the full recipe as green.
Root tests and seven add-on container builds passed at the September 13 checkpoint.
The privacy rewrite and this handoff change documents/receipts only; application
code and deployed file hashes are unchanged. See the [validation ledger](usenet-infra/docs/validation.md)
for dated evidence and limits. New implementation edits require fresh appropriate tests.

## Cold session start

1. Read this plan, [Usenet agent guide](usenet-infra/AGENTS.md),
   [cart-worker runbook](usenet-infra/docs/cart-import.md),
   [native media](usenet-infra/docs/native-media.md), and
   [validation ledger](usenet-infra/docs/validation.md). Inspect `git status`,
   branch, local/remote head and uncommitted work. Stay on `usenet`; preserve
   unrelated lighting work, `msg`, packages, other branches and stashes.
2. Use the repository's existing private `.env`, inventory, dedicated identities
   and host pins. Missing private inputs are recovered through
   [secrets recovery](usenet-infra/docs/secrets-recovery.md) and
   [checkout recovery](usenet-infra/docs/checkout-recovery.md), not new accounts,
   keys or purchases. Do not depend on an earlier agent, browser tab, `/tmp` helper,
   private redaction map, or ignored progress log to discover current state.
3. Refresh read-only `just usenet-cloud-health`, `just usenet-discovery-health`,
   `just usenet-qnap-health` and `just usenet-cart-import-status` from the root.
   Follow the planned capacity recovery for the September 16 failures before
   new acquisition acceptance;
   record remediation separately from the wiki and preserve all existing pauses.
   Inspect `just native-status` privately: its output includes real media names.
   For structured native status, use the existing infra wrapper's
   `./scripts/qnap-command native-status --json`. Save media-bearing output only
   to an ignored private directory; record aggregate status/opaque references.
4. Inspect `/srv/usenet/state/catalog/cart-import/{armed.json,status.json,jobs/}`
   privately through `scripts/cloud-command`. Confirm the timer, canonical mount
   and discovery services; distinguish an active command from a held/retryable
   journal. Follow the worker's guarded retry procedure; never replay native
   import or reset activation. A file already deleted by verified cleanup must
   be reconciled from its journal and canonical evidence, not reacquired.
5. Verify backup freshness and the post-activation recovery row below. Then
   inspect for genuinely new user-selected jobs. Continue authorized independent
   checks while awaiting a needed selection. If none exists, ask once for a new
   desired movie/numbered TV episode or record that prerequisite; preserve the
   excluded paused job and existing cart history. Do not release all feed entries.
6. Record each completed acceptance as a dated sanitized receipt, update this
   plan and the relevant guide/ledger, and review the entire staged diff for media
   privacy before a scoped commit. Do not publish private logs or replacement maps.
   Complete all available work and leave only explicit user-dependent/deferred
   items, with no ad-hoc transfer, deployment or agent process left running.

Host-owned acquisition, import and backup schedules continue between sessions.
No recurring Codex automation is configured. This handoff does not authorize a
merge, PR, branch deletion or checkout removal. GitHub publication previously
used the existing `gh` login over a command-scoped HTTPS push route after the SSH
agent failed; saved Git settings were unchanged. If publication is requested,
verify the actual push URL and remote head first; a new handoff commit is an
ordinary fast-forward, not a reason to repeat the privacy force-push.

## Current system

| Use | Entry point / behavior |
| --- | --- |
| Choose movies and TV | [Radarr](http://10.77.0.1:19696/radarr/) / [Sonarr](http://10.77.0.1:19696/sonarr/). Native search/RSS and completed imports are enabled. |
| Phone discovery | NZBGeek **My Cart** and NZBFinder **Cart** feed [cloud SAB](http://10.77.0.1:18080/) every 15 minutes. Feeds stay enabled but register jobs individually paused; the capacity controller admits one fitting request at a time. Eligible Default-category jobs use the [automatic native import/verified cleanup worker](usenet-infra/docs/cart-import.md); they are not automatically Arr-owned. [Playbook](usenet-infra/docs/nzbgeek-cart.md). |
| Make a title local | [NAS dashboard](http://192.168.1.66:1337/). Choose the Native library action for canonical Movies/TV; transfer phase, rate, progress and history are visible. [Runbook](usenet-infra/docs/native-media.md). |
| Understand and operate the stack | [Usenet field guide](http://192.168.1.66:8090/) explains the ecosystem, shortcuts, daily workflows, storage boundaries and safe first-line diagnostics. It is static and has no live controls or credentials. [Runbook](usenet-infra/docs/wiki.md). |
| Watch | QNAP Plex, using **Movies & TV** and explicit NAS or Remote libraries. The profile has only IDs 2/3/4/5; private library ID 1 is denied. [Layout and client setup](usenet-infra/docs/nas-plex-layout.md). |
| Recover | [Secrets/state](usenet-infra/docs/secrets-recovery.md), [checkout recovery](usenet-infra/docs/checkout-recovery.md), [scheduled backups](usenet-infra/docs/scheduled-backups.md). These cover configuration/state, not whole-NAS loss. |
| Costs | [Dated cost ledger](usenet-infra/docs/costs.md). Infrastructure and NZBGeek total $24.09/month equivalent; Eweka actual terms and NZBFinder charge/currency remain unverified. No purchase is pending. |

Read [the agent guide](usenet-infra/AGENTS.md) before operations. Use the dedicated
identities and host pins in private inputs; never print credentials. Configuration
inspection is not a reason to deploy or restart services.

## Accepted scope

| Capability | Evidence |
| --- | --- |
| Automatic cart worker | September 17 [checkpoint review](usenet-infra/recovery/drills/cart-capacity-checkpoint-20260917.json) captured 13 native movie imports and four existing-target reconciliations with recorded SHA-256 evidence, current native ownership, retained SAB history and exact payload absence. All completed journals are verified in the current backup. Fresh Plex indexing and TV acceptance remain open. |
| Cloud acquisition and native library infrastructure | Provider/indexer checks, mount protection and five existing-file adoptions passed. Arr owns completed imports; the legacy publisher is disabled. [Native workflow](usenet-infra/docs/native-media.md). |
| Deliberate phone-cart movie import | User-selected media-004 completed download/unpack, native manual copy import, independent SHA-256 verification, scoped-scan Plex discovery and exact new-job scratch reclamation. SAB history and older scratch remain intact. [Import receipt](usenet-infra/recovery/drills/cart-native-import-20260914.json). Automatic Arr-owned cleanup remains unproved. |
| Selective NAS movie copy | media-002's 14,878,405,826 bytes passed server/local SHA-256, source-change checks and exclusive publication. Repeat preserved the directory identity and bytes without another download. Plex indexed it automatically. [Live receipt](usenet-infra/recovery/drills/native-copy-live-20260913.json). |
| Downloads UI and privacy | Authenticated action, graph/progress, browser reconnection and verification/completed phases passed. Profile grants, private home/search exclusion and disabled automatic trash emptying were verified. Same live receipt. |
| TV layout | Plex ID 3 scans `TV Shows/library`; staging is the sibling `.staging` within one container bind. The live copy gate is enabled. No real TV title has been copied yet. |
| Recovery | Clean-clone secrets/state restore, checkout files and Git/stash recovery, scheduled cloud/QNAP/Plex archive verification passed. [Recovery ledger](usenet-infra/docs/validation.md). A fresh deletion check is still required before any checkout removal. |
| Native receipt recovery | A fresh encrypted NAS archive independently verified all 56 entries, including the exact published native ownership receipt. [Backup receipt](usenet-infra/recovery/drills/native-receipt-backup-20260913.json). Media is excluded. |
| Security remediation | Compatible updates to five dependency lockfiles and removal of the tracked HA secret file are committed/deployed. Current-source secret scanning passes. Two exposed keys remain in pre-existing Git history; known consumers were retired/wiped. [Findings](usenet-infra/docs/security-findings.md). |

## Operating invariants

- Storage Box `catalog/library/{Movies,TV}` is canonical. Arr imports over the
  synchronous mount; preserve mount-before-Arr startup and mode-0000 unmounted
  protection. Never enable the retired publisher or use a second scratch mover.
- The five adopted files share hard links with legacy objects. Preserve legacy
  objects/manifests and never edit shared media bytes in place. NAS copying stays
  selective and uses the server-enforced read-only account and 100 GiB reserve.
- Preserve the existing share/private collection and independent Plex roots.
  Native ownership receipts are required for repeat/removal; do not adopt an
  unrelated destination. No whole-library copy, hash or permission rewrite.
- Preserve user pauses, retained failed jobs and the enabled cart feed. Do not
  enqueue diagnostic media, clear history or delete scratch to manufacture a pass.
- Backups run on the hosts with hourly retry and daily freshness. Keep original
  recovery snapshots immutable. Do not promise NAS-loss protection or deletion
  readiness from an old receipt.

Required private inventory overrides after restoration:

```yaml
qnap_data_root: /share/FromDrobo
qnap_catalog_cache_dir: /share/FromDrobo/Movies
qnap_native_tv_copy_enabled: true
qnap_backup_root: /share/Usenet/Backups/automatic
qnap_plex_root: /share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server
```

## NAS Usenet wiki — deployed

**Goal:** a simple reference site written for Ryan, with practical explanations
of the Usenet ecosystem and this installation. Working address:
`http://192.168.1.66:8090/`.

- [x] Build a static, mobile-friendly page with a table of contents, desktop
  sidebar, compact mobile navigation, bookmarkable sections, readable typography
  and a small favicon. Keep it usable with browser find and keyboard navigation.
- [x] Explain providers, indexers, NZB files, download clients, automation,
  storage and playback; include a glossary covering retention, completion,
  PAR2 repair, unpacking, RSS and quality profiles. Add an ecosystem diagram
  connecting indexers/Eweka, cloud applications, canonical Storage Box storage,
  selective NAS copies and Plex.
- [x] Add prominent shortcuts to SAB, Prowlarr, Radarr, Sonarr, the NAS copy
  dashboard, Plex, NZBGeek Cart, NZBFinder, Eweka and Hetzner. Verify destinations
  and use ordinary browser links, never token-bearing RSS/API URLs. Include
  official SABnzbd, Servarr, Plex and Storage Box documentation references.
- [x] Document everyday cart and Arr workflows separately: choosing a release
  or requested movie/TV title, checking download/import progress, selecting a NAS
  copy and choosing NAS versus Remote Plex libraries. Explain canonical storage,
  temporary scratch, local copies and backup boundaries. Distinguish deployed
  behavior from still-unproved acceptance; do not represent static text as live
  health or publish real media identities.
- [x] Include troubleshooting for full scratch, paused jobs, unavailable apps,
  delayed imports/Plex discovery and failed NAS copies, plus read-only diagnostic
  commands. Shortcuts open existing applications; the wiki has no live-control
  actions, embedded credentials, media listings or application API integration.
- [x] Store HTML/CSS/assets in `usenet-infra/wiki/`, without a frontend build
  framework, database or browser editor. Future edits go through this repository.
- [x] Add a dedicated Ansible playbook and root `just usenet-wiki-deploy` recipe.
  Run a separate Compose project under `/share/Container/usenet/wiki` using the
  repository's pinned Caddy image and non-root pattern. Bind specifically to
  `192.168.1.66:8090`, rechecking availability first; mount only site/config files
  read-only, with no media, secrets or Docker-socket access.
- [x] Use existing home-network/VPN reachability to the NAS, with no new VPN,
  public exposure or separate wiki login. Existing applications retain their
  authentication. The wiki serves nonsecret reference content only.
- [x] Validate before deployment, retain the previous release on updates and
  restore it if the HTTP smoke check fails. On a failed first deployment, stop
  only the new wiki service. Scope all deployment/restarts to the wiki container
  and preserve existing services and transfers.
- [x] Verify links, anchors, assets, desktop/mobile rendering, keyboard access,
  diagram readability, HTTP delivery, exact private binding, container health
  and rollback. Test existing VPN reachability from a connected client when
  available; otherwise record that acceptance limitation.
- [x] Run infrastructure tests, deployment syntax checks and current-source
  scanning for implementation changes. Report the two known historical
  secret-scan findings separately, rather than declaring the full scan green.
- [x] Record deployment evidence, the working URL and maintenance/rollback
  instructions in the relevant documentation. Source-controlled files make the
  wiki reproducible; do not claim added whole-NAS disaster-recovery coverage.

Wiki completion passed deployed delivery, browser inspection, idempotence and a
controlled rollback drill. LAN access is accepted; repeat reachability from a
connected off-LAN VPN client when one is available. Cloud repair, acquisition,
queue changes and storage purchases remain separate work.

## Download-capacity repair — implemented; extended validation remains

**Goal:** user-selected cart downloads automatically finish, import to the Storage
Box, pass independent verification, reclaim their exact scratch payload and appear
in Plex Remote, without exhausting the application disk. Keep the existing native
importer and its journals; failed archives are not completed library content.
This checklist now records the implemented fix and remaining extended validation.

### Recover the current incident

- [x] Capture fresh private SAB queue/history, RSS provenance, importer journals,
  active download/post-processing state, filesystem usage and application errors.
  Preserve manual pauses, `armed.json`, SAB history and all existing import phases.
  Keep acquisition held during recovery; do not restart SAB while its current
  in-memory queue cannot be persisted safely.
- [x] Prepare an exact-job space-recovery proposal for the retained failed and
  incomplete data, including media-006's changed state. Identify bytes, ownership,
  canonical verification where applicable and the consequence of each disposition.
  Obtain the specific decision before deleting protected payloads, abandoning a
  release or purchasing capacity. Do not label failed archives as imported movies
  or relocate them into Plex's library to manufacture free space.
- [x] After approved recovery restores working space, reconcile the observed
  placeholders against fresh exact job IDs and cart provenance. Preserve one
  intended request per release and all real progress; never deduplicate by title
  alone, clear all history or replay completed imports. Verify SAB can persist
  queue/RSS state before a scoped restart is considered. Investigate why repeat
  polls registered duplicates and ensure recovery cannot launch all copies.
- [x] Reconcile the worker's durable phases and let guarded retries resume after
  state writes and Arr APIs work. Verify canonical files and Plex entries for the
  three already imported movies without reacquiring them. Recheck cloud/discovery
  health, backups and cart polling; diagnose any remaining HTTP/database failure
  separately. Preserve native automatic cleanup and the disabled legacy publisher.

### Prevent another full disk

- [x] Restore and verify the intended `30G` download and completed-space settings
  in source and runtime using a narrow change that preserves enabled cart feeds.
  Report later drift through health checks. Do not run a settings helper that
  rejects enabled feeds by disabling those feeds to satisfy it.
- [x] Add capacity admission before a job starts downloading or unpacking. Budget
  the additional compressed bytes, peak unpacked output, repair overhead and
  safety margin while retaining at least 30 GiB free; account for already allocated
  bytes and every admitted job on the shared filesystem. Use validated size
  estimates or conservative bounds, and hold unknown/oversized jobs with a clear
  reason. A nominal release size or a fixed free-space threshold alone is not
  adequate proof that download plus extraction will fit.
- [x] Initially allow one admitted acquisition through download, repair, unpack,
  native import, verification and cleanup before admitting the next. Cover both
  cart feeds and Arr-owned downloads, including work already queued. Keep RSS
  selection polling enabled; register requests durably without starting their
  payloads. Retained failures consume capacity and must stop further admission
  when the budget is insufficient. Preserve native Arr ownership and avoid a
  competing mover or a second import path.
- [x] Make capacity holds durable and distinguish them from manual pauses.
  Release only holds owned by the controller, after recalculating capacity;
  preserve pre-existing and subsequent user pauses. Fail closed on unavailable
  SAB APIs, stale capacity state, missing canonical mounts or reservation faults;
  isolate importer/Arr holds per item while their retained bytes continue to count.
  Serialize admission decisions so concurrent polls cannot spend the same space.
  Recovery after a restart must reconstruct reservations from actual jobs and
  journals without duplicate acquisition, import or deletion.
- [x] Protect application/database/journal space through application-visible
  admission and both SAB 30 GiB floors. The controller uses `f_bavail`, so reserved
  root blocks do not satisfy its budget; it stops new acquisition before exhaustion.
  A separate scratch filesystem remains an optional future hard-isolation upgrade.
- [x] Apply the authorized failed-job policy only to controller-owned requests.
  Preserve SAB's exact retry metadata, remove only that failed attempt's payload,
  use SAB's native retry at most twice, then isolate the request without stopping
  unrelated work. Existing protected/manual jobs remain excluded. Expose the
  actionable state: awaiting capacity, downloading, unpacking,
  importing/verifying, cleaned, or failed/held, with the blocking reason and bytes.

### Validate and close

- [x] Test multi-cart bursts, repair/unpack peak usage, undersized free space,
  unknown sizes, retained failures, root/inode pressure, application/mount outages,
  manual pauses, controller restarts and duplicate polling. Assert that admission
  never overspends reservations, application state remains writable, and no
  protected job is resumed, deleted or imported twice. Use synthetic fixtures
  for failure tests rather than filling the live disk.
- [x] Run the infrastructure tests, deployment syntax checks and current-source
  secret scan for implementation changes; report the two historical secret
  findings separately. Review affected scripts and staged documents for media
  privacy. Update the agent guide and capacity/import runbooks with deployed
  behavior, configuration, recovery and rollback instructions.
- [ ] With actual user-selected eligible jobs, verify sequential automatic
  completion, canonical SHA-256, exact scratch cleanup, retained SAB history,
  restored reserve and Plex Remote indexing. Record sanitized receipts and verify
  a fresh encrypted backup includes controller state and importer journals.
  Keep fresh TV, Arr-owned cleanup and device-playback acceptance distinct.

The implementation validation passed 569 infrastructure tests with nine optional
skips, Python compilation, shell/config checks, all Ansible syntax checks including
`cart-import.yml`, current-source secret scanning and diff whitespace review. The
full recipe reaches its expected final failure only on the two already documented
historical RSA keys; no new credential finding is present in current source.

### Researched post-incident automation direction

The preferred simplification is **Seerr → Radarr/Sonarr → Prowlarr → SABnzbd →
native Arr completed-download handling → canonical library → Plex/Jellyfin**.
Seerr is the request layer and supports Plex, Jellyfin and Emby while sending
approved requests to Radarr/Sonarr. The Arr applications then own identity,
search, import and monitoring; Prowlarr owns indexer synchronization; SAB remains
the download/unpack engine. This removes direct indexer carts and the custom cart
import path for newly migrated requests instead of adding another orchestrator.

Keep the deployed capacity controller at the SAB boundary during that migration.
The standard applications do not reserve for this host's shared download,
repair, unpack and application-state peak. SAB pre-queue scripts can pause or
reject arrivals, but script failure accepts the job unchanged, so they are not a
safe replacement for the current fail-closed paused-intake controller. Add Arr
categories to the same admission contract and retire each cart feed only after a
real movie and TV request pass end-to-end with capacity serialization and native
cleanup. Keep Seerr private and deploy a current patched release: its project
identified three authentication/authorization CVEs fixed in version 3.1.0.

Jellyfin is a possible **parallel Plex alternative**, not a capacity or acquisition
fix. If Plex independence is desired, evaluate it later against the same canonical
library with read-only media access, separate metadata/config backups and verified
hardware transcoding; do not couple that trial to the queue migration. Seerr keeps
the request layer portable across Plex and Jellyfin.

Do not put Node-RED in the correctness path. Its flow model is useful for optional
notifications and dashboards, but context is in-memory by default and a second
workflow state store would duplicate the durable controller/import journals.
Recyclarr is optional later for declarative Radarr/Sonarr quality profiles,
formats and naming, with preview mode before changes; it does not solve admission.

Research references: [Jellyfin overview](https://jellyfin.org/docs/),
[Jellyfin transcoding](https://jellyfin.org/docs/general/post-install/transcoding/),
[Seerr overview](https://docs.seerr.dev/),
[Seerr service integration](https://docs.seerr.dev/using-seerr/settings/services/),
[Seerr 3.1.0 security release](https://docs.seerr.dev/blog/seerr-3-1-0-security-release/),
[Servarr application roles](https://wiki.servarr.com/),
[SAB pre-queue behavior](https://sabnzbd.org/wiki/configuration/5.1/scripts/pre-queue-scripts),
[SAB duplicate detection](https://sabnzbd.org/wiki/extra/duplicate-detection),
[Node-RED context](https://nodered.org/docs/user-guide/concepts), and
[Recyclarr features](https://recyclarr.dev/guide/features/).

## Outstanding acceptance

Complete these in order when their prerequisites are available. Read-only failure
investigation and existing-archive verification do not require a new selection.
Refresh health before fresh acquisition acceptance and allow failed-service or
quiet-state guards to defer work. Keep each acquisition route's result separate:
cart-worker cleanup does not prove Arr-owned client cleanup. The wiki checklist
is complete; its deployment remains independent of capacity recovery.

| Item | Next action and completion evidence | Prerequisite / closure |
| --- | --- | --- |
| September 16 cloud failures and capacity prevention | Finish the [implemented capacity repair](#download-capacity-repair--implemented-extended-validation-remains): preserve the deployed serialized controller, review health after the backlog drains and record the remaining movie/TV/backup acceptance independently. | Incident recovery, exact queue reconciliation and automatic admission are complete. Extended end-to-end evidence remains; no blanket queue release or storage purchase is needed. |
| New importer recovery checkpoint — passed September 17 | Independently decrypted/restored the fresh guarded cloud archive: all 660 files/four databases verified, exact current helpers and activation marker matched, controller state and all 21 importer journals captured. [Receipt](usenet-infra/recovery/drills/cart-capacity-checkpoint-20260917.json). | Current extension capture verified; repeat after later accepted completions change durable state. This does not establish replacement-host or whole-NAS recovery. |
| Fresh automatic cart movie and TV | September 17 review verified 13 native movie import jobs plus four existing-target reconciliations, recorded canonical SHA-256 evidence, exact payload absence, current native ownership and retained SAB history; all completed journals are backed up. Collect fresh Plex indexing evidence, distinguishing automatic indexing from manual scans, then observe selected TV completion. | Movie import/cleanup receipt and recovery coverage passed with recorded metadata limits. Plex indexing and TV remain pending. Do not reacquire accepted movies. |
| Automatic Arr-owned movie and TV | Observe new user-selected Arr-owned jobs through native import, automatic completed-client removal, scratch reclamation, stable canonical files and Plex discovery. | Separate evidence from the cart worker. No diagnostic acquisitions or repeat of an already accepted item. |
| Real TV selective NAS copy | Copy one actually available user-selected canonical TV title; verify same-bind staging, hashes, exclusive publication, safe repeat and Plex TV-library indexing. | Needs available selected TV content; layout and successful movie copying are insufficient. |
| Recovered oversized selection | Observe its restored exact request through the same controller-owned admission, bounded retry, import and cleanup path; do not bypass capacity serialization. | Its unjournaled failed payload was removed under the user's authorization and the request was preserved for automatic reacquisition. No manual resume or storage purchase is needed. |
| Apple TV/Roku playback and startup privacy | With Ryan's device interaction, verify restricted-profile cold start, NAS/Remote playback, seeking and relevant audio/subtitles. Keep the owner PIN private. | Explicitly user-deferred; not a source-merge blocker. Keep pending until actual device evidence exists. |

The five old Arr tracking entries and two archived scratch groups have a completed
investigation and deliberate retention decision. Do not reopen cleanup merely to
remove warnings. [Disposition](usenet-infra/recovery/drills/queue-disposition-20260914.json).
The external direct TCP/1337 probe passed for its dated WAN/port scope; repeat after
relevant network changes. Alternate static forwarding/proxy paths were not audited.
[Exposure receipt](usenet-infra/recovery/drills/nas-exposure-20260914.json).

The requested NAS wiki is deployed and accepted through the checklist above. Other portals,
NAS-loss protection, whole-machine replacement/reboot drills, additional providers,
LAN HTTPS and capacity purchases remain separate projects. Billing unknowns stay
in the cost ledger. Do not expand this handoff into account setup, unrelated Home
Assistant work, or a default-branch merge.

## Closure and merge criteria

**Implementation closure** means the deployed scope above has durable receipts,
the new native and cart-worker state is captured in verified backups, operational follow-ups
remain explicit, and no authorized transfer/deployment or shared-agent edit is
left running. The newly requested wiki also requires its deployment/validation
checklist and maintenance handoff to be complete. It does not mean client tests
or a fresh import were observed, or that unresolved cloud failures are repaired.

If a merge is later requested, **merge readiness** requires all of the following
on the final reviewed branch head. Use no PR workflow.

1. One reviewable `usenet` → `master` change set describes Usenet infrastructure, Plex/NAS
   copies, recovery/backups, and the five lockfile/security changes. No unrelated
   lighting work, private inputs, media, `msg`, or scratch helpers are included.
2. Review the whole diff and current base. `master` was an ancestor of the branch
   at this audit; recheck before merging and resolve any later conflicts in an
   isolated checkout. Do not pull other unfinished feature branches into it.
3. Run root `just test` and `just usenet-test` against the reviewed source, plus
   current-source/index secret scanning. Functional/build/syntax failures or new
   credential findings block merge. The only known full-history failures are the
   two documented keys already present in `master`; the reviewer must acknowledge
   that existing exposure explicitly. Do not hide it, waive new findings, rewrite
   history to hide credential findings, or call the full scan green. The completed
   media-privacy rewrite did not remediate these historical keys.
4. Record fresh affected-service health and preserve rollback/recovery instructions.
   Deferred media/device/security acceptance must remain visible in the plan and
   validation ledger; merge is not a claim that those tests passed.
5. Obtain final review/approval and satisfy any repository-required checks before
   a requested merge. Do not create or reopen a PR. This wrap-up defines the gate;
   it does not execute the default-branch merge.

**Branch closure after merge:** use a merge that preserves the evidence-referenced
commit history; confirm `master` contains the reviewed head and the remote merge
succeeded. Preserve dirty work on its own reviewed branch/backup before changing
its checkout. Only then remove the merged local/remote `usenet` refs and stale
worktree registrations. Do not delete a checkout as branch cleanup.

## Other branches and local work

At the September 13 cleanup checkpoint, three fully merged local refs were removed:
`codex/docs-sonos-replacement-plan`, `codex/sonos-partial-availability`, and
`two-line-labels`. Their commits remain in published `master`. Eight registrations
for already missing worktrees were pruned; no existing worktree was removed.

| Retained branch | Disposition |
| --- | --- |
| `usenet` | Prior implementation and the private NAS wiki are deployed; capacity repair and remaining media/device acceptance stay outstanding. PR #117 closed at user request. No PR workflow. Branch preserved; merge not requested. |
| `ml/blinds-only` | Three unique commits; retain for its own scope/review, do not bulk merge. |
| `mobile` | Five unique commits, including unfinished responsive/editor work; retain. |
| `nuheat-integration` | Eight unique commits; retain its integration/recovery context. |
| `wall-to-favicon--tetris-controller` | Four unique commits for a separate feature; retain. |

Those branch counts are dated observations; recheck before any branch operation.
The four other feature branches include unpublished commits and require their own
review/publication before deletion. Both existing worktrees contain unrelated
lighting changes; the main checkout also has `msg`. All five stashes remain.
These are preserved work, not abandoned Usenet tasks or permission to deploy HA.

For routine status, use `just usenet-discovery-health`, `just usenet-cloud-health`,
`just usenet-qnap-health`, `just usenet-cart-import-status`, `just native-status`,
and the dashboard. Keep media-bearing status output private. Current detailed
procedures and evidence live in linked runbooks; superseded planning is in Git.
