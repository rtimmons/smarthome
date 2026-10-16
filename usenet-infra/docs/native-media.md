# Native media workflow

Seerr accepts explicit requests using Plex sign-in. Radarr and Sonarr search
through Prowlarr, submit to their own SAB categories, import to the Storage Box
and remove completed source downloads. RSS polling, direct carts, watchlist
acquisition and automatic upgrades stay off. Automatic requests (including
Seerr) use Arr's native failed-download blocklisting and replacement search.
Failures from manually selected interactive-search releases do not trigger
automatic replacement. This is a failure-triggered policy, not a repair timer.
The user accepted native Arr cleanup; it does not perform the retired importer's
independent SHA-256-before-delete gate. Failed jobs remain for explicit review.
Their payloads are not automatically deleted, even when Arr selects a replacement;
retained failures can consume repair-spool space. Apply the retry policy with
`just usenet-configure-failed-downloads`; it updates both apps without a restart
or explicit search command. Already processed historical failures are not replayed
by this helper. Pending failures can be handled on the next normal Arr poll.

Sonarr's **Rename Episodes** setting is enabled for future imports as of October
16. Its existing naming formats are retained; standard episodes include the
series, season/episode number, episode title and quality. This gives Plex a
readable filename after Sonarr has matched an import. Enabling the setting does
not rename existing files or initiate downloads. The change preserved all 435
existing Sonarr file records and queue/acquisition settings, with no rename or
search commands. Keep `renameEpisodes: true` in Sonarr's saved naming settings
when restoring configuration. Any repair of existing filenames remains a
separate, explicitly scoped native operation. Recovery remains report-only.

## Storage and startup

The cloud host is CX43. A 300 GB repair volume holds incomplete downloads;
completed files live under the BX21 Storage Box's
`catalog/library/.acquisition-staging/complete`. The synchronous SSHFS library
mount is `/srv/usenet/library`. Arr sees this common filesystem at `/storage`,
with `/library` pointing to its Movies or TV subtree. SAB's completed path maps
through `/data/complete/remote/complete`; the saved Arr path mapping resolves
that to `/storage/.acquisition-staging/complete` for hardlink imports.

The mount and service definitions are described in [repair storage](repair-spool.md).
Systemd owns startup ordering. Unmounted directories are root-owned mode 0000;
never create ordinary writable folders underneath failed mounts. SSHFS reconnects
without a local writeback cache. Preserve SAB's 100 GiB release limit, 30 GiB
incomplete/completed reserves, concurrent downloading during postprocessing, top-only downloads,
safe postprocessing and disabled direct unpack. Arr retains hardlinks and a
30 GiB import reserve. Wait for cleanup before submitting another large release.
These controls do not guarantee arbitrary archive expansion is safe.

The October 15 processing policy uses `par_option: -T4` to allow four files to
be hashed in parallel. This is a tuning trial, not a measured speedup; repair
calculation keeps the tool's default CPU-thread selection. Apply with
`just usenet-configure-post-processing` after current postprocessing finishes.
The command refuses active postprocessing, persists only these two settings,
verifies the unchanged reserves and disabled direct unpack, and never resumes
a manual pause. The ownership health check detects drift from this policy.
Concurrent downloads can fill the repair spool behind slow processing; the
30 GiB reserve pauses intake but does not reserve every repair's expansion space.

Five existing catalog objects have hard-linked native adoptions. Preserve their
manifests and receipts; never edit shared bytes in place. Native upgrades replace
files. The publisher and cart/admission/maintenance workers remain disabled;
there is no second importer or mover for Arr scratch.

## Buffered completed-file copies

The repository builds `smarthome/sabnzbd:5.1.3-buffered-v1` from the exact
LinuxServer 5.1.3 image digest. A build-time source-hash guard refuses an
unreviewed SAB filesystem module. The adapter is scoped to SAB's filesystem
module and regular files moving from `/data/incomplete` into
`/data/complete/remote/complete`; global Python copy behavior stays unchanged.
It retains rename-first behavior and metadata, uses 1 MiB buffered writes, and
requires flush, fsync and close before source removal. Both SAB copy attempts
use the adapter. The SSHFS mount remains synchronous.

