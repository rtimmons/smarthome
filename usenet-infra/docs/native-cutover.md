# Arr ownership cutover

The September 20, 2026 cutover is accepted and active. A fresh movie and a fresh
TV episode passed native acquisition, canonical import and completed-source
cleanup. Plex discovered the movie automatically and the episode after a general
remote TV library scan. An 80 GiB synthetic PAR2 reconstruction passed independent
SHA-256 with both full copies present, and a scoped SAB/Arr restart preserved
ownership, limits, pauses, historical state and the legacy-worker guards.
See the [sanitized receipt](../recovery/drills/native-cutover-20260920.json).

The user accepted native Arr import and cleanup for new requests, replacing the
independent SHA-256-before-source-unlink gate. Historical verification receipts
remain unchanged. This policy does not claim native cleanup provides that gate's
guarantee. The first selected episode had three distinct missing-article failures,
all with zero downloaded payload; their failed records remain intact and that
selection is unmonitored. A replacement random episode completed acceptance.

## Request and storage policy

- Start requests in Radarr or Sonarr through add-and-search or explicit search.
  Select only the desired movie or episode scope. Separate SAB categories
  `radarr` and `sonarr` preserve each application's ownership.
- RSS polling stays off to preserve seven pre-existing monitored missing movies.
  Prowlarr supplies indexers, with its direct download client disabled. Both old
  cart feeds and the three admission/import/incomplete-maintenance timers are
  disabled. Their journals, processed-feed history and held records are retained.
- SAB keeps a 100 GiB release limit, top-of-queue downloading, pause during
  postprocessing, safe postprocessing, direct unpack off and both `30G` floors.
  Both Arr applications retain hardlinks, free-space checks and 30 GiB import
  reserves. Completed removal is enabled; failed removal and automatic retries
  are disabled, including retries after interactive searches.
- Wait for import and cleanup before submitting another large request. The
  planning envelope allows 100 GiB unpacked output, a full repair replacement
  and remote import-copy fallback. These controls and tests do not establish
  arbitrary archive expansion or broad concurrency. Conservative limits remain.
- The [approved expansion](storage-expansion-20260920.md) supplies BX21 (5 TiB)
  remote storage and a separate 300 GB [repair volume](repair-spool.md), while
  retaining the CX43 VM. The catalog increase is $32.01/month. Preserve private
  inputs `storage_box_type = "bx21"` and `repair_spool_enabled = true` after
  restoring older snapshots. Do not reapply purchase plans or reformat the volume.

## Inspection and evidence

From the repository root:

```sh
just usenet-native-ownership-status
just usenet-native-cutover-preflight
just usenet-cloud-health
just usenet-discovery-health
just usenet-qnap-health
```

`config/catalog/native-ownership.json` is root-owned and has phase `active`.
Systemd conditions and direct helper guards prevent retired workers from touching
native jobs. Legacy cart deployment and the old discovery configurator refuse
this marker. `just usenet-configure-native-ownership` refreshes helpers and checks
an existing deployment; it does not replay acceptance grabs or restart services.

The preflight is read-only. Its `cutover_performed: false` describes that capture,
not the live deployment. `native_ownership_phase` and
`prior_acceptance_evidence_recorded` report the saved acceptance state. Only an
allowlisted summary reaches the terminal; private snapshots are mode 0600 in a
unique mode-0700 directory under ignored `build/native-cutover/`. Never print or
commit them: they include media identities, paths and application credentials.
The initial [pre-expansion preflight](../recovery/drills/native-cutover-preflight-20260920.json)
remains a historical record of insufficient capacity and hybrid ownership.

Private root-owned, backup-readable receipts under `state/catalog/` include
`native-cutover.json` (original settings/fingerprints), `native-acceptance.json`
(exact selected identities and import/cleanup/Plex proof), `native-large-repair.json`
and `native-restart.json`. Local private evidence is in ignored
`build/storage-expansion-20260920/`. The final check preserved the original three
paused requests, all 44 journal hashes, 37 completed journals, 27 importer holds,
ten capacity holds, activation and original SAB history. No old hold was released
and no completed historical title was reacquired for acceptance.

## Interruption and rollback

Do not replay a grab with an uncertain response. Reconcile exact download IDs
against the owning Arr history and SAB before deciding whether another request
is necessary. Preserve failed payloads and failed history for explicit review.

Before rollback, stop further explicit requests, preserve the current global
and per-job pauses, and reconcile every native job with its Arr owner. Only at a
verified idle boundary may saved app policies, feed flags and systemd drop-ins
be restored from `native-cutover.json` and the private baseline. Restore client
categories/cleanup, RSS and Prowlarr direct-client settings as a coordinated
operation; never simply remove the native marker or start a retired worker over
native scratch. Restore only the recorded prior timer/feed states after checking
capacity and source ownership. Keep journals, holds, receipts and all payloads.
No bulk release, history replay, canonical deletion or library migration is part
of rollback. Repair-volume rollback has its own phase-specific runbook.

The 14 historical catalog failure records remain visible and unwaived. The
September 22 [application maintenance](app-maintenance-20260921.md) resolved the
update notices and independently restored the post-update configuration archive;
NAS health passes. Device playback, selective TV copying to NAS, Filex recovery,
NAS-loss protection and whole-machine replacement remain separate work. Indexing
proves discovery, not playback. See the [current plan](../../plan.md) for the
remaining work and the dated recovery evidence.
