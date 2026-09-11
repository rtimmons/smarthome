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

Choose a NAS or Remote library explicitly on the TV. Client cold-start privacy,
codec/transcode behavior and sustained Apple TV/Roku playback still require a
real device test. A successful filesystem or short range read alone does not
prove those capabilities. Plex PIN setup remains private user/device work.
