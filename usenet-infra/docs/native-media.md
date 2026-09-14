# Native media workflow

September 11, 2026: native Radarr/Sonarr Completed Download Handling is enabled.
Search and monitored RSS remain enabled; RSS runs every 15 minutes. The old
publisher timer is disabled. Do not re-enable it while Arr owns completed files.

SAB downloads/repairs/unpacks on cloud scratch. Both Arr containers see its actual
`/data/complete` path, then import into `/library`. Radarr's library maps to
`/srv/usenet/library/Movies`, and Sonarr's to `/srv/usenet/library/TV`. The host
mount is the existing Storage Box's `catalog/library` directory over synchronous
SSHFS. Successful native imports enable download-client cleanup. Failed jobs
are retained and automatic redownload remains disabled.

New Default-category cart completions also have an [automatic completion
worker](cart-import.md): native copy import, independent canonical SHA-256, then
exact verified cloud-payload cleanup. Its activation baseline preserves historical
jobs and existing pauses. This is separate from Arr-owned client cleanup.

`usenet-library.service` mounts storage with the existing writer identity and
host pin. `usenet-discovery.service` requires/binds to it; Docker's independent
restart policy is disabled for these two apps so systemd owns startup ordering.
The unmounted directory is root-owned mode 0000. Its application-user write
failure was tested, as was a unique 4,900-byte write followed by independent
Storage Box readback. SSHFS reconnects; it does not queue writeback in a local
rclone cache. If the mount fails, stop/fix that service rather than creating
ordinary directories beneath the failed mountpoint.

Five already published movies were adopted into the native library using
Storage Box server-side hard links, matched to exact Radarr download IDs.
Identical remote device/inode/size was verified for each pair; no media bytes
were recopied and original catalog objects/manifests remain intact. Radarr's
native rescans marked all five as having files. Do not modify the shared bytes
in place; upgrades must replace files normally. The legacy catalog continues
to serve existing objects and verified selective NAS copies.

Plex remains on the QNAP. `Movies (Remote)` and `TV Shows (Remote)` use a
read-only rclone mount at `/share/FromDrobo/Remote/files`, backed by the existing
read-only Storage Box account. It has no listening port. FUSE's mount capability
is confined to this container, with a shared mount bind so Plex can see it.
`Movies & TV` has exactly library IDs 2, 3, 4 and 5; its token still receives
HTTP 403 for private library ID 1. The existing `loljk` paths/count remain intact.

