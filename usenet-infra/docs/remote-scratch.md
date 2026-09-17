# Remote acquisition staging

The `configure-remote-scratch` recipe places new download/repair/unpack work on
the existing Storage Box. The VM remains CX43 with its existing 160 GB disk;
this change purchases no resources. The library remains canonical, and native
Radarr/Sonarr import still owns publication.

The backing directory is `catalog/library/.acquisition-staging`, outside Movies,
TV and all Plex sources. Two systemd bind mounts expose it:

| Host path | Use |
| --- | --- |
| `/srv/usenet/downloads/incomplete` | Staging `incomplete`; SAB keeps its existing `/data/incomplete` path and queued job identities. |
| `/srv/usenet/downloads/complete/remote` | Staging root; SAB completes into `/data/complete/remote/complete`. |

Old completed scratch stays at its original local paths. The initial incomplete
tree must contain only bounded `__ADMIN__` metadata, with no payloads or links.
While SAB is stopped, every metadata file is copied and SHA-256 checked; the
original directory is renamed locally to `incomplete-local-before-remote`, never
deleted. The original SAB configuration is also retained. The private setup
receipt records queue identities and migration phases. Existing paused requests
must survive with the same IDs, sizes, remaining bytes and categories.

Both unmounted fallback directories are root-owned mode 0000. SAB's Docker restart
policy becomes `no`; `usenet-sab-remote.service` starts it after both mounts exist.
SAB and the native applications stop when the staging mounts disappear. Their
startup recreates the containers so stale bind mounts cannot survive a remount.
The capacity guard still runs during mount loss and pauses SAB when reachable.
The NAS, Plex and Prowlarr lifecycle is unchanged.

An explicit `config/catalog/remote-scratch.json` activates remote capacity
accounting. The controller checks both mounts, common backing filesystem, SAB
paths, available inodes and 30 GiB reserves on both the local application disk
and remote staging. It admits one job through cleanup. The remote estimate is
the larger of remaining archive plus 1.25 times release size, or two expanded
copies at 1.25 times size each, plus 5 GiB. Both staging and canonical copies
consume the same Storage Box budget. This remains a conservative polling estimate,
not a hard quota or protection against arbitrary archive expansion.

Before a new cart admission, read-only native parse/catalog lookup holds ambiguous
identities before downloading their payloads. Arr-owned requests retain native
ownership. Transient lookup/API failures fail closed; they are not classified as
permanent identity holds. Existing identity-held requests remain visible and are
not guessed, discarded or repeatedly downloaded.

The importer independently hashes the source and canonical file before cleanup.
SSHFS rejects exclusive rename, so remote staging uses a durable unlink intent:
verify canonical bytes, check exact source and canonical signatures, persist the
intent, recheck identity/signatures, then unlink only that source. Recovery from
an interrupted unlink re-verifies the canonical file and requires the recorded
intent before accepting source absence. Local jobs retain the existing quarantine
protocol. Unimported sidecars and identity-held payloads remain separate from
successful-import cleanup; they still consume actual available capacity.

## Deployment and recovery

Run `just --justfile usenet-infra/Justfile --working-directory usenet-infra
configure-remote-scratch` after reviewing the current plan. The playbook installs
tested controller/importer code, then requires no active transfer or native
command and every queued request paused at zero progress. It preserves the global
pause, moves only verified metadata, changes SAB's completed path while stopped,
checks the same queued requests after restart, and enables normal automation.
A failed migration leaves its explicit phase and original files for review;
do not rerun it blindly or reset the receipt. It does not move media to make an
active transfer pass preflight.

Cloud encrypted backups include the marker, setup receipt, helpers and Compose
override. Systemd mount/dependency units remain reproducible from this repository.
Restore the mount configuration before starting SAB with a restored remote marker;
never start it against an unmounted fallback. Original private bound snapshots
remain immutable.

Rollback is a maintenance operation: first drain/stop admission and reconcile any
active import. Stop SAB/native applications, preserve any new remote progress,
and unmount incomplete then remote-complete. Restore the original incomplete
folder only after checking that no new request depends on remote metadata;
never overwrite new progress with the initial metadata snapshot. Restore the
original SAB path and lifecycle only after accounting for remote completed jobs.
Do not remove remote staging data until each exact job has been reconciled.

The initial queued advertised sizes total more than current Storage Box free
space. Some include parity/repair bytes, so this is not an exact final-library
forecast. Remote staging fixes local scratch exhaustion; it does not grant
unlimited permanent library capacity. Admission will stop again if the shared
remote reserve cannot cover the next job and its final copy.