October 15 isolated tests of the actual SAB move routine measured 41.00 MiB/s
with the original code and 93.24 MiB/s with buffering (two 1 GiB trials each).
All four uploads passed independent SFTP SHA-256 readback. These tmpfs-source
synthetic tests do not establish real repair, unpack or import speed. Thirteen
image integration tests cover copy failures, metadata, renames, collisions,
symlinks and source preservation; additional deployment tests cover integrity,
idle gating and rollback.

Use `just usenet-sab-buffered-build` to build and test without restarting SAB.
`just usenet-sab-buffered-deploy` refuses queued downloads, any postprocessing,
active Arr commands, missing mounts, low reserves or stale/unverified backups.
It retains a rollback tag and checksummed image archive under
`/srv/usenet/images/sab-buffered`, with the original Compose definition. A brief
maintenance pause prevents intake during the guarded SAB/Arr restart; the prior
pause state is restored. A failed candidate restores the original image.
The existing override that sets SAB's Docker restart policy to `no` is preserved
and checked by its effective configuration and checksum; other override changes
require review. Systemd continues to own mount-dependent startup.
The dedicated rollout stages the live Compose definition with only SAB's image,
pull policy and health check replaced, preserving unrelated runtime settings.
Configuration checks retain the exact saved-settings checksum and complete API
fingerprint, normalizing only SAB's boolean-versus-integer representation of
`pause_on_post_processing` and `start_paused` across startup.
SAB's prior pause state is restored before that comparison because its temporary
maintenance pause changes `start_paused`; Arr remains stopped until the exact
saved settings and API configuration pass, then its prior service state returns.
When SAB preserves pauses, the helper saves the original pause flag through its
supported API after resuming its own maintenance pause; resuming alone updates
only memory. The original saved-file checksum must still match exactly.
`just usenet-sab-buffered-rollback` performs the same idle checks and restores
the retained image/configuration. It does not move media or change storage.

`just usenet-sab-buffered-status` reports deployment state.
`just usenet-sab-buffered-verify-import` tracks the next naturally requested
Arr-owned SAB job by its ID, checks successful SAB completion, matching Arr
import events and nonempty canonical files, then confirms native source cleanup.
It never enqueues a release or retries/deletes a job. Exact IDs remain in the
private deployment receipt; output contains only status and counts. Image
health checks verify the installed adapter and patched-source hashes.

## Plex and selective NAS copies

Plex reads canonical media through the NAS's server-enforced read-only Storage
Box account. The playback mount has a 20 GiB cache target, 100 GiB free-space
reserve and 24-hour cache age. These are eviction targets, not hard quotas on
open files. Fast fingerprints avoid collection-wide hashing during listing.
See [NAS layout and profile privacy](nas-plex-layout.md).

OliveTin offers explicit per-title NAS copies for both native titles and existing
catalog objects. Native IDs bind the media kind and exact directory; a stale
card cannot select another item by position. Copies share a cache lock, reserve
free space, check SHA-256 on the selected files, verify the source did not change,
and publish with an atomic no-overwrite rename. A repeat verifies the existing
copy; retries can reuse verified staged files. Existing unrelated destinations
are never adopted or overwritten. There is no whole-library sync.

Movie copies publish under `Movies/video/native-<id>/<title>` with staging in
`Movies/.staging`. TV uses `TV Shows/library/<series>` and `TV Shows/.staging`
in the same bind mount. Private inventory enables `qnap_native_tv_copy_enabled`;
keep it disabled if Plex's TV source includes staging. New episodes are not
automatically copied. Local eviction removes only an owned NAS copy.

