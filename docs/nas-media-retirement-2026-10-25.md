# QNAP media app retirement — October 25, 2026

Video Station **5.8.9** and Multimedia Console **2.11.2** were removed through
QTS App Center in Safari after the [read-only preflight](nas-preflight-2026-10-25.md).
QTS recorded completion at **18:00:02** and **18:01:14 Eastern**, respectively.
App Center now lists 15 installed packages, and both removed package sections
are absent from the native registry. No additional dependent app was named by
the removal dialogs. Multimedia Console removal received explicit confirmation
at QTS's application-data deletion warning.

## Preservation and recovery

Both apps were stopped first. Before removal, their configuration and database
state was preserved in a local encrypted archive under the Git-ignored
`usenet-infra/backups/qnap-media-retirement-20261025/` directory, which resolves
to the durable controller state outside the checkout. The archive is
`qnap-media-retirement-20261025.tar.gz.age`; its private companion manifest records
file hashes and the original paths. It contains **1,841 regular files**,
291,575,875 uncompressed bytes, and occupies 44,545,241 encrypted bytes.

Encryption uses the existing dedicated NAS administrator recipient. Decryption,
reading every archived file, and the durable copy's SHA-256 readback passed.
Protected database directories were read using the already-installed backup
image in a temporary container with read-only mounts, no network, dropped
capabilities and a read-only root filesystem. The container was removed afterward.
The Multimedia Console database process had stopped before capture. Earlier
incomplete attempts were not accepted as preservation evidence.

The archive includes media-service settings, the protected multimedia databases,
Video Station's application and station state, and package-registry/configuration
references. Multimedia Console's reinstallable binaries were excluded. Recovery
requires the matching official packages and a scoped review of the saved state;
do not replace the entire current package registry or unrelated File Station
database. This was an archive verification, not a live application restore test.
The copy is off the NAS on the controller; no new B2 upload was claimed.

## Retained services and shares

- Plex's local identity endpoint returned HTTP 200 before and after removal.
  Plex, HBS, Container Station and File Station remain enabled.
- The 11 existing long-running containers were running afterward; those with health
  checks reported healthy. The NAS encrypted-backup freshness check passed.
- `just usenet-qnap-health` passed: Storage Box reachable, no catalog failures,
  no active/failed/interrupted NAS pulls, dashboard readiness and refresh healthy,
  and the NAS cache above its free-space reserve.
- HBS showed two successful jobs, none running or failed, and its B2 storage
  available. No new backup or restore was started.
- File Station opened and listed the Multimedia and Usenet roots. Access to the
  private B2 restore-test directory was denied; no permission was widened to
  complete a download test. Media previews, downloads and client playback were
  not qualified by this check.
- The SMB configuration hash matched before and after removal. Public,
  Multimedia, homes, Container, FromDrobo, Usenet and the current Time Machine
  share roots remain present. No share deletion, data migration, ACL edit or
  account change was performed.

## Scrub decision and remaining work

**No RAID scrub or new scrub schedule was started.** The array remained complete,
with zero degraded members, idle synchronization and zero current mismatches.
That does not resolve the recent disk-2 link/I/O errors or establish recovery of
private originals. A short error-free interval after the firmware reboot is not
proof of a repair.

QTS [RAID scrubbing](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/raid-scrubbing-0BE980D3.html)
scans RAID 5/6 sectors and attempts repairs. Given the unresolved connection
fault, defer that additional workload until supported drive/internal-error logs,
the drive/bay/connection path and recovery coverage have been reviewed. Then
schedule a monitored scrub and recurring policy; retain the existing disk-history
evidence. The scrub is not a treatment for a SATA connection problem.

Application retirement completes only that part of phase 5c. Classify the
remaining Multimedia Samples/system metadata before deleting its share; migrate
Ryan's Public files only after qualified private-home and backup coverage. Keep
required Public, homes and Container exceptions. Check after future QTS updates
that retired multimedia apps have not been reintroduced. See the
[remaining migration gates](plan-nas-storage-and-access.md#legacy-share-retirement-and-system-label).
