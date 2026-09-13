# Usenet status and closure plan

Updated September 13, 2026. Implementation is deployed and the native movie-copy
workflow is accepted. `usenet` remains open for review into `master`; deployment
success does not mean all media/client acceptance or merge gates are complete.
The deployed implementation is closed; review and operational follow-ups remain.
Review: [draft PR #117](https://github.com/rtimmons/smarthome/pull/117).

## Current system

| Use | Entry point / behavior |
| --- | --- |
| Choose movies and TV | [Radarr](http://10.77.0.1:19696/radarr/) / [Sonarr](http://10.77.0.1:19696/sonarr/). Native search/RSS and completed imports are enabled. |
| Phone discovery | NZBGeek **My Cart** feeds [cloud SAB](http://10.77.0.1:18080/) every 15 minutes. Its existing setup item is held. Direct cart jobs use Default category and need separate library import; they are not automatically Arr-owned. [Playbook](usenet-infra/docs/nzbgeek-cart.md). |
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
| Selective NAS movie copy | Batman's 14,878,405,826 bytes passed server/local SHA-256, source-change checks and exclusive publication. Repeat preserved the directory identity and bytes without another download. Plex indexed it automatically. [Live receipt](usenet-infra/recovery/drills/native-copy-live-20260913.json). |
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
| Fresh Arr movie and TV completion | Agent observes the next user-selected jobs: import, client cleanup, scratch reclamation, persistent canonical files and Plex discovery. Five old importPending entries and four retained scratch files are not this evidence. | Required for full media-workflow acceptance; tracked follow-up may remain after source merge. |
| Real TV selective copy | Agent copies an actually available user-selected TV title; verify staging isolation, hashes, publication and Plex indexing. | Required for TV-copy acceptance; not proved by layout or movie copying. |
| Phone-cart completion/import | User selects a new cart job; agent verifies acquisition and the deliberate library-import path. Do not promise automatic Arr handling of Default-category jobs. | Separate operational follow-up; feed configuration alone passed. |
| Existing queue warnings | Agent reconciles SAB's nine reported warnings and the old Arr/scratch entries privately, preserving user pauses and unknown files until ownership is established. | Operational follow-up; no blanket healthy-queue claim or automatic cleanup. |
| Apple TV/Roku playback and startup privacy | Ryan supplies device interaction: restricted-profile cold start, NAS/Remote playback, seeking and relevant audio/subtitles. Owner PIN remains private. | Explicitly deferred by user; not a source-merge blocker and not marked passed. |
| External NAS exposure check | A permitted external probe or independent firewall/NAT audit must confirm the private dashboard is unreachable publicly. LAN binding/authentication are verified; the external probe is not. | Security acceptance remains qualified until verified. |

NAS-loss protection, whole-machine replacement/reboot drills, additional providers,
portals, LAN HTTPS and further capacity purchases are separate projects. Billing
uncertainties stay in the cost ledger and do not reopen account setup.

## Closure and merge criteria

**Implementation closure** means the deployed scope above has durable receipts,
the new native receipt is captured in a verified backup, operational follow-ups
remain explicit, and no authorized transfer/deployment or shared-agent edit is
left running. It does not mean client tests or a fresh import were observed.

**Merge readiness** requires all of the following on the final reviewed PR head:

1. One reviewable `usenet` → `master` PR describes Usenet infrastructure, Plex/NAS
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
   Deferred media/device/security acceptance must remain visible in the PR and
   validation ledger; merge is not a claim that those tests passed.
5. Obtain final review/approval and satisfy any repository-required checks. Keep
   the PR draft while review or required validation remains outstanding. This
   wrap-up defines the gate; it does not execute the default-branch merge.

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
| `usenet` | Deployed implementation closed; draft PR #117 open, then apply the gates above. |
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
