# Current workflow update — September 11, 2026

Native Arr imports now own completion, and the old publisher timer is disabled.
Read [native media](native-media.md) and [scheduled backups](scheduled-backups.md)
for the current mount, backup and playback configuration, and the
[current handoff](../../plan.md) for next tasks. The manual catalog commands below
serve legacy independent objects; they must not move Arr-owned completed files.

# Operations

## Administrative access

Normally use SAB at `http://10.77.0.1:18080/` and Prowlarr/Arr at
`http://10.77.0.1:19696/` through the existing LAN VPN route and proxy. Backend
listeners remain loopback-only. For the optional administrative tunnel, from
`usenet-infra/` use the ignored workstation connection settings:

```sh
just cloud-ui
```

Then use `http://127.0.0.1:8080` and `http://127.0.0.1:9696`. Do not change the
Compose bindings to `0.0.0.0`. Keep the tunnel terminal open; stop it when done.
The repository-root equivalent is `just usenet-cloud-ui`.
Prowlarr's Forms login has been configured privately by the user.

Inspect or reconcile SABnzbd's non-secret settings from the repository root:

```sh
just usenet-sab-settings inspect
just usenet-sab-settings apply
just usenet-sab-provider inspect
just usenet-sab-provider configure
just usenet-sab-provider test
```

The settings helper selects `/data/incomplete` and `/data/complete`, sets a
30 GiB free-space floor for both download and completion, and enables normal
repair/unpack processing. Watched folders and automatic scripts remain disabled;
Arr owns movie/TV imports; legacy catalog promotion is separate. It refuses to change settings while downloads or
post-processing jobs exist, or when custom category workflows/RSS feeds need
review. Every change is read back. The provider helper reconciles only the
existing Eweka server. A fill provider is deferred until actual completion gaps
justify one; see `account-setup.md`. Both helpers keep credentials on the VM and return
only approved settings or sanitized failures. Increase the reserve deliberately
if the largest expected repair/unpack needs more than the initial floor.

NZBGeek is saved and enabled in pinned Prowlarr 2.5.2.5491. Its live
credentialed test passed with global strict certificate validation enabled,
base URL `https://api.nzbgeek.info`, path `/api`, and priority 25. Query/grab
quotas remain unset because daily provider limits are unverified. Inspect or
repeat that test from the repository root:

```sh
just usenet-prowlarr-indexer inspect
just usenet-prowlarr-indexer test
just usenet-prowlarr-indexer enable
```

`enable` tests saved credentials before enabling, verifies readback, and
retests; it is idempotent when already enabled. Output omits the API key.
The optional second argument is `nzbgeek` (default) or `nzbfinder`.
From `usenet-infra/`, use `just prowlarr-indexer` with the same subcommands.
`prepare-disabled` is only for first setup: it creates an empty-key disabled
entry for private user input. Both indexer entries already exist.

NZBFinder Pro is paid and its saved entry is enabled at
`https://nzbfinder.ws` with path `/api`, priority 25, strict certificate
validation, and unset query/grab quotas. Private key entry is complete and
the live credentialed test passed. Its account key is managed under
**My Profile**. Inspect or repeat its test:

```sh
just usenet-prowlarr-indexer inspect nzbfinder
just usenet-prowlarr-indexer enable nzbfinder
just usenet-prowlarr-indexer test nzbfinder
```

Prowlarr now has
exactly one enabled SABnzbd client at `http://sabnzbd:8080` on the private
Docker network. Its `prowlarr` category uses `pp=3`, script `None`, an empty
directory, and normal inherited priority. SABnzbd's host whitelist gained
only `sabnzbd`, preserving all existing entries and hostname checking.
Candidate and saved-credential tests passed, including a standalone retest;
a second configure made no changes. Use these bounded commands from the
repository root:

```sh
just usenet-prowlarr-download-client inspect
just usenet-prowlarr-download-client configure
just usenet-prowlarr-download-client test
```

