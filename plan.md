# Usenet integration end-state and cutover plan

## Remaining-work execution — September 22, 2026

The user authorized all remaining follow-ups and explicitly requested disposal
of old held downloads. Three exact old zero-progress SAB requests were discarded;
14 failure records for seven held journals were resolved with a baseline-bound
disposition receipt. All 44 immutable journals and historical hold evidence remain
preserved. Recorded payload paths were already absent, so this operation claims
**zero newly reclaimed payload bytes**. Cloud health now passes.

The selected native TV copy, destination SHA-256 verification, safe repeat and
exact-file NAS Plex discovery passed. A forced scan of general library 3 was
needed. The user confirmed playback and restricted privacy on **both Roku and
Apple TV**; this is user verification, not a separate agent-run codec matrix.

Filex encrypted daily capture and NAS SFTP settings coverage are deployed.
Independent restores verified 26 current server files/one database, 40 bootstrap
escrow files (including the operator CA key), and 63 NAS configuration files.
Plex's separate three-file archive passed byte verification and both databases
opened; the generic SQLite checker cannot validate Plex's custom tokenizer.
See [Filex recovery](usenet-infra/docs/filex-recovery.md). All four encrypted
archives also passed Storage Box readback and match the independently restored
copies. This is a one-time off-host NAS settings checkpoint, not an ongoing
NAS-originals backup.

The authorized Seerr request passed download, native import, complete source
cleanup, exact-file general Plex discovery and Seerr availability/playback-link
checks. The imported file is 2160p (2960×2160 for its aspect ratio), using profile 5.
The first 4K release was unrepairable, short by 1,156 repair blocks. Its exact test
payload was discarded after identity verification; a smaller eligible 4K release
was selected manually for the same request. No quality rejection was bypassed
and future automatic selection remains unchanged. This is an API-submitted
request with a manual alternate, not a successful fresh browser sign-in test.

The bounded two-stream capacity exercise passed: two 50 GiB expansions with
100 GiB of retained allocation, 200.22 GiB peak allocation and 90.97 GiB still
free. All synthetic files were removed. The final encrypted checkpoint,
`cloud-20260922T215403Z.tar.age`, passed off-host readback and independent
restore: **752 files, five application databases and all 44 journals**, including
the disposition, Seerr and capacity receipts. Both nested Filex bundles also
independently restored. Final cloud, NAS, native ownership, discovery, Filex and
Seerr health checks pass; only retained historical holds remain informational.
Infrastructure validation ran 708 cases with nine optional skips and no test
failures. Syntax and current-source scanning pass; full-history scanning still
reports the two documented historical RSA keys.

The embedded-browser Plex sign-in did not advance; user verification in the
normal browser is pending. The user prohibits changes to the host machine’s trust policy.
Installing the Filex CA is therefore excluded from the plan, not a pending
approval. Existing explicit-CA HTTPS checks remain valid; warning-free browser
access under the unchanged host policy is not yet established.

A [replacement-server drill](usenet-infra/docs/replacement-drill-20260922.md)
is validated and planned in a separate Terraform root. It creates only four
disposable resources; it awaits the requested USD 1 spending ceiling. No temporary
server has been created. NAS-loss backup scope (originals plus settings versus
settings only) also awaits the user's answer. Do not treat either pending answer
as approval. These explicit dependencies replace the old blanket deferrals below.


## Seerr quality preference — September 22, 2026

The user requested 4K. Seerr's movie and TV defaults now use the existing
**Ultra-HD** quality profile (ID 5), with 2160p preferred and 1080p allowed
as fallback at the user's request. All eligible 4K sources rank above 1080p.
Within each resolution, the native profile's source-quality ranking is retained.
The single-copy request workflow remains in use;
existing library items and requests were not bulk upgraded or searched.
Automatic upgrades, RSS, watchlist acquisition and direct carts remain off.
This supersedes the initial 1080p default in the dated deployment record below.

## Seerr deployed — September 22, 2026

