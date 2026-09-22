# Usenet integration plan

Housekeeping: September 23, 2026. Operational evidence below is from September 22;
this documentation cleanup is not a fresh live-health audit. The native cutover,
Seerr deployment, Filex rollout and bounded capacity acceptance are complete.
Detailed dated records are preserved in the [plan history](usenet-infra/docs/plan-history-20260922.md).

## Remaining work and explicit deferrals

These four items are the open work. Completed checks are listed separately below.

| Remaining item | Next action | Dependency / completion condition |
| --- | --- | --- |
| Filex browser access | Establish verified browser access within the existing host trust policy. | Host trust-policy changes are prohibited. Do not install the private CA, retry trust prompts or bypass certificate validation. Explicit-CA diagnostic HTTPS passes; ordinary browser acceptance remains unverified. |
| Seerr browser sign-in | Confirm Plex sign-in and browsing in the normal browser. | User confirmation is pending because the embedded-browser sign-in did not advance. The actual request/download/import test already passed. |
| Replacement-server startup drill | Recheck the prepared plan and current prices, then execute, verify startup and remove temporary resources. | Awaiting the proposed **USD 1 ceiling**. No temporary resources exist. Follow the [reviewed drill](usenet-infra/docs/replacement-drill-20260922.md); isolated archive restoration does not establish replacement-host startup. |
| NAS-loss protection | Choose settings-only or encrypted originals plus settings, then implement recurring off-host coverage and verify recovery. | Scope answer is pending. The one-time NAS/Plex settings checkpoint passes; recurring NAS off-host replication and original-file protection remain open. Settings-only coverage would leave originals unprotected. |

A pending answer is not approval. No new purchases, trust changes, media requests,
private-library inspection, or production restoration are implied by housekeeping.

## Completed and verified

The [September 22 closure receipt](usenet-infra/recovery/drills/closure-20260922.json)
records the final follow-up evidence.

| Completed work | Evidence and limits |
| --- | --- |
| Native Arr cutover and application updates | Fresh movie/episode imports, completed-source cleanup, Plex discovery, restart/mount guards and reviewed image updates passed. See [native cutover](usenet-infra/docs/native-cutover.md) and [maintenance receipt](usenet-infra/recovery/drills/app-maintenance-20260922.json). |
| Old held-download disposition | Three paused zero-progress requests discarded; 14 failure records for seven journals resolved. All 44 journals and historical holds remain preserved. Recorded payloads were already absent, so this reclaimed no payload bytes. |
| Selected TV NAS copy | Destination SHA-256, atomic publication, safe repeat and exact-file general Plex indexing passed; a forced general-library scan was needed. |
| Roku and Apple TV | User confirmed playback and restricted privacy on both; no agent-run codec/subtitle matrix is claimed. |
| Seerr 4K request | Download, native import, source cleanup, general Plex indexing and Seerr availability passed. An eligible 2160p alternate was manually selected after the first release was unrepairable. This does not prove browser sign-in or automatic recovery from failed releases. |
| Filex recovery | Encrypted daily server capture, operator bootstrap escrow and NAS SFTP settings coverage deployed. Independent restores and off-host readback passed. See [Filex recovery](usenet-infra/docs/filex-recovery.md). |
| Final cloud checkpoint | `cloud-20260922T215403Z.tar.age` independently restored 752 files, five application databases, all 44 journals and both nested Filex bundles. Separate NAS/Plex settings archives also passed the one-time off-host checkpoint. |
| Bounded capacity | Earlier 80 GiB PAR2 repair plus two concurrent 50 GiB expansions passed. The latter retained 100 GiB of input allocation, peaked at 200.22 GiB and left 90.97 GiB free. Synthetic files were removed; arbitrary expansion remains outside proven limits. See [repair spool](usenet-infra/docs/repair-spool.md). |
| Final service checks | Cloud, NAS, native ownership, discovery, Filex and Seerr checks passed September 22. Historical holds remain informational; active catalog failures were zero. |

Latest implementation validation ran **708 cases, nine optional skips, no test
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
2. Choose an open item above and check its dependency. Read the relevant runbook;
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
