# Current validation and acceptance

Updated September 14, 2026 (UTC). This ledger records accepted behavior and its
limits. The [current plan](../../plan.md) owns remaining work and the
[closure and merge criteria](../../plan.md#closure-and-merge-criteria). Historical
implementation narratives remain in Git and dated receipts; they are not current
operating instructions. Recovery receipts and bound snapshots remain unchanged.

The [September 14 media audit](../recovery/drills/media-acceptance-20260914.json)
refreshed discovery/cloud/NAS health and normal Arr/SAB records at local head
`06bfff4`. Health passed with the same nine historical SAB warnings, zero active
or failed NAS pulls, five native movies and no native TV. SAB was idle;
Radarr's retained history contained no fresh import event, and Sonarr had no
series, queue or history. No fresh movie, TV or cart completion can be accepted
from those baseline records. The existing accepted native movie remained local.
This was a live read-only audit, not a new implementation test run or playback test.
Cloud and NAS backup status receipts were also healthy within their 36-hour
freshness threshold; no new backup or archive-integrity drill was run.

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
| External dashboard direct port | [September 14 probe](../recovery/drills/nas-exposure-20260914.json): three external TCP/1337 timeouts against the independently correlated current home WAN, with a successful same-WAN NAS TCP control. No dashboard UPnP mapping or global NAS IPv6 was found. This passes dated direct-port acceptance; alternate static forwarding/proxy paths were not audited. |
| Phone-cart acquisition | [September 14 acquisition](../recovery/drills/cart-acquisition-20260914.json): user-selected media-004 completed download and postprocessing in Default category. Normal polling queued the other selected item, media-006; it remains individually paused at 0% for capacity disposition. Global pause and feed settings were preserved. Acquisition alone does not prove native import or automatic Arr-owned cleanup. |
| Deliberate native cart import and reclamation | [media-004 import receipt](../recovery/drills/cart-native-import-20260914.json): native manual copy import completed at 01:12:24 UTC, with a `downloadFolderImported` event and no download ID. The 15,090,939,776-byte source matched an independent Storage Box SHA-256. Only its verified scratch file and empty parent were reclaimed; older scratch and SAB history stayed intact. Radarr movie ID 13 is unmonitored, avoiding an extra acquisition. This does not prove automatic Arr-owned client cleanup. |
| New cart movie Plex discovery | [Plex receipt](../recovery/drills/cart-plex-discovery-20260914.json): media-004, Movies (Remote) ID 4, rating key 5638, exact canonical path and size matched. One native scan targeted only this directory; discovery was verified at 01:13:57 UTC. Automatic indexing and real-device playback were not established. |

## Remaining evidence

| Status | Work and completion evidence |
| --- | --- |
| Pending: automatic Arr-owned movie completion | Observe the next user-selected Arr-owned job through import, automatic completed-client removal, scratch reclamation, canonical persistence and Plex discovery. media-004's manual cart import does not establish the automatic path. Do not acquire a diagnostic title merely to fill this row. |
| Pending: fresh TV import and copy | Observe a user-selected series/episode through native import and cleanup, then verify one selective NAS copy, correct TV-library indexing and safe repeat. No canonical TV titles were present at the recorded preflight. |
| Investigated; deliberately retained: old completions | The [September 14 disposition](../recovery/drills/queue-disposition-20260914.json) matched all five stale entries to exact-job legacy cleanup receipts and present canonical files. Retain visible tracking: persistent native ignore lacks an established supported undo. Retain both archived scratch groups (four files, 17,253,186,699 bytes): the media group has no established canonical match, while fixture evidence is historical integrity plus current metadata only. Any later cleanup remains separate; no fresh import is established. |
| Passed for media-004; second cart item pending | media-004's real acquisition, deliberate native import, integrity verification, Plex discovery and exact-job cleanup passed. Oversized media-006 remains paused at 0% pending capacity/release disposition; do not resume or silently replace its release. |
| User-deferred: Apple TV/Roku | NAS and Remote playback, seeking, sustained playback, codec/audio/subtitle behavior, and cold-start/home/search privacy with the restricted profile. Do not invent or request publication of the owner's PIN. |
| Scoped pass: external dashboard | Direct TCP/1337 acceptance passed September 14 as recorded above. A complete alternate-port static-NAT/proxy audit was not performed. Repeat the probe after relevant network changes. |
| Separate: recovery scope | NAS-loss protection, whole-machine replacement and full cloud reboot/Plex package-startup drills remain separate. Revisit only within the scope and authorization set by the current plan. |

These rows do not independently define a merge blocker or authorize a merge.
Use the plan's closure criteria to distinguish required work from explicitly
accepted deferrals. Account bootstrap, optional fill providers and repeating an
already accepted NAS movie transfer are not default next tasks.

## Recorded implementation checks

September 14 continuation: [post-import health](../recovery/drills/post-cart-health-20260914.json)
passed for discovery, cloud and NAS, retaining the nine historical SAB notices.
Native status showed six movies, media-004 remote-only, the accepted media-002 copy
still local, and no TV. The native-import receipt's final check at 01:16:15 UTC
confirmed canonical SHA-256 after cleanup, unchanged older scratch/history and
86,417,821,696 scratch bytes free. media-006 remained individually paused at 0%.
The seven new receipts parse, local documentation links and whitespace pass,
and current-source/index scanning passes (717 source files, 708 index blobs;
history explicitly omitted). This continuation changed documentation/receipts
and performed the recorded live workflow; no implementation code was changed,
so full test suites were not rerun. The September 13 results below remain dated
evidence. The continuation's documentation and receipts are committed locally at
the user's request; unrelated lighting edits and `msg` remain uncommitted. No
push, merge or deployment occurred.

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


## September 14 automatic cart cleanup activation

The user requested automatic canonical movement and cloud cleanup. The new
worker, native adapters, private activation/journals, timer, focused deployment
lock and health reporting were deployed at 01:38:39 UTC. The first scheduled run
was idle and successful. All eleven current/history jobs and two feed entries
were excluded. Exact scratch metadata for 281 files and the sanitized full SAB
snapshot matched before/after; media-006 stayed individually paused, global pause
stayed false, retained history and older payloads were untouched. Installed helper
SHA-256 values match the reviewed source. Cloud/discovery health passed, with only
the nine retained historical SAB warnings. The retired publisher stayed disabled.
[Activation and preservation evidence](../recovery/drills/cart-import-activation-20260914.json).

The full infrastructure run completed 538 cases: 529 passed, nine opt-in skips.
Python compilation, shell/YAML/deployment checks and Ansible syntax passed.
Current-source/index secret scanning passed. Full history scanning remains nonzero
only for the two documented historical RSA keys; no exceptions were introduced.
Independent review drove fixes for exact-file provenance, duplicate-history RSS
provenance, asynchronous TV metadata, durable journals, uncertain submissions,
transient retries and deployment/backup lock coordination. Tests cover verified
cleanup and interruption recovery without production media mutations.

No fresh automatic job was manufactured for acceptance. The next newly selected
eligible cart movie/TV completion still needs native import, independent checksum,
automatic cloud cleanup and Plex indexing evidence. Actual TV NAS copying and
user-deferred playback/privacy checks remain open. Current failed/oversized jobs
are preserved; automatic completion cleanup does not resolve their space demand.
