# Current validation and acceptance

Updated September 13, 2026 (UTC). This ledger records accepted behavior and its
limits. The [current plan](../../plan.md) owns remaining work and the
[closure and merge criteria](../../plan.md#closure-and-merge-criteria). Historical
implementation narratives remain in Git and dated receipts; they are not current
operating instructions. Recovery receipts and bound snapshots remain unchanged.

## Accepted behavior

| Area | Evidence and limit |
| --- | --- |
| Native selective movie copy | [Live receipt](../recovery/drills/native-copy-live-20260913.json): the selected media-002 native title, 14,878,405,826 bytes, passed source/local SHA-256 verification and exclusive publication at 03:56:01 UTC. A safe repeat succeeded at 03:58:59 UTC with unchanged directory identity, signatures and hashes, without recopying. This was an adopted movie, not a fresh Arr completion. |
| Plex discovery and privacy | The same receipt records automatic discovery of the expected native NAS file in Movies (NAS), ID 2, rating key 5633. The managed profile sees exactly IDs 2/3/4/5 and receives HTTP 403 for private ID 1; home/global-search exclusion and disabled automatic trash emptying were verified. Indexing and server grants do not establish playback or safe client startup. |
| Native backend and TV layout | Full application and backup-helper deployments passed; five installed script hashes matched source. ID 3 now scans `TV Shows/library`; TV staging is a sibling within the same bind, and the runtime gate is enabled. The previous TV root had no series. No actual TV transfer has been tested. |
| Live download visibility | The [live receipt](../recovery/drills/native-copy-live-20260913.json) records changing bytes/rate/ETA, graph samples, transfer/history persistence through browser closure and reopen, and verification/completed states without a stale live rate. See [download status](download-status.md) for cadence and per-attempt limits. |
| Arr native-import configuration | [Preflight](../recovery/drills/native-rollout-preflight-20260913.json) verified automatic acquisition/import settings, the active mount-dependent services, and the disabled publisher. Five adopted movies have files. Configuration and adoption do not prove a fresh import or scratch cleanup. |
| Remote Plex access | The [native-media record](native-media.md) documents indexing of the five remote movies and a successful 1 MiB HTTP 206 range read through the read-only mount. Sustained device playback remains untested. |
| Phone cart configuration | [NZBGeek Cart](nzbgeek-cart.md) is enabled in SAB at a 15-minute interval. Its native reader verified the initial held entry; queues stayed empty and no acquisition was started during setup. Direct cart jobs do not establish Arr import ownership. |
| Secrets/state recovery | [Published clean-clone receipt](../recovery/drills/20260911T194408Z.json): 24 vault entries, 15 bundle entries and six keypairs verified; repeated restoration added zero files. The existing master and bound snapshots remain unchanged. |
| Checkout preservation | [Checkout receipt](../recovery/drills/checkout-20260911.json): 1,319 local files, Git refs/reflog history and five stashes preserved and independently restored. Readiness passed at the recorded published revision; recheck current work before any later deletion. |
| Scheduled configuration backups | [Archive verification receipt](../recovery/drills/scheduled-backups-20260911.json): cloud/QNAP/Plex archives fetched and verified using independently recovered identities; Plex SQLite snapshots opened successfully. Schedules run on the hosts. This is not a full Plex startup or NAS replacement drill. |
| Native receipt backup capture | [Independent archive verification](../recovery/drills/native-receipt-backup-20260913.json): `qnap-20260913T041100Z.tar.age` passed `qnap-config` validation with 56 files and no media. Its 1,357-byte native ownership receipt matched the expected SHA-256. This verifies capture and archive integrity, not a restore onto another NAS or destination. |
| Provider and legacy NAS baseline | [QNAP bootstrap](qnap-bootstrap.md) records the official provider fixture's verified legacy copy/removal, authenticated dashboard behavior, CLI parity, restart persistence and isolated configuration-startup restore. These earlier checks do not replace native-import or device acceptance. |

## Remaining evidence

| Status | Work and completion evidence |
| --- | --- |
| Pending: fresh movie import | Observe the next user-selected Arr-owned completion: import event, persistent canonical file, completed-client removal, scratch reclamation and Plex discovery. Do not acquire a diagnostic title merely to fill this row. |
| Pending: fresh TV import and copy | Observe a user-selected series/episode through native import and cleanup, then verify one selective NAS copy, correct TV-library indexing and safe repeat. No canonical TV titles were present at the recorded preflight. |
| Reconciled; disposition pending: old completions | The [September 13 audit](../recovery/drills/queue-reconciliation-20260913.json) matched all four scratch files (17,253,186,699 bytes) to two archived completed SAB jobs: the official fixture and an earlier media download. The five old Radarr `importPending` entries each have a canonical file, but their original SAB completed paths are absent. Preserve both scratch groups and history; path ownership alone does not verify a canonical copy or authorize deletion. No fresh import was observed. |
| Pending: cart acquisition | Verify a future user-selected cart job and its intended library-import route. The setup's held initial entry is not a completed download; avoid queueing all held entries inadvertently. |
| User-deferred: Apple TV/Roku | NAS and Remote playback, seeking, sustained playback, codec/audio/subtitle behavior, and cold-start/home/search privacy with the restricted profile. Do not invent or request publication of the owner's PIN. |
| Pending: external NAS exposure | A permitted external probe or independent firewall/NAT audit must verify the dashboard is unreachable publicly. LAN binding and authentication passed; external exposure acceptance remains qualified. |
| Separate: recovery scope | NAS-loss protection, whole-machine replacement and full cloud reboot/Plex package-startup drills remain separate. Revisit only within the scope and authorization set by the current plan. |

These rows do not independently define a merge blocker or authorize a merge.
Use the plan's closure criteria to distinguish required work from explicitly
accepted deferrals. Account bootstrap, optional fill providers and repeating an
already accepted NAS movie transfer are not default next tasks.

## Recorded implementation checks

Wrap-up health on September 13 verified discovery/import configuration, provider
connectivity, scratch and NAS reserve, fresh dashboard data, and zero active or
failed NAS pulls. The accepted movie remains local. SAB reported nine warnings;
their private reconciliation was pending at that checkpoint alongside the old Arr/scratch entries.
No queue was cleared or resumed to change that result.

The 16:26 UTC continuation reconciled all nine SAB notices: six hostname blocks
and one unpack notice dated September 10, plus two disk-space warnings dated
September 11. All are warning severity; SAB is idle with an empty queue and
86,470,455,296 scratch bytes free against the 32,212,254,720-byte reserve. The
warnings remain in history. Sonarr's normal queue and history are empty; requesting
unknown shared-client items exposes old SAB movie records and must not be treated
as Sonarr ownership. NAS health reports zero active/failed pulls and the accepted
native movie is still local. See the [reconciliation receipt](../recovery/drills/queue-reconciliation-20260913.json).

Fresh root `just test` completed successfully, including 118 Talos tests and all
seven add-on container build checks. The run used the existing checkout with
unrelated lighting edits preserved; it is not isolated clean-head validation of
those dirty generator files. The Usenet rerun again passed 457 cases with nine
opt-in skips and all syntax checks, then failed only on the two historical keys.
Current-source/index scanning passed. At the audit, remote `master` was `58318cf`,
an ancestor of checkpoint `1113982`; whole-diff review and final approval remain
required if a merge is later requested.
The user subsequently directed no PRs: PR #117 was closed without merging, and
the current plan supersedes the receipt's earlier draft-PR status.
Session closure commits the handoff and sanitized reconciliation receipt locally.
No push, merge, deployment or cleanup accompanies that documentation commit.
Resume through the plan's [cold session start](../../plan.md#cold-session-start).

The latest `just usenet-test` run recorded **466 Usenet cases: 457 passed and
nine opt-in skips**. Compilation, shell/YAML checks, generated deployment-shell
checks, and Ansible syntax validation passed. Current-source/index secret
scanning passed. The full recipe remained nonzero because it detected the two
[documented historical RSA keys](security-findings.md); no exemptions or history
rewrite were used.

[Native source validation](../recovery/drills/native-copy-source-20260912.json)
records 28 Linux cases plus a real rclone 1.75.1 smoke using tiny generated movie
and TV fixtures. [Telemetry validation](../recovery/drills/download-status-20260913.json)
records real subprocess/lock tests and the opt-in real-rclone check. These local
checks have no production credentials or network and are distinct from the live
acceptance receipt. Root functional tests and all seven add-on container checks
passed for the native implementation checkpoint; counts are dated evidence,
not promises about a later checkout.

Run current checks after implementation changes, from the repository root:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra test
just --justfile usenet-infra/Justfile --working-directory usenet-infra --command ./scripts/secret-scan --no-history
```

Use the [agent guide](../AGENTS.md) for live access and preservation rules.
Record new acceptance in a dated, sanitized receipt and update this ledger and
current plan together. Do not expose tokens, personalized feed URLs, private
library contents or recovery secrets in evidence.
