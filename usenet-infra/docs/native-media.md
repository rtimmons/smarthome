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
OliveTin is the transitional cache interface for existing catalog objects, not
the downloader, new import owner, or Plex scanner. Newly imported native titles
are available through remote Plex; a convenient selective NAS-copy action for
native-library titles remains to be added. Native Plex hourly scanning is the
fallback for remote mounts, whose filesystem events are not reliable.

Plex indexed all five remote movies, and a 1 MiB HTTP range stream passed after
the fingerprint/connection corrections. Choose a NAS or Remote library explicitly on the TV. Client cold-start privacy,
codec/transcode behavior and sustained Apple TV/Roku playback still require a
real device test. A successful filesystem or short range read alone does not
prove those capabilities. Plex PIN setup remains private user/device work.

## Selective native-library NAS copies

This section describes prepared source; the new workflow is not deployed yet.

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

The prepared TV layout uses `/share/FromDrobo/TV Shows/library/<series>` for
published titles and `/share/FromDrobo/TV Shows/.staging` for transfers. Both
are within one container bind mount, allowing atomic renames. Movie staging
remains `Movies/.staging`, beside the existing `Movies/video` Plex source.
Matching filesystem device numbers alone are insufficient across distinct
container bind mounts.

TV copies default to disabled (`qnap_native_tv_copy_enabled: false`); movie copies
can be deployed independently. Before enabling TV copies, inspect Plex library ID 3
and the existing TV root, then
change **only** that library's source from `TV Shows` to `TV Shows/library`.
Require the old root to have no existing series outside the new `library`
subdirectory; otherwise stop for a preservation/migration review. Retain the
before-change source path for rollback, preserve IDs/profile grants, and leave
automatic trash emptying disabled. After verifying the narrowed Plex source, explicitly set
`qnap_native_tv_copy_enabled: true` in private inventory and redeploy. The backend
refuses TV downloads while disabled. Do not enable transfers with Plex still
scanning the parent containing staging. This path migration and live
native-copy acceptance have not yet been performed.

These controls wrap native [rclone copy](https://rclone.org/commands/rclone_copy/)
and [structured listing](https://rclone.org/commands/rclone_lsjson/).
`--checksum` alone can fall back to size when a hash is unavailable; the native
backend requires usable SHA-256 evidence before publication.
[SFTP hash support](https://rclone.org/sftp/#hashes).

Plex continues to own discovery through local watches/partial scans and the hourly
fallback. Copy verification and indexing do not establish TV playback or profile
startup privacy; those device tests remain deferred at the user's request.

The NAS backup allowlist now includes `state/native-items` ownership and integrity
receipts. Deploy the updated `backup-qnap.py` through `ansible/qnap-backups.yml`
as well as the full QNAP application migration; presentation-only refresh does
not install the backend or mounts. Restoring a receipt does not authorize adopting
unrelated NAS files: ownership checks still require the recorded directory identity
and verified bytes. A different/rebuilt volume requires deliberate recovery review.
