# Download status handoff

Read the current increment in [plan.md](../../plan.md) before operating the NAS.
The Downloads panel at `http://192.168.1.66:1337/` is deployed for both native and
legacy copies. The full native rollout and TV source migration passed September
13 UTC. Batman's native download was started through the authenticated action at
03:43:06 UTC. Changing byte counts, rate, ETA and graph samples were observed in
the rendered UI. SHA-256 publication, safe repeat and automatic NAS Plex indexing
also passed; see the [live receipt](../recovery/drills/native-copy-live-20260913.json).

## Implementation and contract

`catalogctl.Rclone.run` consumes rclone JSON log records while preserving streamed
execution output and nonzero exit handling. The copy calls in `catalogctl.py`
and `native_library.py` enable JSON stats every ten seconds. Their operation
receipt stores only numeric transfer stats: sample time, transferred bytes,
total bytes, rclone-reported speed, optional ETA, and the last 60 samples.
No filename list or raw log object is copied into telemetry. A new pull attempt
creates a new receipt/history; phase changes preserve its samples.

`catalog-dashboard.py` renders active pulls first, or the most recent pull when
idle. It distinguishes copying from preparation, checksum verification, success,
and failure. Unknown/older-than-45-second/future-dated speed samples are not shown
as current speeds. Error snapshots retain context but disable actions. The
`source` field in old cached legacy snapshots is a provenance object; preserve
that compatibility in `item_source` or startup can fail before refreshing.

The graph uses actual timestamps and per-transfer peak scaling, retaining about
ten minutes at the normal cadence. It is not a persistent global network chart.
The browser custom script clears stale displayed rates and retains the existing
interaction-aware refresh policy. Layout styles also travel in authenticated
dashboard data because the unversioned custom script can remain cached. A hard
reload may be needed for updated JavaScript behavior in an existing browser.

## Reproduce validation

From the repository root:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra test
just --justfile usenet-infra/Justfile --working-directory usenet-infra --command ./scripts/secret-scan --no-history
```

The full recipe currently ends nonzero only on the two documented historical RSA
keys; do not waive those findings or describe the full command as green. See
[security findings](security-findings.md). `test_dashboard_deploy.py` also lints
both generated shell modes and runs the actual payload against a local Docker
transport double. The production lease code acquires a real file lock. Tests
cover contention with no script writes, exact rollback bytes, absent/present
native backends, lock ownership during restart, failure cleanup, and assets-only
updates without Docker or cache-lock access. They do not exercise QNAP Docker
lifecycle or a lost SSH connection.

`test_transfer_telemetry.py` exercises actual subprocess output, malformed/nonstats
lines, nonzero exits, and persisted samples through a failed verification phase.
Its optional real-rclone test uses only a generated 1 MiB local file. Set
`CATALOG_TEST_RCLONE` to the installed pinned rclone 1.75.1 binary and run:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra --command python3 -m unittest discover -s tests -p test_transfer_telemetry.py -v
```

The existing local Podman image `localhost/usenet-dashboard-test:3000.19.0` contains
that binary at `/usr/local/bin/rclone`; it was used with no network, read-only
scripts/tests mounts, an ephemeral `/tmp`, dropped capabilities, and no credentials.
Its availability is local convenience, not a clean-clone prerequisite. The test
skips unless explicitly enabled; ordinary tests still cover stream ingestion.
Recorded evidence is in [download-status receipt](../recovery/drills/download-status-20260913.json).

## Deployment and recovery

`just configure-download-status` from `usenet-infra` uses the dedicated pinned
connection from private inputs and updates only the existing script set. It does
not rebuild images, change Compose/environment/authentication/Plex, or install
an absent native backend. Inspect the runtime first; do not redeploy merely to
check status. The helper holds the shared cache lock in an existing-image,
network-disabled container while installing scripts and restarting the dashboard.
A busy cache or unavailable lease fails before script writes. The lease has a
600-second expiry and a shell exit/signal cleanup trap; a lost connection is not
proof cleanup succeeded. Check named `usenet-dashboard-update-*` helpers and the
shared lock before a retry; do not clear a real transfer's lock or kill its process.

The complete update is **not transactional** across files, and failed startup
has no automatic rollback. Script backups are local NAS files under
`state/dashboard-status-backups/<timestamp>`, not a whole-system recovery bundle.
An installation/restart/check failure can leave updated scripts installed and the
UI unavailable. Inspect state/logs and the exact backup before fixing forward or
restoring a compatible script set while idle. A successful file copy or restart
alone is not acceptance: require dashboard refresh/health success and an
authenticated rendered page. The known final rollback set is recorded in the plan;
the earlier `20260913T021208Z` set predates the legacy-cache compatibility fix.

`just configure-download-status assets` atomically replaces only the custom JS
source/runtime files, without a lock or restart. It creates no rollback snapshot;
use Git for the prior asset version. Browser caching can delay its effect.

## Remaining acceptance and limits

- Live acceptance verified the authenticated, full-width panel during the native
  Batman copy: 5.0% / 24.5 MiB/s / three samples, then 11.6% / 25.9 MiB/s / seven
  samples spanning 60 seconds. The screenshot showed a readable graph and progress
  bar. Closing and reopening the tab preserved the running copy and 180 seconds
  of history (31.8%, 23.8 MiB/s). Verification and completion retained the graph
  and displayed no stale live rate; completion showed succeeded and 100%.
- This measures Storage Box → NAS copies. It does not report SAB acquisition,
  repair/unpack, remote-playback-cache traffic, or whole-NAS link utilization.
- Rclone's reported rate is smoothed; ETA and totals belong to the current attempt
  and may change on retries/checks. Bytes reaching 100% do not establish a
  verified copy or Plex discovery. Verification has phase text, not a percent bar.
- Samples are about ten seconds apart; catalog refresh is normally 60 seconds
  plus listing latency, and browser interaction/dialogs/hidden tabs defer reload.
  This is not a ten-second live UI guarantee. Missing data is not measured zero.
- A numeric receipt-write failure follows the existing operation failure path;
  telemetry is not an independent best-effort service. Existing copy verification,
  publication and cache-lock protections still apply.
- The native backend, TV source migration/enablement and backup helper are deployed.
  Actual TV copying, fresh native import,
  new receipt backup capture, device playback/seeking/privacy, and NAS-loss
  recovery remain separate. Follow the current handoff for live acceptance.