Credentials stay on the VM. From `usenet-infra/`, use
`just prowlarr-download-client` with the same subcommands. Configuration and
testing do not initiate downloads or searches.
Prowlarr's application API key was rotated through the supported `ResetApiKey`
command without restarting the app. The old key returns HTTP 401, the new key
HTTP 200, and the protected dependent environment is synchronized with its
mode `0640` and owner preserved. Other XML settings were unchanged.
Saved-client and NZBGeek tests also passed after rotation.
The user subsequently enabled Radarr/Sonarr automatic search and RSS globally.
Monitoring selects the titles/episodes eligible for acquisition; quality profiles
select matching releases. Arr imports its successful completed SAB jobs into
the canonical library and enables completed-client cleanup. The transitional
publisher timer is disabled; keep it disabled.

## Native acquisition and legacy manual promotion

For curated movie browsing and TV lookup/calendar, use the deployed
[Radarr/Sonarr interfaces](discovery.md). Both connect to the existing indexers
and SAB with automatic search and 15-minute RSS checks enabled. Completed jobs
are imported by Arr into the mounted Storage Box library. The pages use the catalog login at
`http://10.77.0.1:19696/radarr/` and `http://10.77.0.1:19696/sonarr/`.

To search interactively, keep `just usenet-cloud-ui` running from the repository
root, open Prowlarr at `http://127.0.0.1:9696`, and select **Search**. Enter a
query, select NZBGeek and NZBFinder (or all Usenet indexers), optionally select
a category, and press **Search**. The download icon at the right of a result
sends it to the configured SABnzbd client. Follow its queue and completed
history at `http://127.0.0.1:8080`. This downloads to the cloud VM. A direct
Prowlarr grab does not establish Arr ownership, so do not assume it will be
automatically imported. Prefer Arr for managed movies/TV; review independent
jobs for manual promotion. Subsequent NAS copies remain deliberate selections.
See the [official search guide](https://wiki.servarr.com/prowlarr/search).

The official diagnostic fixture has already passed NNTP downloading,
verification, unpacking, and promotion. Inspect it from the repository root with
`just usenet-sab-smoke-test status`; its durable receipt prevents `start` from
silently creating another job. Canonical item `sabnzbd-official-100mb-2026-09-10`
has passed the NAS dashboard download/reconnection/eviction checks; remaining
acceptance is tracked in the validation ledger.

The following manual promotion procedure remains available for exceptional
imports outside Arr ownership. Do not manually promote an Arr-owned SAB job
or turn the retired publisher back on. Establish ownership before touching scratch.

1. Confirm that the material is authorized and record the basis.
2. Deliberately send the selected NZB to SABnzbd.
3. Wait for local download, PAR verification/repair, and unpack to finish.
4. Review the completed directory and promote it from the workstation:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra catalog-promote \
  /srv/usenet/downloads/complete/ITEM \
  "Human-readable title" \
  other \
  "Indexer or official test source" \
  "Public-domain, freely redistributable, owned, or generated test content"
```

Promotion rejects sources outside the configured completed directory and
rejects symlinks. It calculates SHA-256 for every file, copies to a unique remote
`.incoming` path, downloads/checks the remote bytes, moves the verified tree to
its immutable catalog ID, and publishes the manifest last. Failures leave local
content and recoverable remote staging intact. Local completed content is kept
unless the operator explicitly adds `--delete-local` after a verified publish.

Remote layout:

```text
catalog/
├── .incoming/
├── manifests/<item-id>.json
├── objects/<category>/<item-id>/...
└── library/{Movies,TV}/...     native Arr imports; no legacy manifests
```

After important configuration changes, ensure a fresh verified archive exists.
[Scheduled backups](scheduled-backups.md) run on the cloud and NAS, daily with
hourly retry. The separate `just usenet-backup-cloud` manual capture remains
available when its own idle checks permit; it verifies an archive without
changing the original master-bound recovery inventory. See [recovery](recovery.md)
for that manual format and [scheduled backups](scheduled-backups.md) for current
schedule scope, retention and status. Never alter the SAB queue to force capture.

## Selective QNAP cache

Use the authenticated OliveTin dashboard through the private address/tunnel
recorded during [QNAP bootstrap](qnap-bootstrap.md). The local QTS administration
address and dedicated SSH access are verified. The deployed dashboard is at
`http://192.168.1.66:1337`; runtime, login, download/removal, and restart checks
passed. External reachability verification awaits explicit approval. Repeat
safe metadata discovery from the repository root
with `just usenet-qnap-recon`. The runtime setup and pinned configuration are in
[QNAP Compose](../compose/qnap/README.md).

The prepared native-copy update (not yet deployed) also lists canonical titles
by Movies or TV. These
use a distinct native copy action and do not need legacy catalog manifests.
Choose only the title wanted on the NAS. Copying a TV series selects its current
folder contents; it does not subscribe the NAS to later episodes or upgrades.
See [native copy details](native-media.md#selective-native-library-nas-copies)
for collision handling and verification boundaries.

The normal workflow is:

1. Browse/filter the automatically refreshed catalog by title and category. Inspect the
   remote/local counts and sizes, available NAS capacity, reserve, active
   transfers, and recorded failures. Use the header search for titles/categories
   or the **Entities** table's filter to inspect every state.
2. On a `remote only` card select **Download**. The card supplies the validated
   catalog identity; no copied ID or shell command is required.
3. Follow the running execution and output/history. A running state is meaningful
   even when an exact transfer percentage is unavailable. `local` means the
   backend completed SHA-256 verification and atomic publication.
4. If the operation fails, read its failure/output and fix the reported capacity,
   connectivity, permission, or integrity problem before selecting **Retry**.
   If a previously verified local copy is now damaged, the valid action can be
   **Remove local copy** first, followed by a fresh **Download**. Preserve
   staging for a transfer retry. Closing a browser is not a cancellation
   mechanism; inspect execution status before starting another action.
5. On a `local` item select **Remove local copy** and confirm the message that
   the canonical remote copy remains. After success, refresh to `remote only`.

Catalog data refreshes every 60 seconds while idle, about every 30 seconds
during a pull, on demand, and after each action. The supported custom-JS
extension refreshes an idle visible Catalog page when configuration/entity
events arrive; it avoids active forms and dialogs. Return to **Catalog** from
the execution view. **Logs** shows the initiator, confirmation arguments, status and
output. A refresh failure displays the last snapshot as stale and disables
mutation actions until refresh succeeds.

The deployed movie cache now lives beside the existing private library on
the large data volume. Verified movie pulls appear under Plex's `Movies (NAS)`
source, with Plex-native filesystem watching and an hourly scan fallback.
Use the restricted `Movies & TV` profile. See [NAS/Plex layout](nas-plex-layout.md)
for paths, permissions, client setup, and rollback records.

The current finite action timeout is 30 days. Metadata refresh is separately
bounded at 120 seconds; its timeout terminates the entire metadata process
group. Browser closure leaves the action running. Container shutdown or action
timeout stops the action's process group, and any interrupted item must pass
the usual safe retry path before becoming local.

The same backend is available from `usenet-infra/` on the workstation when the
dashboard is unavailable or for automation:

```sh
just catalog-list
just catalog-status
just catalog-pull "item-id"
just catalog-evict "item-id"
```

For a native-library title, use `just native-list` or `just native-status`, then
`just native-pull "native-<id>"` or `just native-evict "native-<id>"`. Root recipes
have the `usenet-` prefix. Native actions resolve a single exact title; they never
accept a directory to synchronize or access Arr scratch. A changed canonical
version is not silently merged into a prior NAS copy. Native eviction requires
the ownership receipt and unchanged verified bytes; modified or unrelated local
directories remain for manual review. These native commands require the deployment
and TV Plex-source prerequisite described in [native media](native-media.md).

Pull requires enough free bytes for the item plus the configured reserve. It
copies to hidden staging, validates every local SHA-256, then performs a
same-filesystem rename into the cache. A failed or interrupted item never appears
as a complete cached object. Retry the same command safely; hash-verified staged
files are kept, and damaged or unlisted staging remnants are removed before
continuing. One interrupted large file restarts from byte zero.

Pulls and evictions share a persistent operating-system lock. A simultaneous
mutation refuses with an operation-already-running error instead of competing
for staging or capacity. Refresh status, let the active operation finish, then
retry. Read-only status remains available. An abandoned transfer without its
lock becomes `failed`/stalled; it does not stay falsely `downloading` forever.
Rclone emits transfer output every 10 seconds and times out after five minutes
without I/O. Phase messages distinguish copying, verification, and publication.

`catalogctl.py status --json` is the structured summary/item snapshot used by
the dashboard. Its internal states are `remote_only`, `downloading`, `local`,
and `failed`. A normal refresh consults the prior verification record and file
metadata; it does not rehash every cached byte. Every successful pull still
requires full manifest SHA-256 verification before publication.

`RCLONE_BWLIMIT` configures a per-process transfer cap for pulls and promotion;
the default `off` imposes none. A scalar such as `20M` caps bytes per second
using rclone's size suffixes. Adjust `qnap_rclone_bwlimit` in the ignored Ansible
inventory for NAS deployment, and preserve conservative transfers/checkers
until a representative large-file test passes. Do not confuse bytes per second
with the Internet plan's bits per second.

Eviction resolves a local state record and deletes only the root-confined local
object directory. Its implementation never calls rclone. The QNAP's server-side
read-only Storage Box subaccount is the independent backstop against a client
bug.

## Health and failures

```sh
just cloud-health
just qnap-health
```

Cloud health checks Storage Box reachability/capacity, SABnzbd, Prowlarr health
including indexer-reported faults, scratch free space, and recorded promotion
failures. QNAP health checks Storage Box access, cache free space, and recorded
pull failures. Ansible synchronizes the locally generated SABnzbd and Prowlarr
API keys into the protected health environment after starting the applications.
A missing application API key is a warning; a configured but unreachable service
is a failure.

The current cloud health run exits 0: Storage Box, catalog-failure checks,
Prowlarr, and scratch capacity pass. The seven historical SABnzbd warnings were
classified as six setup hostname blocks and one Direct Unpack autotest notice,
with no authentication, provider, or TLS failures. The settings helper restored
`direct_unpack=0` after the one-time autotest, and all settings read back as
intended with no active jobs. The compatibility fix installed the
tested catalog script atomically and updated the health helper without
restarting applications, migrating schema-1 records, or mutating content.

Provider authentication faults are surfaced through SABnzbd's recorded warning
and error API. This is not a fresh NNTP login on every health run: after changing
provider credentials, use SABnzbd's built-in server test and an authorized
transfer. Likewise, a reachable dashboard readiness endpoint does not prove its
authentication policy; exercise anonymous denial and a valid login separately.

Set `STORAGE_WARN_FRACTION=0.80` in the deployed catalog environment. Do not
rely on a compiled/default value: 80% is the approved operator warning. At a
warning:

1. Check catalog objects, `.incoming`, and snapshots for unexpected growth.
2. Confirm current used space and the next tier's authenticated account price.
3. Back up the storage Terraform state and verify independent recovery copies.
4. Before 90% use, change only the desired Storage Box type along the approved
   BX11 -> BX21 -> BX31 -> BX41 ladder.
5. Require the storage plan to show an in-place type update with no replacement,
   deletion, location change, SSH-key change, or protection reduction.
6. Apply deliberately, then verify the Storage Box ID, catalog hashes, QNAP
   read-only access, capacity, and health checks.

Hetzner permits upgrades and permits downgrades only when use is below the
smaller tier's capacity. Snapshots consume capacity and lower tiers have fewer
snapshot slots, so remove or independently preserve excess snapshots before a
downgrade. The provider's type update is in place, but Hetzner does not make an
explicit zero-downtime guarantee for ordinary tier changes. See the official
[scaling rules](https://docs.hetzner.com/storage/general/which-storage-is-right-for-me/),
[snapshot limits](https://docs.hetzner.com/storage/storage-box/snapshots/), and
[hcloud provider 1.68.0 implementation](https://github.com/hetznercloud/terraform-provider-hcloud/blob/v1.68.0/internal/storagebox/resource.go#L432-L447).

Failure records live under the configured catalog state `failures/` directory.
Inspect the corresponding service/container logs and keep the record until the
cause is fixed and the operation has been successfully retried. Successful
retry or eviction marks the relevant history resolved with `resolved_at`;
resolved history is retained while health/dashboard failure counts focus on
unresolved failures and interrupted transfers.

Do not treat a container's `running` state as full health. Confirm the dashboard
login, catalog refresh, and action execution as well as its container health
check. Authentication/access failures and the absence of progress after an
interrupted pull need investigation before another download is started.

## Updates

Review release notes and change pinned versions in Git first. Then:

```sh
just test
just terraform-plan
just configure-cloud
just configure-qnap
just cloud-health
just qnap-health
```

Never use `latest`. Preserve application config backups before upgrades and test
the authorized fixture path after a major SABnzbd, Prowlarr, rclone, Docker, or
catalog-tool or OliveTin update. The playbooks perform Compose reconciliation;
for targeted recovery use the corresponding Compose runbook. Inspect any
Terraform change independently before applying it, especially the protected
Storage Box root. Do not pull a new application version through mutable tags.

## Configuration backups

Current schedules and verified archive receipts are in [scheduled backups](scheduled-backups.md).
The protected configuration includes:

- `/srv/usenet/config/sabnzbd`;
- `/srv/usenet/config/prowlarr`, `radarr` and `sonarr`;
- `/srv/usenet/state/catalog`;
- the QNAP catalog state directory and remote provenance manifests;
- OliveTin authentication/runtime configuration and execution history, plus
  the selected private access/TLS configuration; and
- Plex preferences and its two SQLite databases in the NAS-local schedule; and
- Terraform states, variable files, SSH keys and verified host keys through the
  separate immutable master/checkout snapshots, not the daily application job.

Storage Box snapshots are same-box rollback aids. Cloud configuration ciphertext
is replicated to the NAS; Plex/QNAP configuration stays encrypted on the NAS.
Source is published in Git and recovery keys have the confirmed independent
master chain. NAS-loss protection is explicitly deferred.

For OliveTin, preserve the protected auth JSON and
`QNAP_DASHBOARD_STATE_DIR`, particularly `runtime/sessions.yaml` and
`logs/results` / `logs/output`. The versioned source template is combined with
catalog cards into `runtime/config.yaml`; generated configuration contains
environment placeholders rather than password hashes. The runtime supervisor
suppresses upstream startup debug output and redacts the known hash so it does
not enter operational logs.

Manual `just usenet-backup-cloud` and `just usenet-backup-qnap` captures remain
available alongside the host-owned schedules. Their format, verification and
fresh-directory restore commands are in [recovery](recovery.md). The initial
cloud/QNAP isolated startup drills predate the native media changes; current
scheduled cloud/QNAP/Plex archive verification does not claim full machine or
Plex package-startup restoration. Preserve the matching recoverable identities.

## Authorized end-to-end acceptance test

Use a provider's official test NZB or a small item whose redistribution license
has been independently verified. Record that evidence in the manifest. Execute
and record the [acceptance matrix](validation.md), including the browser workflow,
CLI parity, authentication/exposure, interrupted-transfer recovery, persistent
history, and unchanged remote hashes after local eviction. Local unit tests and
healthy containers alone do not satisfy that matrix.
