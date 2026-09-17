# Automatic cart imports and cloud cleanup

Deployed September 14, 2026 at 01:38:39 UTC. The first scheduled idle run passed;
all 11 historical/current jobs and two feed entries were excluded. The queue and
all 281 existing scratch files were preserved. [Activation receipt](../recovery/drills/cart-import-activation-20260914.json).

The cart completion worker uses Radarr/Sonarr to copy newly completed selections
into the canonical Storage Box library, then independently checks SHA-256 before
removing the corresponding cloud payload. It handles movies and explicitly
numbered standard TV episodes. Arr-owned downloads keep their existing native
Completed Download Handling path. The retired publisher remains disabled.

## What runs automatically

SAB's NZBGeek Cart and NZBFinder Cart feeds poll every 15 minutes. The new
`usenet-cart-import.timer` checks completions every 30 seconds after each worker
run. Only successful, unarchived Default-category jobs with unique exact native
cart provenance and a download timestamp after activation qualify. Feed URLs and
keys never enter worker journals; provenance stores a one-way URL hash.
Activation excludes every current queued/history job and known feed entry,
including paused media-006 and the older completed and failed downloads. It is
idempotent and is never inferred from an empty receipt directory.

The worker matches native parsed identity against a unique catalog title/year,
adds absent titles unmonitored without searching, and asks the native application
to review the exact source candidates. It refuses upgrades, monitored targets,
ambiguous titles, unsupported numbering/disc layouts, unexpected files and
concurrent Arr ownership. Samples, extras and unimported sidecars stay on cloud
storage. A file-valued SAB receipt authorizes only that exact file.

Native `ManualImport` uses copy mode and no download ID. The worker records its
submission intent before making the request. If a response is lost, it recovers
one exact native command or holds for review; it never blindly submits again.
New TV episode metadata receives a bounded readiness wait and can retry later.
Temporary connection failures preserve the journal phase for a guarded retry.

The `usenet-capacity-admission.timer` runs every 20 seconds and owns acquisition
pauses for both cart feeds and the Default/Prowlarr categories. Requests continue
to register with SAB at paused priority. The controller admits one fitting job at
a time and does not admit the next until the current job has left SAB and its
native import/cleanup has reached a terminal state. Its conservative requirement
is remaining download bytes plus 1.25 times the full advertised release size,
plus a 5 GiB margin, while leaving at least 30 GiB application-visible free.
Unknown or oversized requests remain paused.

The controller persists ownership, admission, per-item holds and bounded failure
retry counts under `/srv/usenet/state/catalog/capacity-admission`. It collapses
only exact-filename, zero-progress duplicates and never deletes their payloads.
An importer hold is isolated so unrelated queued work can continue. A failed
controller-owned download has only its exact history-owned payload reclaimed;
SAB's `__ADMIN__` state is retained and native history retry requeues it paused.
After two failed retries it remains held instead of looping forever. Reserve,
concurrency, state-integrity or API failures pause globally and fail closed.
Configuration preserves an admitted history item, and normal runs scan all
nonterminal cart journals before admitting more work. This reconstructs the
import/cleanup boundary after controller restarts or deployments instead of
orphaning completed scratch while the queue continues.

After successful native import, native file/history records must establish exact
ownership. The worker compares each admitted source SHA-256 with an independent
Storage Box server hash and stable metadata. Only verified payload files enter a
private same-filesystem cleanup directory before removal. Crash recovery repeats
canonical verification before further cleanup. Source changes, missing mounts,
collisions or checksum differences preserve remaining bytes and report a hold.
SAB history is retained. Empty job directories are removed when possible.

Plex discovers native libraries through its existing watches and hourly scan.
Automatic cart cleanup does not wait for Plex indexing, which is a separate
acceptance check. NAS copies remain explicitly selected.

## Operation and recovery

From the repository root:

```sh
just usenet-configure-cart-import
just usenet-cart-import-status
just usenet-cloud-health
```

Deployment refreshes only worker/helper files and the importer/capacity timers. It requires
quiet SAB state, the canonical mount and discovery services. It refuses an active
worker or unreconciled processing receipt; code replacement uses the shared
catalog cache lock so backups and imports are protected. File replacement is atomic per helper, not a transaction across the entire bundle;
an interrupted deployment leaves the timer stopped until a clean redeploy. Other
applications and the retired publisher are not restarted. The worker shares that lock with cloud
backups for its entire run; complete activation/journal state is already covered
by the `state/catalog` backup tree. Deployment initializes controller ownership,
leaves every queue entry individually paused and resumes only SAB's global queue.
Later manually paused normal-priority jobs are not adopted or deduplicated; only
new category/feed arrivals carrying SAB's paused priority join controller ownership.

Private state is under `/srv/usenet/state/catalog/cart-import`: `armed.json` holds
the activation baseline, `jobs/<opaque-reference>.json` holds each import receipt,
and `status.json` reports idle, processing, held or failed counts. Armed workers
with missing/stale status fail cloud health; long processing uses the live worker
PID and a six-hour bound. Journals contain filenames but never personalized feed
URLs or credentials. Inspect them privately and publish only sanitized evidence.

A hold needs its exact cause resolved before using `cart-import.py retry <reference>`
as the `usenet` account with `config/catalog.env` loaded and the shared cache lock
(the CLI acquires it). Retry preserves completed phases and never resets activation
or download history. For completed imports with retained sidecars, retry only
recounts those files; after deliberate separate disposition it clears the warning
if none remain. It never deletes sidecars. Do not remove the activation marker,
edit protected IDs, or re-enroll historical jobs to make status green.

To disable new imports, stop/disable `usenet-cart-import.timer`. Allow an active
native command to settle before changing code. An interrupted worker resumes
from its journal after mount/application health returns; a stopped worker does
not cancel an already submitted native Arr command. Do not delete scratch or
quarantine files manually as a recovery shortcut.

## Capacity limits

Completion cleanup and serialized admission prevent a large queue from spending
the same free space concurrently. A request that cannot meet the conservative
peak estimate waits; it is not force-started. Permanently held importer sources
still consume real capacity and can eventually produce an ordinary
`awaiting_capacity_or_known_size` warning. Resolve their private journal cause;
do not lower the reserve or manually resume around it.

The September 16 incident recovery removed an unjournaled failed partial while
preserving its queued selections, and replaced a separate failed payload with one
paused request from exact native provenance. No storage was purchased. The live
controller subsequently resumed a serialized drain with both cart feeds enabled.

Production idle activation and local recovery tests do not prove a fresh live
completion. Record the next user-selected new cart movie/TV job through native
import, independent verification, automatic cleanup and Plex discovery. Do not
re-download accepted media or release oversized jobs to manufacture that evidence.
