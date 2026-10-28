# NAS data protection policy

Start with the [migration plan](plan-nas-storage-and-access.md). This document
owns target recovery policies and migration-specific exceptions. Operational job
settings and dated receipts belong in the [backup runbook](../usenet-infra/docs/scheduled-backups.md),
not duplicate baselines here. Proposed policies are not deployed jobs.

## Private-library migration exception

The user reports that `/share/FromDrobo/loljk` is static and already backed up on
B2, and accepts temporarily disabling backups of that dataset while moving it
into `PrivatePlexLibrary`. This is an explicit exception to continuous backup
coverage during path changes. It is user-supplied recovery assurance, not a new
agent-verified full-library restore. Do not require a replacement initial sync,
full-library download or new whole-tree checksum scan before the NAS-side move.

1. Before moving, record the affected legacy and replacement HBS source selections,
   destination catalogs and recovery-key references. Both jobs may include the
   same private root. Protect the existing B2 versions from pruning/deletion while
   the source is excluded or renamed; verify source-removal behavior rather than
   assuming that removing a selection preserves remote history.
2. Exclude/disable this dataset in all affected jobs. A running seed must not keep
   reading the disappearing path: use a supported stop/edit/resume procedure for
   that affected job if necessary. Preserve the other source selections, schedules,
   retention and credentials. If HBS cannot isolate the source without broader
   interruption or deleting history, resolve that specific constraint before
   proceeding; do not silently abandon other datasets' protection.
3. Complete and accept the local share/path migration. Record the intentional
   backup gap; no new writes are expected. Existing B2 history remains the fallback.
4. Later, configure protection for the new canonical root and perform its initial
   sync. Keep old history until the new private-library coverage completes and a
   bounded independent restore demonstrates usable data and applicable metadata.
   Resume the intended recurring policy and record the old-to-new restore path.
5. Only then retire the superseded private-library B2 data. If it is inside a
   mixed HBS/QuDedup repository, use supported catalog-aware retirement; do not
   delete shared chunks or an entire prefix that still protects other datasets.
   Identify the exact target and account for object versions before deletion.

**Coordination with the ongoing backup migration:** the October 27 runbook records
legacy `Backup 1` and a replacement `B2 QuDedup 20261027` seed. Re-read their live
status before editing; creation/startup is not completed recovery. Its earlier
retirement condition (seed plus a settings sample restore) is insufficient to
delete the old repository if the private library has since been excluded.
Before excluding the source, reconcile the active seed-completion follow-up and
its handoff with this changed scope so it cannot retire that only retained copy.
The private-library replacement and other still-required sources must all be
accounted for before whole-repository retirement. Keep the backup task's current
bandwidth and scheduling decisions; do not reinstate an older cap from a plan.

## Per-share policy

This is the canonical protection mapping. Share purposes and grants live in the
[access model](plan-nas-access-model.md). Protected means retain fault-tolerant
backing storage; Replica can use lower redundancy only after independent source
and restore qualification; Disposable requires a proven rebuild source. These
are eventual tiers: all current local NAS volumes still share one RAID-5 group.
Shares and bind aliases do not create independent failure domains.