[Seerr](http://10.77.0.1:15055/) is the browsing/request entry point; sign in
with the existing Plex owner account. Trending, popular movies and popular TV
feeds each returned 20 results. Radarr and Sonarr connections verify with the
HD-1080p profile and canonical library roots. Only general Plex library IDs
2/3/4/5 are selected; the completed availability scan found 40 available media
records. The private library remains excluded. No media request was created.

Both indexer cart feeds stay disabled, as requested. Prowlarr still uses the
indexers for explicit Arr searches. Watchlist acquisition and RSS polling stay
off; selected TV seasons can be requested, and future episodes require explicit
Sonarr searches. Existing paused jobs, 44 journals and retired-worker guards
remain preserved. Native ownership, discovery, NAS and Filex checks pass.

Seerr's private login page renders in the browser, anonymous discovery returns
401, and the app backend is loopback-only. A fresh interactive Plex browser
sign-in and an actual new media request were not exercised. The encrypted
`cloud-20260922T201332Z.tar.age` independently restored **732 files and five
SQLite databases**, including Seerr settings/database, and all 44 old journals.
This is isolated archive recovery, not replacement-host startup.

Infrastructure validation ran **701 cases**, with nine optional skips and no
test failures; deployment syntax and current-source scanning pass. Full-history
scanning still reports only the two documented historical RSA keys. See the
[Seerr runbook](usenet-infra/docs/seerr.md) and
[acceptance receipt](usenet-infra/recovery/drills/seerr-20260922.json).

## Source checkpoint — September 22, 2026

The native cutover, repair-volume and Filex implementation, application updates,
and sanitized deployment/recovery evidence are recorded together in this source
checkpoint. The root `just test` recipe passed, including container checks.
Infrastructure validation reran 694 cases: 685 passed and nine optional skips;
compilation, shell/YAML and deployment syntax checks passed. Current-source/index
credential scanning passed. The full-history scan still reports only the two
documented historical RSA keys; no exemptions or history rewrite were added.
Unrelated Home Assistant lighting edits and the pre-existing `msg` remain outside
this checkpoint. Earlier statements about staging and commits describe those
dated operations. The remaining-work table below continues to apply.

## Application update completed — September 22, 2026

The user approved the prepared production maintenance. **Radarr 6.4.4.10685,
Sonarr 4.0.20.3014 and Prowlarr 2.6.5.5623 are deployed and verified**, using the
exact reviewed image tags. All three containers are healthy and application
health reports zero findings. Discovery policy and native ownership pass;
RSS remains off, native cleanup/reserves remain enabled, and retired timers
remain inactive. See the [deployment receipt](usenet-infra/recovery/drills/app-maintenance-20260922.json)
and [maintenance/rollback runbook](usenet-infra/docs/app-maintenance-20260921.md).

All three held requests remain paused, all 44 journals and historical fingerprints
match, and catalog failure files are unchanged. SAB's container ID and start time
are unchanged. NAS and Filex private HTTPS health pass. Anonymous private proxy
requests still return 401; the updated APIs accept the proxy Host header with
valid credentials. A fresh browser login was not tested. Cloud health remains
nonzero **only for the 14 retained historical catalog failure records**; no
application-update warnings or health exceptions remain.

The updater stopped during verification because its wrapper disallows a Prowlarr
health command. The command was refused before dispatch, after all applications
had started. Verification resumed by reading Prowlarr's startup health and
checking discovery/ownership/history; deployment was not replayed. All three
stopped pre-update database copies pass SQLite integrity and remain available
with the old pins/images for deliberate rollback.

The new `cloud-20260922T191826Z.tar.age` passed remote ciphertext readback,
independent decryption and isolated restore: **726 files, four databases, all
44 journals and 59 live hash matches**. Six mount/service unit hashes remain
unchanged. The earlier recovery checkpoints remain intact. The prepared-source
694-case validation (nine skips, no failures) still applies; no implementation
changed during deployment. No new acquisition, TV copy, held-record cleanup,
Plex/NAS restart, staging or commit occurred. The dated preparation and audit
checkpoints below are provenance; this deployed state supersedes their pending
application-update instructions.

## Recovery verified; application update prepared — September 21, 2026

The accepted native state now has independently verified recovery evidence.
`cloud-20260921T155229Z.tar.age` passed encrypted remote readback, local ciphertext
comparison, authenticated decryption and an isolated restore: **726 files and
four SQLite databases**. All **59 selected live configuration/helper/journal
hashes** match the restore, including all 44 journals and native ownership and
acceptance receipts. Six live mount/service definitions reconstruct exactly from
repository sources and the restored volume identity; the repair binding override
and live volume/dependency checks also pass. See the
[recovery receipt](usenet-infra/recovery/drills/native-state-restore-20260921.json).

This closes the accepted-state isolated restore item. It does not establish
replacement-host startup, NAS-loss protection or Filex recovery. Systemd units
were reconstructed/compared, not captured as `/etc` files. Local Terraform and
inventory are outside the cloud archive; current BX21, repair-volume, NAS paths
and TV-copy overrides were checked and remain unchanged. Preserve them and the
uncommitted source checkout separately; original bound snapshots are immutable.

The three application updates are **reviewed and prepared, not deployed**:
Radarr `6.4.4.10685-ls318`, Sonarr `4.0.20.3014-ls325`, Prowlarr
`2.6.5.5623-ls161`. Source pins and version guards agree. Official release/source
review found the integration interfaces unchanged. Infrastructure validation ran
**694 tests**, with **nine optional skips** and no test failures; syntax checks
passed, and full-history scanning still reports only the two documented RSA keys.
The [maintenance runbook](usenet-infra/docs/app-maintenance-20260921.md) contains
the exact scope, stopped-state backup and rollback procedure.

Automatic approval review blocked the live three-container update because it
requires explicit user approval for the concrete production maintenance. That
approval is pending; no application was stopped or replaced. A separate question
asks whether the already imported acceptance series should be used for the NAS
TV-copy test; no copy was started without that selection. Native ownership and
NAS health pass, all three requests remain paused, and the known historical
catalog findings/update notices remain. No changes are staged or committed.

## Earlier health audit — September 20, 2026, 22:05 UTC

The requested health audit is complete. Native ownership remains **active and
verified**, with no pending cutover requirements or measured capacity shortfalls.
All three requests remain individually paused, global SAB is resumed, and no
postprocessing is active. The ownership check confirms historical state is
unchanged: 44 journals, 37 completed journals, 27 importer holds and ten capacity
holds. All three retired timers remain disabled. NAS health and Filex service/
private HTTPS health pass; SAB responds without warnings.

Cloud/discovery health remains nonzero for identified, retained findings:

- **14 historical catalog records refer to seven held journals**, dated September
  17–18. Three journals have source-identity mismatches and four have ambiguous
  catalog identities. Nine records report import holds; five report failed cleanup
  attempts whose journals now contain later completed disposition receipts and no
  disposal error. This is receipt reconciliation, not a new source-file integrity
  check or authorization to clear records, release holds or download replacements.
- Radarr, Sonarr and Prowlarr each report exactly one **update-available warning**.
  No other application health findings were returned. Cloud health fails on the
  catalog records and Prowlarr warning; discovery health rejects the Arr warnings.
  No health exceptions, application updates or restarts were applied.
- Scheduled backup status is fresh: cloud last succeeded at **19:01:42 UTC**,
  NAS at **04:07:26 UTC**, both September 20. Cloud capture predates the accepted
  native checkpoint at 20:18 UTC. Freshness does not close the independent restore
  gap for the accepted state, and Filex remains outside existing backup coverage.

See the [sanitized audit receipt](usenet-infra/recovery/drills/health-audit-20260920.json)
and [health interpretation](usenet-infra/docs/operations.md#health-and-failures).
Raw API records stay in ignored, private
`usenet-infra/build/health-audit-20260920/`. This continuation changed only the
handoff, documentation and sanitized evidence; production and all pre-existing
checkout changes are preserved. Nothing is staged or committed.

## Remaining work and explicit deferrals

The native cutover and Filex rollout are complete. The old hybrid next-admission
test is **superseded**, not an outstanding requirement: do not re-enable carts or
retired workers to satisfy it. Use this table for follow-up work instead of the
dated checkpoints below.

| Status | Follow-up | Completion evidence |
| --- | --- | --- |
| Passed September 22 | Apply the three reviewed pinned application updates. | Exact images deployed; application health, native ownership, historical preservation, private access checks and post-update isolated restore pass. See the [receipt](usenet-infra/recovery/drills/app-maintenance-20260922.json). |
| Passed September 22 | Discard the three old paused requests and reconcile seven held journals. | Exact identities recorded privately; 14 failure records resolved, all 44 journals preserved and cloud health passes. No payload bytes were reclaimed because recorded payloads were already absent. |
| Passed September 22 | Independently restore accepted native/storage state. | Final cloud archive independently restores 752 files, five databases, all 44 journals and both nested Filex bundles; remote ciphertext readback passes. |
| Passed September 22 | Selected TV-series NAS copy and safe repeat. | Destination SHA-256 verification, unchanged owned copy on repeat and exact-file general NAS Plex discovery pass. |
| Host trust changes prohibited | Filex browser access under existing trust policy. | Do not install the private CA or change host trust settings. Explicit-CA HTTPS checks pass; warning-free browser access remains unverified. |
| Passed September 22 | Filex configuration/state recovery. | Daily encrypted snapshot, bootstrap-key escrow and NAS SFTP configuration capture deployed; isolated restores and off-host ciphertext readback pass. See [Filex recovery](usenet-infra/docs/filex-recovery.md). |
| User verified September 22 | Apple TV/Roku playback and restricted privacy. | User explicitly confirmed both devices; no agent-run codec/subtitle matrix is claimed. |
| Passed September 22 | Seerr request through download/import. | A real request completed using a manually selected eligible 2160p alternate after an unrepairable release; import/cleanup, Plex exact-file indexing, Seerr availability and playback link pass. |
| User verification pending | Interactive Seerr browser sign-in. | The embedded-browser flow did not advance; normal-browser confirmation is requested. |
| Passed September 22, bounded scope | Concurrent scratch and high-expansion capacity. | Two 50 GiB streams independently verified with 100 GiB retained allocation; 200.22 GiB peak, 90.97 GiB free and complete fixture cleanup. Existing limits remain; arbitrary expansion is not proven safe. |
| Prepared, spending decision pending | Replacement-server startup. | Separate create-only four-resource plan, reviewed scope and cleanup procedure; proposed USD 1 ceiling. |
| Scope answer pending | NAS-loss protection. | Await originals-plus-settings versus settings-only choice; private originals have not been read or uploaded. |

## Completed — native Arr cutover, September 20, 2026

The cutover is **accepted and active**. One fresh movie and one fresh episode
passed native acquisition, canonical import and exact completed-source cleanup.
Plex discovered the movie automatically; the episode was verified against its
exact imported file after a general remote TV library scan. An **80 GiB**
synthetic PAR2 reconstruction passed independent SHA-256 with both complete
copies present and **131.15 GiB** still free at full replacement. Its temporary
fixture was removed. A scoped SAB/Arr restart preserved imported ownership,
limits, pauses and historical state; all three retired workers refused startup.
See the [acceptance receipt](usenet-infra/recovery/drills/native-cutover-20260920.json)
and [operating/rollback runbook](usenet-infra/docs/native-cutover.md).

New requests start in **Radarr or Sonarr**, using add-and-search or explicit
search for the intended movie/episode scope. Distinct categories, a 100 GiB
release limit, top-of-queue downloading, postprocessing pause and 30 GiB SAB/Arr
reserves remain in force. Wait for import and cleanup before another large
request. Direct carts, Prowlarr direct downloading and all three legacy workers
are disabled. RSS stays off to preserve seven pre-existing monitored missing
movies. Native checks and cleanup are the user-approved integrity policy for
new requests; historical independent SHA-256 evidence remains intact.

The original **three paused requests**, all **44 journal hashes**, **37 completed
journals**, **27 importer holds**, **ten capacity holds**, activation and original
SAB history are unchanged. Three distinct failed releases from the first fresh
TV selection downloaded zero payload; their failed records remain preserved and
that selection is unmonitored. A replacement random episode completed acceptance.
No historical completed media was reacquired and no old hold was released.

The approved BX21 (5 TiB) and 300 GB repair-volume expansion is deployed,
retaining CX43, for **+$32.01/month** at the confirmed catalog rates. Final free
capacity is **291.18 GiB** on the repair spool and **3.98 TiB** remotely. The
original spool remains intact. Updated private Terraform inputs must survive
restoration of older snapshots; do not repeat purchases or migrations.

Read-only `just usenet-native-ownership-status` and
`just usenet-native-cutover-preflight` report active ownership, recorded acceptance,
zero capacity shortfalls and no pending cutover requirements. The field guide
at `http://192.168.1.66:8090/` now documents the native request flow.
Infrastructure verification ran **693 cases**, with **nine optional skips** and
no test failures. Syntax/current-source checks pass; the full recipe remains
blocked only by the two documented historical RSA keys. NAS health passes;
14 existing catalog failures and application update notices remain visible and
unwaived. Device playback, broader concurrency/arbitrary archive expansion,
selective TV copying to NAS and whole-machine/NAS-loss recovery are not claimed.
No changes are staged or committed; pre-existing checkout changes are retained.

The dated checkpoints below are provenance. Their active cart/timer instructions
are superseded by the accepted native policy above.

## Storage expanded — September 20, 2026

The user approved and the deployment completed the existing Storage Box upgrade
from BX11 to **BX21 (5 TiB)** and a **300 GB repair volume**, retaining the CX43 VM.
The confirmed catalog increase is **$32.01/month** ($9 + $23.01; USD, account VAT 0%).
The 18:03 UTC preflight measured **291.18 GiB** free on the repair spool and
**4.06 TiB** free remotely. Both observed-workload shortfalls are now zero,
including full repair replacement, import-copy fallback and the 30 GiB reserves.
See the [expansion record](usenet-infra/docs/storage-expansion-20260920.md),
[repair-volume runbook](usenet-infra/docs/repair-spool.md) and
[sanitized receipt](usenet-infra/recovery/drills/storage-expansion-20260920.json).

Only the incomplete spool moved. Its 535 files (28,639,139 bytes) matched full
SHA-256 and metadata inventories; the original remains intact. Canonical paths
and the library were not migrated. The controller checks the pinned volume,
root disk and remote filesystem independently. Missing-mount startup refusal,
mode-0000 unmounted write protection, scoped service restart, a 128 MiB synthetic
PAR2 repair with independent SHA-256, both Arr application-user hardlink probes
and NAS server-enforced read-only access passed. This storage-only probe was followed by the accepted 80 GiB reconstruction
recorded above.

The three individually paused requests, SAB history, all 44 journal hashes,
activation, ten capacity holds and original feed/pause settings are unchanged.
There are 37 completed journals, 27 importer holds and zero importer errors.
At that storage checkpoint the three timers and two feeds were active and
global SAB was resumed, with
no admitted or postprocessing job. The 14 existing catalog failures and update
notices remain unwaived. NAS health passes. No media was deleted or reacquired.

The subsequent native cutover completed as recorded above. The storage receipt
remains a dated pre-cutover checkpoint, including its original feed/timer states.

Use `just usenet-native-cutover-preflight` for a private, read-only baseline;
its capture is `preflight_only`, while its ownership/acceptance fields report
the saved live result. The read-only command itself never performs a cutover. Detailed
evidence is in ignored `usenet-infra/build/storage-expansion-20260920/`.
Preserve updated private Terraform inputs after restoring older recovery data:
Storage Box `bx21`, cloud `repair_spool_enabled = true`. The original bound SOPS
snapshot remains immutable; expansion is not a whole-machine restore milestone.
No changes are staged or committed.

## Earlier September 20 checkpoint — features deployed and recovery verified

The private Filex portal is deployed at **https://10.77.0.1:5213**. Both dedicated
staging roots support recoverable writes; canonical Storage Box roots remain
read-only. Live acceptance passed browsing, metadata, search, eight browser sort
directions, file/folder download hashes, copies, verified moves, restore,
interruption/retry, client disconnect, confinement and coexistence with real SAB
postprocessing and native import. See the [portal runbook](usenet-infra/docs/filex.md)
and [acceptance receipt](usenet-infra/recovery/drills/filex-pilot-20260919.json).
Strict HTTPS validation against the private CA passes. User trust settings
have not been changed; the subsequent user instruction prohibits changing the
host trust policy, superseding the earlier optional CA-installation proposal.

The user-approved admitted recovery completed. Matching preserved metadata was
restored, SAB finished downloading, and isolated remote PAR2 repair plus independent
SHA-256 passed. Reversible local repair changed seven blocks (28 MiB), preserving
original blocks and hashes. Native SAB retry completed, and Radarr imported the
73,961,948,234-byte media file by hardlink. Independent Storage Box metadata showed
the same device/inode and two links; canonical SHA-256 matched both the source and
the verified repair. Exact source unlink completed with durable intent, leaving
one canonical link. Six non-media files (21,313,535 bytes) remain deliberately
retained. The journal is `cleaned_with_retained_files`, not a failed import.
See the [recovery receipt](usenet-infra/recovery/drills/admitted-recovery-20260920.json).

The deployed fixes reserve a full local PAR2 replacement, protect a recovered
failed payload from automatic reclamation, and handle Radarr's duplicate-copy
space rejection only after proving the exact source supports hardlinks and the
30 GiB reserve remains. The importer keeps its read-only canonical boundary;
Arr's global settings and both SAB `30G` floors are unchanged. The NAS dashboard
now traverses only canonical Movies/TV, and its refresh and health checks pass.

The importer reports **37 completed journals, 27 held records and zero errors**.
Both timers are active, global SAB is resumed, and the capacity controller is
idle without a blocked reason. All original ten capacity holds are preserved.
The three remaining requests are individually paused and held: one has ambiguous
catalog identity and two require identity resolution before redownload. There
are **zero eligible requests**. No other request was manually released, and no
unchanged rejected source was reacquired. A fresh next-admission demonstration
requires a new eligible user cart selection; that live criterion remains pending.

Cloud/discovery health still reports 14 existing catalog failures and update
notices in Radarr, Sonarr and Prowlarr. They remain visible, not waived. NAS and
portal health pass. Backup/restore work and TV/Plex device acceptance remain
outside this closure.

Validation ran **668 infrastructure tests**, with nine optional skips and no test
failures. Syntax and current-source secret checks pass. The full recipe fails only
on the two documented historical RSA keys. The reviewed portal has zero reachable
Go vulnerabilities and zero production npm audit findings in the September 20
scans. No changes were staged or committed.

## Target end-state — Arr owns new media requests

Radarr and Sonarr own each new movie and TV request from selection through
import. Prowlarr supplies indexers; the owning Arr application sends a
category-tagged job to SABnzbd, tracks it through completed-download handling,
imports it into the canonical Storage Box library, and removes the completed
download when its own import/cleanup rules allow. SAB owns downloading, repair,
and its native queue and free-space protections. Plex reads the resulting
library. A request must not enter SAB directly from the old cart feed or from
two independent owners. Ambiguous identities are resolved before selection in
Arr, not guessed after a release has downloaded.

The Storage Box remains canonical and the NAS remains a read-only consumer of
canonical media. SAB completed downloads and Arr library paths must be visible
through a consistent shared filesystem layout with permissions and native
hardlink behavior verified on the actual mounts. Provision enough measured
headroom for the largest admitted download, a full PAR2 replacement and reserve
in SAB's incomplete area, plus completed-download/import behavior and reserve
on the Storage Box. Size for a full copy if native import can fall back to a
copy; do not depend on the current special-case override of Arr's free-space
check. Native free-space thresholds and a conservative SAB queue limit remain
enabled. The exact capacity and queue settings come from a measured worst-case
preflight, not from the present small-job success.

The custom cart importer, capacity-admission timer, per-job journal gate,
reclaim controller, and hardlink free-space exception are retired as active
decision-makers for **new** requests after cutover. Existing journals, holds,
SAB history, verification receipts, and activation provenance remain preserved
for audit and disposition; they are not replayed into Arr or silently released.
The Filex portal remains an operator convenience on its separately approved
roots and has no authority over active downloads or canonical media.

The user explicitly accepted native Arr import and cleanup on September 20.
Independent SHA-256-before-source-unlink is no longer required for new Arr-owned
requests. Native completion/import checks, verified storage and existing recovery
coverage form the selected policy; this does not claim native cleanup provides
the retired gate's guarantee. Preserve historical SHA-256 receipts unchanged.

## One-time cutover — no library migration or replay

1. Record a sanitized baseline of SAB queue/history, Arr download clients and
   categories, the three held requests, importer journals, storage mounts and
   free space. Preserve all holds and any in-flight payloads. Stop new direct
   cart-to-SAB submissions while the existing pipeline reaches a safe idle
   point; do not manufacture an eligible job from a held request.
2. Measure worst-case repair and import space on the actual filesystems, then
   provision the needed headroom and set native SAB limits. Verify the shared
   completed/library path, permissions, hardlink behavior, Arr free-space
   acceptance, and Storage Box read/write boundaries. Resolve the integrity
   policy above before admitting a new request.
3. Configure Radarr and Sonarr as the only media request owners, with distinct
   SAB categories, completed-download handling, and cleanup. Route the user
   selection flow into the appropriate Arr application. Disable the old direct
   cart feed and custom admission/import timers for new requests together;
   retain their data and a documented way to restore their configuration.
4. Admit one newly selected movie and one newly selected TV episode through
   Arr. Confirm each has exactly one owner, SAB repairs/completes within its
   free-space floor, Arr imports to the canonical Storage Box path and cleans
   only its owned completed source, and Plex can discover the result. Include
   a representative large/repair case and a service-restart check before
   lifting the conservative queue limit.
5. Confirm the three pre-existing held requests and all historical journals
   are unchanged. Review them separately for explicit disposition; no bulk
   release, redownload, deletion, or legacy backfill is part of this cutover.
   Remove obsolete active services/configuration only after the native path
   passes and the preserved evidence is accessible.

If preflight or the first native request fails, stop new admissions and restore
the prior routing/configuration while preserving every payload and hold. Once
native jobs have started, reconcile those jobs with their Arr owner before any
rollback; never run the old importer against the same source in parallel. The
cutover is accepted only when native movie and TV imports, cleanup, space
limits, restart recovery, and held-request isolation are demonstrated and the
integrity-policy decision is recorded. These criteria passed September 20;
the earlier hybrid operating invariants below are historical.

## Previous state — September 18, 2026, 18:14 UTC

The hybrid acquisition layout remains deployed and verified, but the first live
acceptance job has not completed. The fresh handoff audit shows the queue is
currently paused and the cart importer is failed; no manual release, reserve
reduction, or source deletion was used.

| Area | Current evidence |
| --- | --- |
| Queue | Six requests remain: five are paused and one is queued; no postprocessing is active. |
| SAB | Global queue pause is active. Both staging mounts remain active. |
| Admission | One request remains admitted; the controller is not blocked, but the admitted item has not progressed to import. |
| Automation | `usenet-capacity-admission.timer` and `usenet-cart-import.timer` are active. |
| Storage | Root free space is about **57.1 GiB**; remote staging free space is about **262.1 GiB**. |
| Hybrid layout | Marker is version 2 with native hardlinks enabled; migration receipt is `verified`. Radarr and Sonarr hardlink probes passed. |
| Importer | 34 completed journals, 24 held records, and zero disposal errors, but the importer service is failed and has not advanced the journal. |
| SAB floors | `/data/incomplete` and `/data/complete/remote/complete` remain configured with `30G` floors. |
| Health | Cloud health reports unresolved catalog failures and a Prowlarr issue; NAS health reports a failed catalog refresh. These are recorded as acceptance blockers, not waived. |
| Backups | Backup capture and restore are intentionally out of scope for this closure. Existing scheduling is not part of acceptance. |

The earlier 17:59 snapshot said the admitted request was advancing, but the
18:14 audit does not confirm that progress. Preserve the admission, queue pause,
held records, and source payload while diagnosing the failed importer; do not
manually release the queued item or restart the workflow blindly.

## Acceptance state of the deployed hybrid path

1. Importer recovery and retained admission ownership: **passed**; recovery and
   native retry are tied to durable matching metadata and journal evidence.
2. Native SAB postprocessing: **passed** (`Completed`).
3. Native Arr hardlink, independent SHA-256 and exact media-source cleanup:
   **passed**; six non-media files remain retained for review.
4. Error-free importer advancement: **passed**. Next automatic admission:
   **pending a new eligible user cart selection**; all three current requests
   have existing identity holds, so idle is the correct controller behavior.
5. Held-record isolation: **passed**; original holds are preserved and do not
   globally pause acquisition. Do not clear holds or reacquire rejected inputs
   merely to manufacture an admission demonstration.
6. Health checks: **completed**. NAS refresh is fixed. Existing catalog failures
   and application update notices remain explicitly documented and unwaived.
7. Sanitized portal/recovery receipts and current operator documentation:
   **recorded**. Exact media paths, identifiers, hashes and credentials stay private.

Plex indexing of later imports, TV-specific acceptance, Arr-owned cleanup, and
deferred device playback were outside this deployed-path acceptance. The
one-time cutover above adds native TV import, Arr-owned cleanup, and Plex
discovery to its own acceptance checks; device playback remains separate.

## File management portal — implemented

### Implementation status — September 20, 2026

The portal implementation and deployment are complete. It uses a shell-free,
non-root, resource-limited image with the reviewed backend safety patch, private
TLS, pinned NAS SFTP, separate operator credentials and exactly three roots.
The application and proxy deny canonical writes, permanent deletion, root escapes,
administration and executable plugins. Moves independently hash destinations,
write durable receipts and quarantine sources. Interrupted operations stay visibly
failed until an explicit retry; a 256 MiB interrupted synthetic transfer passed
retry and independent destination verification after client disconnect.

Live synthetic portal acceptance and coexistence with recovered native SAB
postprocessing, import and verified cleanup passed. The dedicated
CA is available locally; no user trust settings have been changed. The runbook
contains build/deploy/status/disable, credential boundaries, resource limits and
rollback instructions. Portal backup coverage remains separate.

Set up a small, private file-management portal using **filex** so the NAS,
download host, and Storage Box can be inspected and operated from one simple
web UI. This is an operator convenience layer, not a replacement for SAB,
Radarr, Sonarr, the importer, or the existing native NAS-copy workflow.

### Intended use cases

- Browse each host's approved filesystem roots from a browser.
- Sort directory listings by name, extension, size, and modification date;
  search for a file or folder by name and inspect its size and timestamp.
- Download individual files or folders to the operator's computer.
- Delete or move disposable download scratch, failed payloads, temporary
  archives, and other explicitly approved files.
- Copy or move selected files between the download host, NAS, and Storage Box,
  with a visible transfer state, error reporting, retry behavior, and
  verification before a source is removed.
- Keep transfers running when the browser is closed, where the selected
  filex workflow supports durable server-side progress.
- Provide read-only visibility into canonical media until a separate deletion
  policy has been reviewed and accepted.

### Deployed shape

Run filex on the download host, where it can reach the three systems over the
existing private network and SSH/SFTP paths. Configure three separately named
storage roots rather than presenting one unrestricted filesystem:

| Root | Initial access | Scope |
| --- | --- | --- |
| Download host | Read/write | Dedicated portal staging; active acquisition and importer files excluded |
| NAS | Read/write | Dedicated portal staging over pinned SFTP; no broader share or cache writes |
| Storage Box | Read-only | Canonical Movies/TV and isolated portal scratch; acquisition metadata excluded |

Use dedicated low-privilege credentials, host-key verification, TLS through the
existing private access path, and an application account with a strong secret.
Do not expose the portal directly to the public internet. Do not give the
portal shell access, unrestricted `/`, Docker control, or access to secrets,
application databases, importer journals, or backup keys.

### Safety rules

- The Storage Box remains canonical. Direct edits to canonical media must not
  bypass Arr ownership, importer journals, hardlink relationships, manifests,
  or independent verification.
- The NAS reader credential remains server-enforced read-only wherever the
  current design requires it. A writable NAS path must be a deliberate cache
  or staging path, not an accidental broader share mount.
- Deletion of canonical media, legacy media, shared hardlink sources, active
  downloads, or importer-owned payloads is disabled or excluded from the
  initial deployment.
- Prefer filex trash/quarantine or a reviewable staging area over irreversible
  deletion. If filex cannot provide an adequate recoverable-delete boundary,
  deletion remains unavailable and the existing guarded commands remain the
  only removal path.
- A cross-host move is accepted only after destination existence, size, and
  hash or equivalent transfer verification are recorded; the source is then
  removed only when it is disposable and the operation was explicitly
  authorized.
- The portal must not alter permissions, timestamps, filenames, or directory
  layout of manifest-managed media as a side effect of browsing or copying.

### Acceptance criteria

1. Deploy filex in an isolated service with pinned, reviewable configuration
   and a documented rollback/removal path. Confirm the deployed version,
   license, update source, and current security posture before enabling writes.
2. Confirm the portal is reachable only through the intended private access
   route and that unauthenticated requests, path traversal, shell execution,
   and access outside each configured root are rejected.
3. Browse all three roots and verify that filename, type, byte size, and
   modification date agree with independent host-side listings for a small
   synthetic fixture set. Confirm ascending and descending sorting by size and
   date.
4. Download a fixture from each root and confirm the resulting local file's
   byte count and SHA-256. Confirm folders can be downloaded without exposing
   unrelated sibling paths.
5. Create, rename, and delete only synthetic files in the approved writable
   scratch paths. Confirm the deletion is recoverable or produces a durable
   audit/operation record; confirm canonical and excluded paths reject the
   same actions.
6. Transfer synthetic files in both directions between every permitted pair:
   download host ↔ NAS, download host ↔ Storage Box, and NAS ↔ Storage Box.
   Confirm progress, retry after interruption, destination integrity, source
   preservation on failure, and source removal only after an explicit verified
   move.
7. Run the portal while a real SAB/importer operation is active and confirm it
   does not pause, resume, rename, delete, or lock active application files.
   Check that the existing health and importer-status commands remain healthy.
8. Document the approved roots, credentials/host-key ownership, deletion
   policy, transfer limits, backup treatment, and emergency disable procedure
   in the Usenet operations documentation. Record sanitized acceptance evidence
   without committing real media names, paths, credentials, or hashes.

### Explicit non-goals

This portal does not create a general-purpose cloud drive, synchronize the
whole library, replace Plex or Arr, add NAS-loss protection, expose the portal
outside the private access boundary, or authorize bulk deletion/reorganization
of canonical media. If filex cannot safely provide the required cross-storage
operations, evaluate Filestash as the fallback before considering a custom
frontend; custom code should be limited to our safety/policy integration.

## Operating invariants until cutover

- Keep both SAB free-space floors at `30G`.
- Keep the global SAB queue resumed unless the controller fails closed or a
  live safety check requires a pause.
- Do not manually release queued requests or clear durable holds.
- Do not lower reserves, resize the VM, purchase storage, or delete canonical
  or legacy media to make admission pass.
- Keep acquisition serialized through admission, native import, verification,
  and cleanup before admitting another item.
- Preserve all importer journals, SAB history, activation provenance, and
  disposal receipts.
- Preserve the version-2 hybrid marker, local incomplete spool, remote staging
  mount, shared Arr `/storage` mount, and native hardlink mappings.
- If a timer or controller fails, inspect its durable state and live mounts
  before changing queue state. Do not replay a migration with an existing
  `hybrid-scratch-setup.json` receipt.

## Verification commands

Use the repository-owned read-only checks from the repository root:

```sh
just usenet-cart-import-status
just usenet-cloud-health
just usenet-qnap-health
```

For a sanitized queue/layout/capacity snapshot:

```sh
just usenet-native-cutover-preflight
```

New snapshots remain in unique ignored, mode-0700 directories under
`usenet-infra/build/native-cutover/`; prior evidence stays under
`usenet-infra/build/queue-repair-20260918/`. Do not commit media names,
identifiers, URL hashes, credentials, or raw logs.

## Deployed implementation status

The deployed implementation uses local compressed acquisition scratch, remote
unpack staging, native hardlinks through the shared Arr mount, independent
canonical hashing, and exact cleanup. Same-filesystem bind mounts are validated
through the kernel mount table, with a local fallback where `findmnt` is absent;
both affected test suites pass (**60 tests**).

The hybrid layout and live hardlink probes are complete. The recovered admitted
job's import, verification, and cleanup passed as recorded above. Its next
automatic admission remains untested because there is no eligible request.
This implementation is the rollback baseline for the one-time cutover, not
the target architecture.