Plex owns discovery through watches, partial scans and an hourly fallback.
Remote mounts may need a general-library scan; copying alone does not prove
indexing. Ownership receipts under `state/native-items` are included in NAS
settings backups. A rebuilt destination still requires integrity/ownership
review before those receipts can authorize eviction.

See [validation](validation.md) for accepted cases and their limits, and
[operations](operations.md) for commands.

## Seerr recovery reporting

`just usenet-configure-seerr-recovery` installs a separate five-minute report-only
service and the Home Assistant notification package. It checks native ownership,
validates HA configuration, reloads automations, runs one report, then enables the
timer. It does not restart media services. Private HA setup uses the repository's
dedicated SSH identity; authentication failure requires the human-only key-copy
repair, with no alternate credential fallback.

Only approved/completed single-copy Seerr requests with exact server, native ID
and TVDB/TMDB bindings are included. TV scope is the explicit approved seasons;
unrequested seasons and pending, declined, blocked or deleted requests cannot
propose acquisition. Existing file records are excluded even when their disk
verification fails: that inconsistency needs review, never a replacement search.
The report distinguishes native files from Seerr availability; it does not prove
Plex indexing or playback. An availability lag lasting 15 minutes raises a finding.

Completed jobs take precedence over replacements. After 15 minutes, one-to-one
embedded series, season, episode and episode-title matches can propose a native
manual import. A narrowly recognized resolution/source/codec suffix is permitted
in embedded titles. Only the two filename-identity rejection categories can be
resolved by this match; other native blockers remain held. Conflicting, absent or duplicate metadata, existing-file overlap,
extras/bonus-only releases, and unrelated native rejection reasons remain held.
Bounded metadata reads never scan whole media files. Active/unknown jobs and
unlinked completed downloads hold searches. Remaining proposals name individual
missing episodes and list existing episodes to exclude from overlapping packs.
Historical completed requests with missing files need review before reacquisition.
Stale Seerr Plex scans (over 20 minutes), mount, reserve, manual-pause,
native-health and post-processing gates suppress all
proposals. Incomplete API reads fail closed.

**There is no recovery executor or apply switch.** Search, grab, import, delete,
rename and acquisition-setting writes are absent. The only remote write is a
Home Assistant notification. Unsuitable-release classification is evaluated in
reports; live release restrictions, retry budgets and automated recovery remain
for a later reviewed promotion. That promotion must revalidate scope, library,
queue and release overlap immediately before any native action and enforce a
persistent bounded retry budget. Native Arr handling remains unchanged.

`just usenet-seerr-recovery-status` returns a sanitized summary and report age.
`just usenet-seerr-recovery-run` requests an extra report through the same locked
service. Exact evidence lives in mode-0600 `snapshot.json` and `report.json` under
`/srv/usenet/config/catalog/seerr-recovery` (mode 0700), covered by configuration
backups. No requester emails or media identifiers are sent to HA or stdout.

Home Assistant keeps one persistent recovery notification, updates it only when
findings change, and dismisses it when clear. Quiet heartbeats allow HA to warn
when the monitor has been silent for 20 minutes. Failed deliveries are retried;
no notification success is recorded on an HTTP error. The cloud receives only an
opaque webhook secret, not an HA API token. TCP 8123 is permitted only to the
configured HA LAN host through the existing IPsec policy; there is no new public
listener. Ordinary VPN redeploys preserve the installed destination.

The installer preserves HA's other secrets, backs up its owned package and
secrets file, and restores them if configuration validation fails. Local ignored
`usenet-infra/secrets/seerr-recovery/notify.json` and HA's ignored `secrets.yaml`
retain the token for redeploy. Keep those aligned on restore; the installer
refuses token rotation. Reinstall the service/HA package after rebuilding a host.
To suspend reporting, stop and disable `usenet-seerr-recovery.timer` and disable
`automation.usenet_recovery_watchdog` in HA; native media processing continues.