| Share | Target storage tier | B2 policy | Scope / current coverage |
| --- | --- | --- | --- |
| `PrivatePlexLibrary` | Protected | Local originals | Static private originals; October 28 move accepted, temporarily excluded from both HBS jobs; new-root seed and restore verification pending |
| `Documents` | Protected | Local originals | Explicitly classified shared originals; no current Public payload assigned here; new roots need explicit inclusion |
| `home` (Ryan) | Protected | Local originals | Canonical AD home, including both Ryan-owned Public folders after cutover; personal root unqualified and homes absent from current HBS selection |
| `home` (Michael) | Protected | Local originals | Canonical AD home; personal root unqualified and homes absent from current HBS selection |
| `homes` | Protected | Local originals | Back up the selected canonical user directories once; the administrative parent and per-user views are not additional copies |
| `MediaCache` | Disposable | Rebuild | No B2 copy of replaceable media; back up manifests/ownership receipts as application settings |
| `PlaybackCache` | Disposable | Rebuild | No B2 copy of disposable rclone cache bytes; protect `remote-reader` configuration through Application recovery |
| `RemoteMedia` | Provider-managed | Rebuild | Canonical replaceable media is excluded from B2; this read-only view is not a second backup source |
| `RemoteManage` | Provider-managed | Rebuild | Same canonical data and policy as `RemoteMedia`; a writable alias does not create another backup set |
| `RemoteFiles` | Provider-managed | Remote originals | General files and originals; new protection, not covered by the current NAS HBS selections |
| `Hetzner` | Provider-managed | Mixed by subtree | One canonical account inventory: remote originals protected, replaceable media excluded, already-covered settings replicas deduplicated by source policy |
| `TransferStaging` | Disposable, conditional | Transient | No B2 backup while another verified source exists; a sole copy must be moved into a protected class before it is treated as durable |
| `forgejo` | Protected | Forgejo recovery | Entire consistent application recovery set, including Git objects; existing encrypted Forgejo archives already sit in the B2-selected parent |
| `forgejo-backups` | Replica | Forgejo recovery | Upload these archives to B2 once; preserve old history and existing confined Hetzner copy |
| `jellyfin` | Protected | Application recovery | Consistent export to `infrastructure-backups`; exclude only proven-rebuildable cache/transcodes; qualify recurring coverage |
| `media-control` | Protected | Application recovery | Preserve ownership receipts and journals in consistent exports; media bytes remain in their separate shares |
| `filex` | Protected | Application recovery | Export required configuration/keys; keep transfer payload policy separate |
| `dns` | Protected | Application recovery | Capture resolver/discovery recovery inputs together; preserve subfolder ownership and startup dependencies |
| `wiki` | Disposable, conditional | Rebuild | Independent source/build recovery verified for wiki; preserve unique configuration and qualify unattended capture |
| `remote-reader` | Protected | Application recovery | Export configuration/credentials; exclude FUSE mounts and `PlaybackCache` from capture |
| `remote-maintainer` | Protected | Application recovery | New dataset when gateway is provisioned; encrypted export to `infrastructure-backups` |
| `hetzner-gateway` | Protected | Application recovery | New dataset when provisioned; secrets stay off the exported Storage Box filesystem |
| `backup-control` | Protected | Application recovery | Capture recovery inputs through an independent encrypted export; exclude output archives, locks and rebuildable scratch; keys escrowed independently |
| `infrastructure-backups` | Replica | Application recovery | Split from existing `Usenet/Backups/automatic`; include consistent Jellyfin/media/Filex/DNS exports and supported QTS/Plex/HBS exports; qualify gaps |
| `HomeAssistantBackups` | Replica | HA archives | Native protected HA archives; new NAS/B2 coverage is required; the native daily job currently stores only on HA |
| `SpaceBlackTimeMachine` | Replica | Laptop history | Preserve existing HBS/B2 coverage of the current laptop backup chain |

## Recovery contracts

| Policy | Target capture and offsite behavior | Retention / acceptance |
| --- | --- | --- |
| Local originals | Nightly versioned HBS, preserving ownership/ACLs/xattrs; private-library exception above applies temporarily | Proposed 30 daily and 12 monthly points; isolated data/metadata restore |
| Remote originals | Proposed cloud-side encrypted B2 backup of canonical Storage Box originals from a stable read-only view or quiesced source | Proposed 30 daily and 12 monthly points; account-wide inventory with explicit replaceable/transient exclusions |
| Forgejo recovery | Consistent stopped-state capture of database, repositories, LFS, attachments, configuration and keys; encrypted archives to `forgejo-backups`, separate uploader to B2; retain existing Hetzner recovery | Preserve existing producer retention (at least seven generations and archives younger than 90 days) and history; proposed B2 30 daily/12 monthly; restore IDs, repository integrity, login and attachments |
| Application recovery | Application-aware consistent exports to `infrastructure-backups`; separate B2 upload, preserving current activity gates and off-host readback | At least daily and before material changes; proposed B2 30 daily/12 monthly; per-stream freshness and restore evidence |
| HA archives | Native protected Home Assistant archives, then separate NAS/B2 replication; preserve their own encryption and restore semantics | Proposed 30 daily/12 monthly offsite; do not confuse HA's local retention with independent protection |
| Laptop history | Consistent Time Machine capture through HBS, avoiding active-writer inconsistency | Preserve current latest-30-version policy until a separate change; demonstrate a usable restore, not just an uploaded bundle |
| Rebuild | No backup of reproducible media/cache/site payloads; protect unique configuration and source/build inputs | Prove the replacement source remains available |
| Transient | No backup while another verified source exists | A sole-copy original must become protected data, not disappear as staging cleanup |
| Mixed by subtree | Back up each canonical remote object once under its actual policy | Writable aliases are not separate sources; full-account access gets no B2/decryption credentials |

