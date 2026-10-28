# NAS storage readiness evidence — October 25, 2026

Historical read-only findings still relevant to the [current migration plan](plan-nas-storage-and-access.md).
This is not a second work queue. Full probe chronology and obsolete counters are
in Git history; raw logs and identifiers remain in ignored private evidence.
The user confirmed on October 27 that no later physical repair or UPS/shutdown
qualification had occurred. No later remediation is established here.

## Unresolved storage findings

| Area | Evidence and consequence |
| --- | --- |
| Disk 2 connection path | Current drive replaced August 14; retained logs show 26 `ata2` link resets through October 24, failed reads/writes and October 18/20/23 I/O warnings. A successful short SMART test and QTS “Good” summaries do not clear these faults. Drive, bay/backplane, power and controller cause remains unresolved. |
| Other disks | Retained slot-1 medium/read errors in 2025 and a slot-4 read error during the August 2026 rebuild warrant reconciliation with physical identities. Current drive-internal logs/self-test evidence are incomplete. |
| RAID | One four-member RAID-5 group/pool was complete and idle. No retained completed scrub was found; QTS scrub scheduler was off. Clean membership/current mismatch counters do not establish a completed scrub or repaired SATA path. |
| Snapshots | Main data volume GPvQNAP had only a September 2024 local snapshot with no schedule; Scratch and laptop volumes had none. HBS capture snapshots are not demonstrated retained-volume rollback coverage. |
| Power | UPS support was disabled. Physical UPS, communication, runtime and controlled shutdown behavior were unqualified. |
| Filesystems | Scratch maps to CACHEDEV1_DATA; GPvQNAP to CACHEDEV2_DATA. All local volumes share the same disk failure boundary. Re-read actual source/destination device IDs for any rename. |

Do not launch scrub, rebuild, extended stress testing or physical redesign to
clear a checklist. Diagnose the fault and qualify recovery in a separate window.
Do not delete old snapshots or retired volumes as incidental space cleanup.
The completed wiki exception and newly approved private-library path move are
narrow exceptions recorded in the active plan, not proof these findings resolved.

## Share inventory, ownership and platform dependencies

- FromDrobo mixes local originals, replaceable copies, staging and a remote
  namespace. Its cached aggregate size included remote content and cannot size a
  local migration. Use shallow per-scope metadata and existing summaries.
- Both selected Public payload folders belong to Ryan. They are deferred personal
  data, not shared Documents or automatically part of the private Plex library.
- Homes are enabled and the deployment account's home/key is a known SSH recovery
  dependency. Human AD-home isolation remains unqualified; do not disable homes.
- Container Station has a required Container root. Keep explicit native-package
  exceptions. TMBackup and retired volume/root remnants require later ownership
  and consumer checks before retirement.
- Video Station and Multimedia Console were subsequently removed; use the
  [retirement receipt](nas-media-retirement-2026-10-25.md), not their old installed
  status from this preflight. Multimedia's share remains pending retirement.

## Backup findings

The preflight observed selected originals, two Public folders, NAS settings
archives and the current Time Machine share in HBS; homes and Multimedia were
not selected. Later job/seed settings belong to the
[backup runbook](../usenet-infra/docs/scheduled-backups.md).
A dated B2 sample restore of encrypted Forgejo artifacts and email delivery test
passed; neither established a private-originals/ACL or Time Machine restore.
The user's current static-private-library B2 assurance and temporary exclusion
are recorded separately in the [protection policy](plan-nas-data-protection.md#private-library-migration-exception).
