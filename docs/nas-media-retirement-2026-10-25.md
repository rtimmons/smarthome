# QNAP media-app retirement receipt — October 25, 2026

Video Station 5.8.9 and Multimedia Console 2.11.2 were removed through QTS App
Center in Safari after encrypted preservation. No unexpected dependent app was
named. The [migration plan](plan-nas-storage-and-access.md#legacy-share-retirement-and-system-label)
owns remaining share cleanup; this receipt is not an active execution plan.

## Preservation and recovery

Ignored durable evidence is under
`usenet-infra/backups/qnap-media-retirement-20261025/`.
`qnap-media-retirement-20261025.tar.gz.age` and its private manifest retain the
stopped applications' settings/databases and original paths: 1,841 regular files,
291,575,875 uncompressed bytes, 44,545,241 encrypted bytes. Decryption, every-file
read and durable-copy checksum verification passed. Keep the existing dedicated
NAS administrator recovery recipient/key and this archive unchanged.

This was archive verification, not a live app restore. Recovery needs matching
official packages and selected saved state; do not replace the entire current
package registry or unrelated File Station database. Reinstallable binaries were
excluded. The archive was preserved off-NAS on the controller; no new B2 copy
was claimed. The detailed removal chronology remains in Git history.

## Result and remaining boundary

Plex's identity endpoint, retained container health and NAS backup freshness
checks passed after removal. HBS, Plex, File Station and Container Station stayed
enabled. File Station root browsing passed; private download/media-preview and
client playback were not qualified by this check.

Shares and SMB configuration were unchanged. **Multimedia still exists and should
be retired** through supported QTS controls after checking its remaining sample/
system metadata and dependencies. Public, homes and Container have separate
platform/ownership requirements; do not delete them as part of app retirement.
No scrub, account change or data migration was performed. Disk-2 concerns remain
in the [storage readiness record](nas-preflight-2026-10-25.md). Check after future
QTS/package updates that retired apps or broad default-share grants have not
returned.