Schedules are proposed start times, not completion promises. Preserve deployed
retention/encryption/schedules until their own change is approved. New encrypted
jobs require independent destinations and recovery tests; a source selection or
SSE policy alone is not proof of client-side encryption. Do not apply another
backup tool's pruning rules to an HBS repository. Keep historical keys.

Application capture must use a native database export, supported consistent
snapshot or qualified stop/capture/start. Copying live SQLite/AD files is not an
accepted substitute. Forgejo is the complete application recovery unit, not only
a repository clone or settings directory. Native HA backups remain separate from
Talos/controller exports, NAS settings and media backups. A fresh outer archive
may contain an old native QTS export: check source freshness as well as upload time.

Daily protected streams should target source age under 24 hours, with failure and
age-over-36-hour alerting; the approved static private-library pause is an explicit
exception. Keep producer checksums, destination readback and independent sample
restores. Recheck affected recovery after path/key/format changes. Whole-machine
or full Time Machine recovery claims require their own evidence.

### Required platform roots

Retained Public, homes, Container and native QTS/Plex/HBS paths are explicit
exceptions, not implicit backup exclusions. Unique originals use Local originals;
supported package/configuration exports use Application recovery. Keep a minimal
platform root unbacked only after establishing it has no unique payload, while
still preserving its share/ACL definition. `Scratch` → `System` is only a later
volume label change; it neither creates protection nor changes source identity.
Human homes remain unqualified; preserve deployment SSH homes and select canonical
personal directories once rather than backing up every alias. The two Public
folders belong to Ryan and retain their existing protection until separately moved.

## Job owners and access

| Job / target account | Source role | B2 destination role |
| --- | --- | --- |
| HBS originals, homes and laptop jobs / `svc-originals-backup` | `originals-backup-reader`, `home-backup-reader`, bounded per job | `b2-backup-writer(originals)` and `b2-backup-writer(laptop-history)` |
| Forgejo capture / `svc-forgejo-backup` | `forgejo-backup-source-reader`, bounded `forgejo-capture-control`; writes `forgejo-backups` through `archive-writer(forgejo)` | None; emits verified encrypted archives for the separate uploader |
| NAS/application capture / `svc-settings-backup` | `infrastructure-backup-source-reader`; writes assigned `infrastructure-backups` streams through `archive-writer(infrastructure)` | None; preserves the existing separately confined Hetzner upload/readback |
| Forgejo archive upload / `svc-archive-b2` | `archive-readers(forgejo)` on `forgejo-backups`; no live Forgejo grant | `b2-backup-writer(forgejo)` |
| Infrastructure archive upload / `svc-archive-b2` | `archive-readers(infrastructure)` on `infrastructure-backups`; no live service-source grant | `b2-backup-writer(infrastructure)` |
| HA archive replica / `svc-ha-backup-replica` | `ha-backup-readers` | `b2-backup-writer(home-assistant)` |
| Remote originals / `svc-hetzner-backup` | `hetzner-account-readers` through a read-only source view | `b2-backup-writer(remote-originals)` |
| Recovery operator | Explicit isolated-restore role and separately held decryption material | `b2-restore-readers(scope)`; no routine prune authority |

These service names are targets, not newly created identities. Keep capture
producers, uploaders, recovery operators and runtime principals separate. HBS
jobs still share a trusted native package process; separate selections/keys are
not OS-level isolation. Runtime accounts get no archive or B2 grant. Destination
keys are scoped per repository/job and remain outside ordinary source exports.
`backup-control` contains per-job inputs/status, not recursively captured output
archives; preserve its recovery inputs and independently escrowed keys.

## Other migrations and acceptance

Outside the private-library exception, preserve old protection until replacement
source mapping, normal capture, offsite verification and restore pass. Keep
cross-volume sources frozen until acceptance; a same-volume rename has reverse-
rename rollback but creates no second data copy. Record post-cutover writes before
rollback. Never duplicate remote FUSE content into local backup scope by accident.

Wiki's named-share capture and independent manual offsite restore passed. Verify
its next eligible unattended cycle, alongside the repaired cloud/Forgejo schedules.
Do not infer whole-NAS or private-originals recovery from those application checks.
Storage redundancy reduction, scrub/rebuild work and physical redesign still need
the separate [storage readiness findings](nas-preflight-2026-10-25.md) addressed.