The remote mount has a 20 GiB cache target, 100 GiB free-space reserve and 24-hour
cache age. These are cache eviction targets, not hard quotas on open files.
Fast fingerprints avoid reading an entire SFTP movie to hash it on every open;
this read-only playback cache uses size/modtime checks. Existing canonical
publication and NAS copy verification retain their SHA-256 checks. Do not impose
a small SFTP connection limit on a mount: rclone documents the deadlock risk.
[Fingerprinting](https://rclone.org/commands/rclone_mount/#fingerprinting),
[SFTP connection limits](https://rclone.org/sftp/#sftp-connections).

Local Plex libraries remain available for selected permanent NAS copies.
OliveTin is the transitional copy/removal interface for both legacy catalog objects
and native-library titles. Arr owns imports and Plex owns discovery. Newly imported
native titles are available through remote Plex and can be selected explicitly
for a NAS copy. Native Plex hourly scanning is the
fallback for remote mounts, whose filesystem events are not reliable.

Plex indexed all five remote movies, and a 1 MiB HTTP range stream passed after
the fingerprint/connection corrections. Choose a NAS or Remote library explicitly on the TV. Client cold-start privacy,
codec/transcode behavior and sustained Apple TV/Roku playback still require a
real device test. A successful filesystem or short range read alone does not
prove those capabilities. Plex PIN setup remains private user/device work.

## Selective native-library NAS copies

The full QNAP application deployment passed and installed the native-copy backend,
mounts and dashboard integration. Plex library ID 3 has been narrowed to
`TV Shows/library` after confirming its old root contained no series. The selected
media-002 native copy passed SHA-256 publication, safe repeat, automatic NAS Plex
indexing and Downloads graph/reconnect/phase acceptance. The
[live receipt](../recovery/drills/native-copy-live-20260913.json) records the evidence.

The native-copy backend discovers titles under canonical `library/Movies` and
`library/TV`; it does not require legacy publication manifests. OliveTin combines
these titles with the legacy catalog and supplies an explicit per-title action.
Stable IDs include the library kind and exact title directory, so a stale card
cannot select another title by list position. Movie and TV destinations remain
separate, and staging stays outside Plex sources.

Transfers use the NAS's existing server-enforced read-only Storage Box account
and the same cache lock as legacy operations. Capacity admission reserves the
configured free-space floor. Only a selected title receives SHA-256 verification;
background listing reads metadata without hashing the collection. Verification
checks the selected source before and after copying, then publishes by an atomic
no-overwrite rename. Existing unrelated destinations and changed source files
must be investigated rather than overwritten. A repeat checks the prior verified
copy; retries may reuse safe staged files. New imports and later TV episodes are
not automatically copied to the NAS.

The deployed TV layout uses `/share/FromDrobo/TV Shows/library/<series>` for
published titles and `/share/FromDrobo/TV Shows/.staging` for transfers. Both
are within one container bind mount, allowing atomic renames. Movie staging
remains `Movies/.staging`, beside the existing `Movies/video` Plex source.
Matching filesystem device numbers alone are insufficient across distinct
container bind mounts.

TV copies default to disabled (`qnap_native_tv_copy_enabled: false`) for new or
restored deployments. During this rollout, only Plex library ID 3's source changed
from `/share/CACHEDEV2_DATA/FromDrobo/TV Shows` to its `library` child. The old root
was checked for existing series first, and all other stable library fields and
roots were verified unchanged. Private inventory now sets
`qnap_native_tv_copy_enabled: true`; the follow-up deployment passed and the
running dashboard confirms the gate is enabled, with `NATIVE_TV_ROOT=/data/tv/library`
and `NATIVE_TV_STAGING_ROOT=/data/tv/.staging`. No TV transfer has been accepted live.

For recovery, preserve the narrowed source before enabling the TV gate. If an older
root contains series outside `library`, stop for a preservation review instead of
moving files automatically. Keep library IDs, profile grants and disabled automatic
trash emptying intact. Retain the old source for rollback, and disable TV transfers
before restoring a Plex source that includes staging. The backend refuses TV
copies while the gate is disabled.

These controls wrap native [rclone copy](https://rclone.org/commands/rclone_copy/)
and [structured listing](https://rclone.org/commands/rclone_lsjson/).
`--checksum` alone can fall back to size when a hash is unavailable; the native
backend requires usable SHA-256 evidence before publication.
[SFTP hash support](https://rclone.org/sftp/#hashes).

Plex continues to own discovery through local watches/partial scans and the hourly
fallback. Copy verification and indexing do not establish TV playback or profile
startup privacy; those device tests remain deferred at the user's request.

The NAS backup allowlist now includes `state/native-items` ownership and integrity
receipts. The separate backup-helper deployment through `ansible/qnap-backups.yml`
has passed, and the deployed helper SHA-256 matches source. Independent verification
of `qnap-20260913T041100Z.tar.age` confirmed 56 configuration files, no media, and
the exact native ownership receipt; see the
[archive receipt](../recovery/drills/native-receipt-backup-20260913.json). This does
not establish restoration onto another destination. Presentation-only refresh
does not install the backend or mounts. Restoring a receipt does not authorize adopting
unrelated NAS files: ownership checks still require the recorded directory identity
and verified bytes. A different/rebuilt volume requires deliberate recovery review.

The selected media-002 title is one of the five previously adopted movies. Its
native copy was started through the authenticated dashboard at
`2026-09-13T03:43:06Z`, published after verification at `03:56:01Z`, and
automatically indexed by Plex at the `03:57:17Z` check. Repeating `just native-pull`
verified the existing copy without recopying; directory identity and hashes stayed
unchanged. This copy cannot establish a fresh Arr completion or scratch cleanup.
Automatic Arr-owned movie/TV completion and cleanup, a real TV-series NAS copy,
and device playback/seeking/startup privacy remain unverified.

September 14: the user-selected Default-category cart movie media-004
completed download/unpack and a deliberate native Radarr copy import. Its
15,090,939,776 bytes matched independent source/Storage Box SHA-256, Plex indexed
the exact file in Movies (Remote) after one selected-directory scan, and only the
verified new scratch file/empty parent were reclaimed. SAB history and older
scratch stayed intact. See the [import receipt](../recovery/drills/cart-native-import-20260914.json)
and [Plex receipt](../recovery/drills/cart-plex-discovery-20260914.json).
The native library now has six movies; media-004 is remote-only and unmonitored in
Radarr. This establishes deliberate cart import, not automatic Arr-owned client
cleanup, automatic Plex discovery, a NAS copy of media-004 or device playback.
Automatic Arr-owned movie/TV completion and real TV copying remain outstanding.
