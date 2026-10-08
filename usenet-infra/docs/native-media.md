# Native media workflow

Seerr accepts explicit requests using Plex sign-in. Radarr and Sonarr search
through Prowlarr, submit to their own SAB categories, import to the Storage Box
and remove completed source downloads. RSS polling, direct carts, watchlist
acquisition, automatic upgrades and automatic failed-release retries stay off.
The user accepted native Arr cleanup; it does not perform the retired importer's
independent SHA-256-before-delete gate. Failed jobs remain for explicit review.

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
incomplete/completed reserves, pause during postprocessing, top-only downloads,
safe postprocessing and disabled direct unpack. Arr retains hardlinks and a
30 GiB import reserve. Wait for cleanup before submitting another large release.
These controls do not guarantee arbitrary archive expansion is safe.

Five existing catalog objects have hard-linked native adoptions. Preserve their
manifests and receipts; never edit shared bytes in place. Native upgrades replace
files. The publisher and cart/admission/maintenance workers remain disabled;
there is no second importer or mover for Arr scratch.

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
