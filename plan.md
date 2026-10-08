# Usenet integration plan

Updated October 8, 2026. All four remaining follow-ups are complete within the
user-approved scope. The native cutover, Seerr, Filex, recurring settings backups
and isolated replacement-server startup are verified. Detailed dated records are
preserved in the [plan history](usenet-infra/docs/plan-history-20260922.md) and
[October 8 closure receipt](usenet-infra/recovery/drills/closure-20261008.json).

## Remaining work and explicit deferrals

No implementation or acceptance work remains from the approved plan.

| Follow-up | Completed evidence and limits |
| --- | --- |
| Filex browser access | User confirmed sign-in and browsing at `http://127.0.0.1:15213/`. Run `just usenet-filex-ui` and keep its encrypted SSH tunnel running. No domain, trust-policy change or TLS bypass. The truncated local credential file was corrected and encrypted escrow refreshed. |
| Seerr browser sign-in | User confirmed normal-browser sign-in and browsing. The earlier actual request/download/import test also passed. |
| Replacement-server startup drill | Approved under USD 1; authenticated services, reboot startup, storage-loss stop/refusal and retired-worker guards passed. All disposable resources and their IPv4 allocation were removed and independently checked absent. Used empty read-only library fixtures, with no NAS/VPN or live acquisition. See [drill scope](usenet-infra/docs/replacement-drill-20260922.md). |
| NAS-loss protection | User selected settings only. Recurring encrypted off-host QNAP/Plex settings backups now require successful upload and independent ciphertext readback. Independent restore passed for 66 QNAP files and three Plex files. Original media, artwork and a replacement NAS/Plex boot test are outside this chosen scope. |

Whole-NAS recovery, original-file protection and expansion beyond the measured
capacity envelope are explicit limits, not unfinished approved tasks. No further
purchase, media request, private-library inspection or production restoration is
implied by plan completion.

## Completed and verified

The [September 22 closure receipt](usenet-infra/recovery/drills/closure-20260922.json)
records the earlier operational evidence; the October 8 receipt closes its follow-ups.

| Completed work | Evidence and limits |
| --- | --- |
| Native Arr cutover and application updates | Fresh movie/episode imports, completed-source cleanup, Plex discovery, restart/mount guards and reviewed image updates passed. See [native cutover](usenet-infra/docs/native-cutover.md) and [maintenance receipt](usenet-infra/recovery/drills/app-maintenance-20260922.json). |
| Old held-download disposition | Three paused zero-progress requests discarded; 14 failure records for seven journals resolved. All 44 journals and historical holds remain preserved. Recorded payloads were already absent, so this reclaimed no payload bytes. |
| Selected TV NAS copy | Destination SHA-256, atomic publication, safe repeat and exact-file general Plex indexing passed; a forced general-library scan was needed. |
| Roku and Apple TV | User confirmed playback and restricted privacy on both; no agent-run codec/subtitle matrix is claimed. |
| Seerr 4K request | Download, native import, source cleanup, general Plex indexing and Seerr availability passed. An eligible 2160p alternate was manually selected after the first release was unrepairable. Browser sign-in was separately confirmed October 8; automatic recovery from failed releases is not proven. |
| Filex recovery | Encrypted daily server capture, operator bootstrap escrow and NAS SFTP settings coverage deployed. Independent restores and off-host readback passed. See [Filex recovery](usenet-infra/docs/filex-recovery.md). |
| Final cloud checkpoint | `cloud-20261008T192037Z.tar.age` independently restored 785 files, five application databases, all 44 journals and both nested Filex bundles, including corrected operator login escrow. NAS/Plex settings also have recurring off-host readback and independent restore. |
| Bounded capacity | Earlier 80 GiB PAR2 repair plus two concurrent 50 GiB expansions passed. The latter retained 100 GiB of input allocation, peaked at 200.22 GiB and left 90.97 GiB free. Synthetic files were removed; arbitrary expansion remains outside proven limits. See [repair spool](usenet-infra/docs/repair-spool.md). |
| Final service checks | Cloud, NAS, native ownership, discovery, Filex and Seerr checks passed October 8. Historical holds remain informational; active catalog failures were zero. |

Latest implementation validation ran **712 cases, nine optional skips, no test
failures**. Syntax and current-source/index scanning passed. Full-history scanning
still flags the two [documented historical RSA keys](usenet-infra/docs/security-findings.md).
This dated result is not a clean bill of health for unrelated checkout changes.

## Current operating policy

- Browse and request through [Seerr](http://10.77.0.1:15055/) using Plex sign-in.
  Ultra-HD profile 5 prefers **2160p with 1080p fallback** for movies and TV.
  Automatic upgrades, RSS polling, watchlist acquisition and direct carts remain off.
- Radarr/Sonarr own imports and completed-source cleanup. Retired publisher,
  cart-import and capacity-admission workers remain inactive; do not replay old
  held requests or re-enable them to satisfy historical acceptance instructions.
- Storage Box is canonical; NAS copies are selective and independently verified.
  Preserve read-only NAS access, separate staging/library roots, mount-dependent
  startup, the 100 GiB release limit, 30 GiB SAB reserves and 100 GiB NAS reserve.
- Preserve original SOPS-bound recovery snapshots, all 44 journals, disposition
  receipts and historical integrity evidence. Do not regenerate credentials or
  repeat account setup/purchases. Do not modify shared hard-linked media in place.
- Preserve private Plex library ID 1 and general-profile grants to IDs 2/3/4/5.
  Do not browse private content. Host trust policy must remain unchanged.
- Use [Filex](usenet-infra/docs/filex.md) only within its approved staging and
  read-only canonical roots. Configuration recovery excludes staging and media.

## Cold session start

1. Read this plan and [the infrastructure guide](usenet-infra/AGENTS.md). Inspect
   Git status; preserve unrelated edits, untracked files, private inputs and `msg`.
2. The approved plan is complete. For new work, read the relevant runbook;
   dated archived instructions are evidence, not a queue of commands to replay.
3. Before live changes, inspect current queue/transfers and service health with
   the repository wrappers and dedicated identities. Preserve active work and
   manual pauses. Do not restart services or enqueue downloads just for an audit.

Read-only checks from the repository root:

```sh
just usenet-native-ownership-status
just usenet-discovery-health
just usenet-cloud-health
just usenet-qnap-health
just usenet-filex-status
just usenet-seerr-status
```

## Closure and merge criteria

Close each remaining item only with its stated evidence and recorded limitations.
Keep archive extraction, replacement-host startup and NAS-originals recovery as
separate claims. Do not treat bounded capacity or user device acceptance as an
unlimited archive-expansion or codec guarantee.

The user requested commits and no PRs. No merge, push, branch deletion or checkout
removal is authorized. If a merge is later requested, review the full branch,
validate the reviewed source, acknowledge the historical key findings and protect
local work before changing refs. Original recovery evidence stays immutable.
