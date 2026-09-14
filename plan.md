# Usenet status and closure plan

Implementation was deployed and closed September 13, 2026; the native
movie-copy workflow is accepted. The remaining work is operational acceptance;
source integration into `master` is conditional on a later merge request.
User direction: **no PRs**. [PR #117](https://github.com/rtimmons/smarthome/pull/117)
was closed without merging on September 13. Do not reopen it or create a replacement.
The branch and local work remain preserved; no default-branch merge was requested.

September 14 continuation (UTC): parallel audits refreshed live acceptance from
local `usenet` head `06bfff4`. Initial discovery, cloud and NAS health passed;
SAB was idle, the native library had five movies and no TV, and no fresh movie,
TV or cart completion was present. The accepted native movie remained local
and NAS pulls were idle with no failures. See the dated pre-acquisition
[media acceptance receipt](usenet-infra/recovery/drills/media-acceptance-20260914.json).
The user then selected the two current cart items. media-004, the held setup
item, was individually released at 01:04:40 UTC and completed download and
postprocessing at 01:06:10 UTC. Its native manual import completed at 01:12:24;
independent full SHA-256 matched all 15,090,939,776 bytes. Plex indexed the exact
file in Movies (Remote), ID 4, after one selected-directory scan. Only that new
verified scratch file and its empty parent were reclaimed; SAB history and the
four older scratch files were preserved. This passes deliberate cart completion,
import, verification and reclamation, not automatic Arr-owned client cleanup.
[Acquisition](usenet-infra/recovery/drills/cart-acquisition-20260914.json),
[native import and cleanup](usenet-infra/recovery/drills/cart-native-import-20260914.json),
[Plex discovery](usenet-infra/recovery/drills/cart-plex-discovery-20260914.json).
Normal feed polling queued media-006, about 61 GB; it was paused
individually at 0% because it exceeds scratch admission while preserving the
reserve. Keep it paused pending the user's smaller-release/defer choice. Global
SAB pause and feed settings are unchanged. Do not force-read or release all feeds.
Actual TV selection/copy and device playback/startup checks remain outstanding.

The [external dashboard probe](usenet-infra/recovery/drills/nas-exposure-20260914.json)
passed for the current public TCP/1337 path: three external timeouts, a successful
same-WAN NAS TCP control, no dashboard UPnP mapping, and no global NAS IPv6.
Alternate static forwards or proxies were not audited. The
[queue disposition investigation](usenet-infra/recovery/drills/queue-disposition-20260914.json)
matched all five stale Radarr entries to cleaned legacy publisher receipts and
present canonical files. Retain their visible tracking and both archived scratch
groups: the media scratch has no established canonical match, and a supported
undo for Radarr's persistent ignore action was not found. Investigation and the
retention decision are complete; destructive cleanup is not required for closure.

This continuation's documentation and receipts are committed locally on `usenet`
at the user's request. Existing lighting changes and `msg` remain uncommitted;
branches and stashes remain preserved. No PR, merge,
push or deployment is part of this continuation. The September 13 checks below
remain dated implementation evidence, not tests rerun against a new branch head.

September 13 continuation (16:26 UTC): the nine SAB warnings are reconciled as
historical notices (six hostname blocks, one unpack notice, two disk-space
warnings). The four retained scratch files match two archived completed SAB jobs:
the old diagnostic fixture and an earlier media download. Preserve them; this
matching does not verify a canonical copy or establish deletion readiness.
The five old Radarr entries have canonical files but remain `importPending`;
their original SAB completed paths are absent. No fresh completion occurred.
[Audit and validation receipt](usenet-infra/recovery/drills/queue-reconciliation-20260913.json).
Root tests and seven add-on container checks passed in the existing checkout;
Usenet functional/syntax checks and current-source/index scanning passed. The
full Usenet recipe still fails only on the two documented historical keys.
At the audit, remote `master` was `58318cf`, an ancestor of the implementation and
documentation checkpoint `1113982`. This session's handoff commit follows that
checkpoint on `usenet`; it is local only, with no push or merge performed.
Whole-diff review and final approval are required only if a merge is later requested.

## Cold session start

1. Read this plan, [the Usenet agent guide](usenet-infra/AGENTS.md), and the
   [validation ledger](usenet-infra/docs/validation.md). Inspect `git status`,
   the current branch and recent commits before editing. The expected branch is
   `usenet`; the September 13 handoff and September 14 audit documents/receipts
   are committed locally. Unrelated lighting edits and `msg` remain uncommitted.
   Do not stage unrelated work with Usenet work.
2. For resumed operations, refresh read-only state with
   `just usenet-discovery-health`, `just usenet-cloud-health`,
   `just usenet-qnap-health`, and `just native-status`. The last audit found SAB
   idle with only media-006 individually paused at 0%, zero active/failed NAS
   pulls, six native movies and no native TV title. media-004 is remote-only and
   unmonitored in Radarr; do not reacquire or replay its accepted cart import.
   These are dated observations, not assurances about a later session.
3. Check whether a new user-selected movie, TV or cart job is available. If so,
   follow the acceptance rows below through import, cleanup and Plex discovery;
   a TV NAS copy requires an actually available selected title. Do not submit
   diagnostic media, replay the accepted movie copy, or release held cart items
   to manufacture evidence. Default-category cart jobs need deliberate import.
4. Preserve the September 14 retention disposition for the five stale Radarr
   entries and two archived scratch groups. Recheck evidence before any later
   correction; identifying ownership did not establish deletion readiness.
   Repeat the scoped external dashboard probe after relevant network changes;
   do not expand its result into a complete static-NAT/proxy audit.
   Client playback/startup checks remain user-deferred until device interaction
   is available. No PR or merge task is scheduled by this handoff.

No active acquisition, native import, NAS copy or deployment remains. media-006
is deliberately paused pending a capacity/release decision; do not resume it
or mark its acquisition passed. Post-cleanup canonical SHA-256 and preservation
checks passed at 01:16:15 UTC; all agent read helpers and sub-agents have stopped.
Affected-service health, receipt JSON, documentation links, whitespace and
current-source/index secret scanning passed. No implementation source changed,
so the full test suites were not rerun; their September 13 results and historical
secret-scan limits remain recorded below.
[Continuation checks](usenet-infra/recovery/drills/post-cart-health-20260914.json).
Scheduled backups and existing acquisition/feed schedules continue on their
hosts. No recurring agent automation was created. The durable
[reconciliation receipt](usenet-infra/recovery/drills/queue-reconciliation-20260913.json)
records sanitized findings and checks; its earlier `pr_draft` observation predates
the user's closure instruction. Ignored `build/` logs and one-off read helpers are
supplemental evidence, not prerequisites for resuming. Use the committed recipes
and recovery runbooks if private inputs must be restored.

## Current system

| Use | Entry point / behavior |
| --- | --- |
| Choose movies and TV | [Radarr](http://10.77.0.1:19696/radarr/) / [Sonarr](http://10.77.0.1:19696/sonarr/). Native search/RSS and completed imports are enabled. |
| Phone discovery | NZBGeek **My Cart** feeds [cloud SAB](http://10.77.0.1:18080/) every 15 minutes. media-004's deliberate native import passed; oversized media-006 remains individually paused. Direct cart jobs use Default category and need separate library import; they are not automatically Arr-owned. [Playbook](usenet-infra/docs/nzbgeek-cart.md). |
| Make a title local | [NAS dashboard](http://192.168.1.66:1337/). Choose the Native library action for canonical Movies/TV; transfer phase, rate, progress and history are visible. [Runbook](usenet-infra/docs/native-media.md). |
| Watch | QNAP Plex, using **Movies & TV** and explicit NAS or Remote libraries. The profile has only IDs 2/3/4/5; private library ID 1 is denied. [Layout and client setup](usenet-infra/docs/nas-plex-layout.md). |
| Recover | [Secrets/state](usenet-infra/docs/secrets-recovery.md), [checkout recovery](usenet-infra/docs/checkout-recovery.md), [scheduled backups](usenet-infra/docs/scheduled-backups.md). These cover configuration/state, not whole-NAS loss. |
| Costs | [Dated cost ledger](usenet-infra/docs/costs.md). Infrastructure and NZBGeek total $24.09/month equivalent; Eweka actual terms and NZBFinder charge/currency remain unverified. No purchase is pending. |

Read [the agent guide](usenet-infra/AGENTS.md) before operations. Use the dedicated
identities and host pins in private inputs; never print credentials. Configuration
inspection is not a reason to deploy or restart services.

## Accepted scope

| Capability | Evidence |
| --- | --- |
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

## Outstanding acceptance

These are explicit follow-ups, not a reason to replay setup or broaden the branch.

| Item | Owner / completion evidence | Effect on closure |
| --- | --- | --- |
| Automatic Arr-owned movie and TV completion | Agent observes the next user-selected Arr-owned jobs through import, automatic client cleanup, scratch reclamation, canonical persistence and Plex discovery. media-004's manual Default-category cart import and five old importPending entries do not establish that automatic path. | Required for full automatic media-workflow acceptance; tracked follow-up may remain after source merge. |
| Real TV selective copy | Agent copies an actually available user-selected TV title; verify staging isolation, hashes, publication and Plex indexing. | Required for TV-copy acceptance; not proved by layout or movie copying. |
| Phone-cart completion/import | media-004 passed real acquisition, deliberate native import, independent integrity verification, Plex discovery and exact-job reclamation. Oversized media-006 remains paused at 0% pending a smaller-release/capacity decision. | Deliberate cart workflow accepted for media-004. The second selected item is pending; automatic Arr ownership is not implied. |
| Existing queue/scratch disposition | September 14 investigation matched five stale entries to legacy cleanup receipts and current canonical metadata. Deliberately retain visible tracking and both scratch groups; archived media lacks an established canonical match, and fixture metadata alone is insufficient for deletion. [Receipt](usenet-infra/recovery/drills/queue-disposition-20260914.json). | Investigation and retention decision complete. Any later persistent ignore or destructive cleanup requires its own deliberate disposition; no blanket healthy-queue claim. |
| Apple TV/Roku playback and startup privacy | Ryan supplies device interaction: restricted-profile cold start, NAS/Remote playback, seeking and relevant audio/subtitles. Owner PIN remains private. | Explicitly deferred by user; not a source-merge blocker and not marked passed. |
| External NAS exposure check | September 14 direct TCP/1337 probe passed from the cloud with current-WAN correlation and a successful NAS TCP control; no dashboard UPnP mapping or global NAS IPv6. [Receipt](usenet-infra/recovery/drills/nas-exposure-20260914.json). | Dated direct-port acceptance complete. Alternate static forwarding/proxy paths remain unaudited; repeat after network changes. |

NAS-loss protection, whole-machine replacement/reboot drills, additional providers,
portals, LAN HTTPS and further capacity purchases are separate projects. Billing
uncertainties stay in the cost ledger and do not reopen account setup.

## Closure and merge criteria

**Implementation closure** means the deployed scope above has durable receipts,
the new native receipt is captured in a verified backup, operational follow-ups
remain explicit, and no authorized transfer/deployment or shared-agent edit is
left running. It does not mean client tests or a fresh import were observed.

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
   history, or call the full scan green.
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

Remote tracking is refreshed. Three fully merged local refs were removed:
`codex/docs-sonos-replacement-plan`, `codex/sonos-partial-availability`, and
`two-line-labels`. Their commits remain in published `master`. Eight registrations
for already missing worktrees were pruned; no existing worktree was removed.

| Retained branch | Disposition |
| --- | --- |
| `usenet` | Deployed implementation closed; PR #117 closed at user request. No PR workflow. Branch preserved; merge not requested. |
| `ml/blinds-only` | Three unique commits; retain for its own scope/review, do not bulk merge. |
| `mobile` | Five unique commits, including unfinished responsive/editor work; retain. |
| `nuheat-integration` | Eight unique commits; retain its integration/recovery context. |
| `wall-to-favicon--tetris-controller` | Four unique commits for a separate feature; retain. |

The four other feature branches include unpublished commits and require their own
review/publication before deletion. Both existing worktrees contain unrelated
lighting changes; the main checkout also has `msg`. All five stashes remain.
These are preserved work, not abandoned Usenet tasks or permission to deploy HA.

For routine status, use `just usenet-discovery-health`, `just usenet-cloud-health`,
`just usenet-qnap-health`, `just native-status`, and the dashboard. Current detailed
procedures and evidence live in linked runbooks; superseded planning is in Git.
