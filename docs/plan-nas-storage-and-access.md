# NAS storage and access improvement plan

Status: proposal, based on read-only inspection on **October 24, 2026**.
No NAS/cloud configuration, credentials, shares, ACLs, media, or disks were changed.
The requested laptop access includes **read/write access to managed media**.

The recommended order is recovery qualification, permission boundaries, clearer
shares and service identities, writable remote access, shared authentication, and
only then physical storage changes. Most of the benefit does not require a pool
rebuild. Separate the changes so each has a small, independently reversible cutover.

## What is actually deployed

### Disks, pool and volumes

QTS 5.2.10 build 20260731 runs on the TS-X53D platform, with two CPU cores and
about 4 GB RAM. All four installed disks belong to **one RAID-5 group, one pool,
and one LVM thin pool**. `/proc/mdstat` reported all four data members present,
with no rebuild in progress. This is array membership evidence, not a SMART test.

| Layer | Observed configuration | Consequence |
| --- | --- | --- |
| Disks | Three nominal 4 TB disks and one nominal 3 TB disk | RAID capacity is limited by the smallest member; about 9 TB decimal before higher-level overhead |
| RAID / pool | `md1`, RAID 5; pool 1 / `vg1`; `tp1` about 8.01 TiB | Every local volume shares the same disk failure boundary and redundancy |
| Thin pool | 57.27% data allocation, 0.50% metadata allocation | About 3.42 TiB of thin-pool data space was unallocated; do not add volume free-space figures together |
| System volume | `Scratch`, `/share/CACHEDEV1_DATA`, nominal 100 GiB; filesystem about 65.6 GiB used / 32.5 GiB available | Hosts applications and services despite its name |
| Main data volume | `GPvQNAP`, `/share/CACHEDEV2_DATA`, nominal 4 TiB; about 2.79 TiB used / 1.17 TiB available | Private collection, replaceable copies, remote cache, staging, and settings archives share this volume |
| Retired laptop volume | `SpaceGrayTimeMachine`, `/share/CACHEDEV4_DATA`, nominal 1,105.88 GiB; about 76 MiB filesystem usage | Share/data retirement left a nearly empty volume; ownership, snapshots and hidden dependencies must be checked before reuse/removal |
| Current laptop volume | `SpaceBlackM4TimeMachine`, `/share/CACHEDEV5_DATA`, nominal 2 TiB; about 1.37 TiB used / 626 GiB available | Active `SpaceBlackTimeMachine` SMB share |

LVM also reports a 4 TiB logical snapshot of the main data volume. Logical sizes,
filesystem usage, thin allocation and snapshot retention measure different things.
The retired thin volume is not automatically 1.08 TiB of reclaimable physical space.
`vg1` having zero unassigned extents does not mean the thin pool is full.

**A new share or volume cannot make Usenet non-redundant on this pool.** That
requires separate disks/another pool or rebuilding the disk layout. QTS documents
online migration from Single → RAID 1 → RAID 5 → RAID 6; it does not document a
RAID-5-to-single-disk downgrade. Treat such a redesign as evacuate/recreate/restore,
not an in-place toggle. [QTS RAID migration](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/changing-the-raid-type-of-a-raid-group-B775699B.html).

### Data and application dependencies

| Data or service | Current location / relationship | Preserve during migration |
| --- | --- | --- |
| Private originals | `/share/FromDrobo/loljk`; Plex library ID 1 | Physical root, library ID, metadata, watched state, privacy and offsite backup coverage |
| Optional NAS media copies | `/share/FromDrobo/Movies/video`, `/share/FromDrobo/TV Shows/library` | Copy ownership receipts, exact published paths, staging boundaries and Plex IDs 2/3 |
| Canonical Hetzner media | Existing BX21 Storage Box, 5 TiB; about 61% used | Arr-owned native library, legacy manifests/hardlinks, snapshots and independent settings-backup scopes |
| NAS remote view | Existing read-only rclone/SFTP mount at `/share/FromDrobo/Remote/files` | Server-restricted reader identity, mount propagation, Plex IDs 4/5 and Jellyfin source mounts |
| Playback cache | `/share/FromDrobo/.remote-cache` | Disposable; 20 GiB target, 100 GiB reserve, 24-hour age policy |
| Transfers | `/share/FromDrobo/FilexStaging` | Separate from canonical libraries; verified transfers, quarantine and disabled purge |
| Application state | `/share/Container/usenet`, plus `/share/Container/home-git` | Media apps, DNS, static wiki, Filex, backup configuration and Forgejo state |
| Native packages | Plex, HBS and Container Station on `CACHEDEV1_DATA` | Package installation paths and QTS system configuration |
| Settings archives | `/share/Usenet/Backups/automatic` | Separate confined off-host backup credential and recurring ciphertext readback |
| Other originals | Selected folders under `Public` | Distinguish actual originals from incidental downloads and application backups |
| Laptop backup | `SpaceBlackTimeMachine` | Existing destination identity and backup chain; do not recreate it just to rename it |

Eleven containers were running; containers with health checks reported healthy.
The native cloud ownership check passed. Cloud health reported four SAB warnings,
about 55.7 GiB repair-spool free space, and the intentionally retained historical
holds. These are baseline findings to inspect before a cutover, not reasons to
restart services or clear queues. Current acquisition/playback/backup activity
still needs a fresh check at each maintenance window.

The laptop currently mounts the Time Machine share. No other SMB mount was
present. Terraform already declares SMB enabled for the **read-only** Hetzner NAS
reader and says it was intended for Finder. This is configuration evidence, not
a current successful laptop mount or a fresh provider-side permissions test.

### Access findings

1. **The private filesystem boundary is broader than the Plex boundary.** The
   `FromDrobo` SMB share grants write access to named human accounts, `hass`, and
   administrators. The private-library root itself has explicit `rwx` ACL entries
   for `badmin`, `ryantimmons`, `hass`, and `michaellee`, plus permissive group/other
   and default entries. Descendant permissions and actual logins were not tested.
   Plex's restricted-profile grants do not protect direct SMB or local access.
2. **There are no purpose-specific local groups.** The observed groups are
   `administrators`, `everyone`, and `guest`. Share policy mostly names users or
   broad built-in groups; ACL masks and inherited defaults differ between roots.
   `0777` alone is not proof of guest access: guest is explicitly denied and
   effective access also depends on share policy and ACLs.
3. **Deployment and runtime identities overlap.** `usenet-deploy` is UID 1004 and
   a NAS administrator. Media-copy, Filex, DNS, wiki and Forgejo containers reuse
   UID 1004/GID 100. Their inspected containers do not automatically inherit the
   host's administrator supplementary group, and most have narrow mounts and
   dropped capabilities. Nevertheless, filesystem ownership and service lifecycle
   are coupled to the deployment principal.
4. **Jellyfin uses a documented exception:** UID 0/GID 100 with
   `DAC_READ_SEARCH`, narrow read-only media mounts, and no private library mount.
   Its GPU device permission is a separate constraint from media ACLs. Fix and
   test both before removing the exception.
5. **SMB hardening needs a compatibility pass.** Effective Samba configuration
   reports SMB2 minimum, SMB3 maximum, signing `No`, and
   `ntlm auth = ntlmv1-permitted`; inspected shares explicitly disable SMB
   encryption. This records permitted policy, not the protocol/authentication
   actually negotiated by every client. Guest mapping is `Never`.
6. **Authentication is local:** Samba reports `security=USER` with an `smbpasswd`
   backend. No deployed Authentik integration was found in the reviewed source or
   NAS container inventory. This is not an inventory of every other household host.

### Recovery evidence and limits

The latest NAS settings status was `ok`, with three archive scopes and last success
at **11:09 a.m. Eastern on October 24**. Earlier independent settings restores and
recurring off-host readback are documented in the existing recovery runbooks.
This investigation read the current status; it did not perform another restore.

The [scheduled-backup runbook](../usenet-infra/docs/scheduled-backups.md) records
B2 coverage for the private originals, two selected Public folders, encrypted
settings archives and the current laptop backup. It also records successful HBS
uploads, **no demonstrated B2 sample restore**, disabled client-side encryption,
and unverified email alert delivery. The newest HBS run and current selections
were not revalidated here. Do not infer media protection from the settings status.

## Target storage and namespace

Use purpose and recovery requirements for names. Separate shares, credentials,
backup selection and capacity policy even where data initially stays on one pool.
Names below are proposed; physical paths should change only when necessary.

| Proposed share / area | Purpose | Access | Protection and placement |
| --- | --- | --- | --- |
| `PrivateLibrary` | Private original collection | Explicit private readers/maintainers, scoped Plex and backup access | Keep on RAID; snapshots plus independently restored offsite backup |
| `Documents` / `Archive` | Personal and shared originals, classified from Public | Named household groups | RAID, snapshots and offsite backup according to ownership |
| `MediaCache` | Selective, replaceable NAS movies/TV | Media readers; copy service writes | No media backup needed after canonical availability is verified; separate non-redundant disk is an eventual option |
| `RemoteMedia` | Existing read-only canonical media view | Media readers and playback services | Keep existing reader; mount itself needs no backup |
| `RemoteManage` | Read/write canonical media mount | Media maintainers only | Separate Hetzner writer subaccount; snapshot/recovery and application reconciliation required |
| `RemoteFiles` | Optional general writable remote files | Explicit owner/group | Separate confined subaccount; define independent backup before storing originals |
| `TransferStaging` | Manual incoming/outgoing files and quarantine | Transfer owner and Filex | Quota, retention policy and completion verification; excluded from Plex |
| `AppData` | Application databases and settings | Per-service principals and administrators | RAID, application-consistent snapshots/backups; retain existing paths initially |
| `BackupArchives` | Encrypted settings archives | Backup services/operators | Local staging plus off-host verified copy; separate from general media writers |
| `SpaceBlackTimeMachine` | Current laptop recovery | Laptop backup principal and recovery admin | Keep name/destination now; capacity limit and restore test |

Initially expose `PrivateLibrary` as a QTS-managed share of the existing private
root, if supported by the installed firmware, preserving Plex ID 1 and its source
path. Remove unintended access through the old `FromDrobo` export at the same
cutover: a restricted new share does not fix an accessible old path. Inventory
every alias, NFS export, File Station path, snapshot/recycle view and service mount.

Prefer changing display labels and share definitions first. `Scratch` should be
described as system/application storage. Keep `CACHEDEV*` paths stable. Move the
smaller replaceable/staging trees only in separately tested same-filesystem
renames; do not recursively copy, hash or chmod the private collection merely to
make names prettier. Moving an active remote mount or playback cache requires
its own service/mount cutover, not a normal directory rename.

Keep the current RAID-5 pool initially. It already has substantial unallocated
thin-pool space, and all four bays are occupied. If more capacity is needed,
compare upgrading the smallest disk through QTS's supported expansion workflow
against a full rebuild or separate cache hardware. A nominal 4 TB replacement
could eventually remove the smallest-disk constraint, but capacity gain and safe
expansion depend on hardware health, model support, backups and the actual QTS
workflow; no purchase or disk change is proposed for the first phase.

If a future rebuild is justified, consider a protected pool for originals/apps
and an independent single-disk cache. Avoid making multiple disposable disks one
RAID-0/JBOD failure domain without a specific capacity reason. The key decision is
acceptable re-download time and downtime, not whether replaceable files deserve
another copy. Cache replicas still consume capacity even without RAID redundancy.

## Hetzner access from NAS and laptop

**Preserve the current NAS read-only mount and add a distinct maintainer path.**
The requested general read/write access must not turn the Plex/Jellyfin reader or
NAS-copy credential into a writer. Scope the human maintainer to the media tree,
excluding settings-backup directories, keys and unrelated data; use additional
subaccounts for disjoint roots rather than exposing a common privileged parent.

| Route | Benefit | Cost / limit | Proposed role |
| --- | --- | --- | --- |
| Laptop → Hetzner SMB3, encrypted | Native Finder filesystem; no dependency on NAS uptime or home uplink | Provider-specific credential; macOS must actually negotiate encryption; WAN latency and interrupted writes need tests | First pilot for full read/write access |
| Laptop → NAS SMB → separate Hetzner writable mount | NAS enforces household groups and presents consistent names; credentials remain on NAS | NAS and home uplink become dependencies; remote sees gateway identity; re-export, locking, ACLs and durability need qualification | Optional preferred home route if central access control wins |
| Laptop → encrypted SFTP filesystem client | Uses scoped key and host pin; avoids WAN SMB reachability issues | Requires a supported filesystem client; Finder alone is not an SFTP mount | Fallback if direct SMB cannot meet requirements |

Hetzner supports confined subaccounts and SMB/SFTP access. Its documentation
explicitly says SMB may be unencrypted without additional configuration. Verify
SMB3 encryption on the actual Mac connection; use provider hostnames and a
dedicated saved credential, not the primary account. [Hetzner subaccounts and
protocols](https://docs.hetzner.com/storage/storage-box/general/),
[SMB access and encryption](https://docs.hetzner.com/storage/storage-box/access/access-smb-cifs/).

For the NAS gateway pilot, establish a separately mounted writable backend with
explicit share authorization. A reverse proxy/Authentik web login does not
authenticate SMB. Do not assume local QNAP ACLs or usernames propagate through a
single backend credential. Direct access is a separate authorization route and
must be revoked separately. Keep NAS SMB LAN/VPN-only; do not publish its port to
the Internet. Do not expose backup archives through either media route.

Qualify locking, atomic rename, rename-over-existing, open-file deletion, large
files, Unicode/case behavior, extended attributes and reconnects with synthetic
files. A read-only rclone playback cache is not proof of safe writable re-export.
Prefer writes acknowledged by the remote server; if a candidate queues local
writeback, define when data is durable and test cache-full/power/network loss.
Mac caches, Spotlight/thumbnailing and offline copies must respect the same
private-data and capacity policy.

### Editing managed media without creating a second owner

Read/write mounting is allowed in the target design. Applications still own their
catalogues and import bookkeeping. Before moving/renaming/removing a managed item,
resolve its exact native/catalog ID and all consumers privately. Prefer Arr's
supported move/rename/delete operations where they express the requested edit;
otherwise quiesce affected writers, record the change and reconcile applications
afterward. Do not add a background two-way sync or automatic reacquisition worker.

Never modify hardlinked content bytes in place. Use a new file and atomic replacement
where appropriate, and preserve the five existing legacy/native hardlink relations
and their manifests. An uncoordinated Finder edit can invalidate file records,
manifests and NAS-copy ownership receipts even when the filesystem operation works.
Test manual-add, rename, replace and delete cases in a synthetic area before a
real maintenance operation. Preserve disabled automatic upgrades/RSS and existing
request scope so rescanning does not become unrequested acquisition.

## Identities, groups and SSO

Use one human identity per person, a separate administrative identity when needed,
and one service principal per independently managed service. Consistency means a
documented identity/group model and lifecycle; it does not mean reusing a human
password or one administrator UID for all daemons. Preserve stable numeric IDs
and, if a directory is introduced, stable SID/idmap mappings. Identical usernames
alone do not preserve ownership or ACLs across local/domain migration.

Proposed policy groups:

| Group / principal | Intended rights |
| --- | --- |
| `nas-admins` | NAS administration and recovery; no ordinary application membership |
| `private-media-readers`, `private-media-maintainers` | Explicit private access; no automatic inclusion of general media users |
| `media-readers`, `media-maintainers` | General playback/read access; maintainer write access to the separate management path |
| Household document groups | Access only to designated shared/original areas |
| `backup-operators` | Backup monitoring and isolated restore; source read and destination write scoped separately |
| `svc-media-copy`, `svc-remote-reader`, `svc-remote-maintainer` | Separate local-copy, canonical-read and gateway-write roles |
| Per-service DNS/Git/wiki/Filex/playback/backup identities | Only required config/state and explicit media roots; noninteractive where QTS supports it |
| Local emergency administrator | Independent of Authentik, DNS and remote storage; credentials and recovery instructions kept offline |

Keep a distinct NAS deployment administrator if QTS requires admin membership for
SSH/container management. First move application runtime ownership away from it;
do not remove the working recovery/deployment login as an incidental cleanup.
Cloud SAB/Arr shared-write and hardlink requirements need a deliberate group/umask
design; splitting their IDs blindly is not an improvement.

**Choose the identity authority before integrating SMB.** Two defensible paths:

1. **Practical first step:** local QNAP users/groups plus Authentik for supported
   web applications. Consistent naming and permissions, with separately managed
   SMB/Hetzner credentials. This fixes today's authorization problems without a
   directory dependency, but does not deliver one password everywhere.
2. **Full shared credentials:** an SMB-capable directory, such as an AD-compatible
   directory, supplies NAS users/groups; Authentik consumes that directory for
   web SSO. Test the actual QTS/directory combination in isolation. Keep directory
   storage, DNS and recovery independent of a NAS share that requires that same
   directory to mount. Given this NAS's 4 GB RAM and existing services, avoid
   making it the only home for both the directory and Authentik.

QNAP supports AD/LDAP membership, but its LDAP-backed SMB path additionally
requires Samba schema and Samba-password handling. Authentik's LDAP provider
documents basic LDAP compatibility; a successful LDAP bind is not proof of SMB
authentication. Do not choose Authentik-only LDAP as the NAS backend without a
demonstrated compatible implementation. The directory → Authentik direction is
documented by Authentik. [QNAP domain security](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/domain-security-5933D0DB.html),
[QNAP LDAP/Samba requirements](https://www.qnap.com/en/how-to/tutorial/article/connect-the-qnap-nas-to-an-ldap-directory),
[Authentik LDAP provider](https://docs.goauthentik.io/add-secure-apps/providers/ldap/),
[Authentik AD source](https://docs.goauthentik.io/users-sources/sources/directory-sync/active-directory/).

Migrate web apps individually. Preserve Plex account/library grants and Seerr's
Plex sign-in plus its approved local request account until replacement client
flows are actually demonstrated. An SSO proxy must not break APIs, TV clients,
service tokens or background requests. Test account disablement and session
expiry separately for browser, LDAP, SMB and direct Hetzner access.

## Staged execution and rollback

| Phase | Deliverable / gate | Rollback boundary |
| --- | --- | --- |
| 0. Recovery and baseline | Complete inventory below, current configuration exports, B2 and settings sample restores, usable alert route | No production changes; isolated restore destinations only |
| 1. Permission pilot | Synthetic test share, proposed groups, effective-access matrix; verify emergency admin | Remove pilot grants/share; no production media touched |
| 2. Private isolation | Restrict unintended users at private root and every alternate route; introduce clear share alias; preserve Plex source/ID | Restore exact saved ACL/share policy if authorized access or playback fails; do not leave an untested alias exposed |
| 3. Runtime separation | Move one service at a time to scoped identity and state ownership; address Jellyfin filesystem and GPU access separately | Restore that service's UID/GID, ACLs and config; compatible database checkpoint if required |
| 4. Writable remote access | Encrypted direct laptop pilot, then optional NAS gateway; separate writer and read-only reader; managed-edit protocol passes | Unmount/revoke only new writer routes; retain existing read-only playback mount |
| 5. Naming and placement | Rename misleading labels; split logical shares; selectively move replaceable/staging paths with all consumers mapped | Reverse same-volume rename and config references while original data remains; no conflicting dual writers |
| 6. Shared authentication | Directory/backend decision, synthetic SMB login, one web app and user pilot, account lifecycle tests | Keep tested local emergency login; restore mappings and old policy, not a stale whole-system database |
| 7. Optional pool redesign | Capacity/downtime decision and independently verified evacuation; disk-level runbook | Rebuild has no instant rollback: retain verified external source until full restore and acceptance |

Allow each changed service and backup to complete its normal cycle before the
next phase. Keep disk layout, identity authority and media path migrations in
different maintenance windows. A regression in privacy, file identity, backup
coverage or application ownership stops progression.

## Preflight and acceptance checklist

Checked items below are evidence obtained during this read-only investigation.
Unchecked items are execution gates or remaining inspection, not completed tests.

### Baseline and recoverability

- [x] Map disk sizes, RAID membership, pool and mounted volumes; record thin allocation.
- [x] Record share roots, root ACLs/defaults, local users/groups, effective Samba policy and container mounts/users.
- [x] Confirm existing read-only remote mount, current laptop destination and native cloud ownership status.
- [x] Read latest settings-backup success; record previously documented media-restore and alert gaps.
- [ ] Read disk SMART attributes, error history, last RAID scrub, snapshot schedule/retention, pool alarms and UPS shutdown behavior. The non-root probe did not produce SMART data.
- [ ] Determine used bytes by data class from existing indices/QTS accounting; do not trigger a whole-collection scan/hash merely to plan.
- [ ] Inventory shares/aliases, NFS/AFP/WebDAV/FTP, QTS application privileges, scheduled tasks, package paths, symlinks, open sessions and every client. The SMB session probe required root and was not completed.
- [ ] Resolve the retired laptop volume and its snapshots/hidden references. Retired share absence alone does not authorize deleting a volume.
- [ ] Export QTS settings, share/ACL configuration, UID/GID/SID mappings, Compose and mount definitions, Plex databases/preferences and library/profile IDs, Arr/Seerr settings, copy receipts and backup selection. Store secrets privately and encrypted.
- [ ] Verify fresh cloud and NAS settings archives, all required off-host ciphertext readbacks, and isolated restore readability. Include DNS/Forgejo and any future identity databases explicitly; do not assume media backups cover new services.
- [ ] Recheck live HBS source selection, exclusions, latest success and integrity status; restore a small private sample to an isolated location and verify bytes, ownership, ACLs and extended attributes without displaying content.
- [ ] Restore a Time Machine sample and confirm its encryption/recovery credential. Decide whether backing up the entire Time Machine history to B2 remains worth the cost.
- [ ] Establish working backup failure notifications. Decide client-side encryption and independent deletion-resistant backup policy before introducing more writable remote data.
- [ ] Agree acceptable data loss, service downtime and recovery time per class, including whether private originals have another independent copy.

### Permissions and identity

- [ ] Use synthetic files to test each human/service role: list/read/create/rename/delete, denied private traversal, denied backup/config access, and denied canonical writes by playback readers.
- [ ] Test all access routes: SMB, File Station, local container mounts, any NFS export, snapshots/recycle bins, direct Hetzner, and the optional NAS gateway. Hidden share names are not authorization.
- [ ] Verify both existing objects and newly created objects inherit intended group/ACL/mask behavior. Capture exact ACLs before changes; avoid collection-wide chmod/chown.
- [ ] Prove general users and `hass` cannot enter the private root; confirm intended private users and Plex still work. Preserve the restricted Plex profile's exact grants to IDs 2/3/4/5 and exclusion of ID 1.
- [ ] Verify service runtime UID/GID, supplementary groups, umask and mounts; ensure no human credentials or deployment admin group are needed for routine jobs.
- [ ] Qualify SMB signing/encryption and removal of NTLMv1 with the actual Mac, Time Machine and other clients; save prior settings and change one control at a time.
- [ ] Test directory DNS/time/TLS, stable ID mappings, name collisions, nested groups, password changes, user disablement, session/cache expiry and emergency access during IdP/DNS/WAN outage.

### Paths, storage and writable remote mounts

- [ ] Record each source → destination mapping, filesystem/device identity, required space/reserve, writer, reader, backup and rollback reference before any move.
- [ ] For same-volume renames, require absent destination and compare device/inode afterward. For a justified cross-volume move, preserve metadata/hardlinks, verify the moved data, and retain the old source until acceptance.
- [ ] Keep TV staging and publish locations in the same bind/filesystem for atomic rename. Preserve manifests and ownership receipts; do not adopt unrelated files into eviction ownership.
- [ ] Keep NAS 100 GiB reserve, cloud 30 GiB reserves, 100 GiB release limit, current repair volume and retired-worker disablement.
- [ ] Test startup with storage unavailable and reconnect after interruption: refuse dependent work, preserve mode-0000 unmounted cloud directories, prevent writes into empty local mountpoints, and do not empty Plex trash.
- [ ] Verify FUSE/shared-mount propagation, remount behavior and dependent-container visibility using a pilot before any production mount move.
- [ ] Test writable remote large-file transfers, checksum readback of synthetic files, interrupted copy, rename/replace, hardlink behavior, filename/metadata semantics, concurrent users, full destination/cache and laptop sleep/wake.
- [ ] Verify server-side reader denial remains effective and the new writer cannot reach backup/config roots. Record credential owner, root, allowed protocols and revocation for every subaccount.
- [ ] Define manual managed-media reconciliation: native records, manifests, link relationships, NAS receipts and both media servers agree after each operation; no unexpected downloads or deletes.

### Application and household acceptance

- [ ] Before each cutover, check downloads/postprocessing/imports, manual pauses, NAS transfers, Plex/Jellyfin sessions, Time Machine and HBS activity. Preserve active work and stop only affected services.
- [ ] Compare Plex library IDs/roots, profile grants and private visibility before/after. Keep automatic trash emptying disabled. Test actual household TV clients and owner/restricted profiles privately.
- [ ] Verify Jellyfin general-library scans and representative playback/transcoding, with private media still absent and GPU access working after any identity change.
- [ ] Verify Seerr sign-ins/requests/availability, Arr library mappings and queue history, copy/evict receipts, Filex quarantine and existing held jobs. Do not enqueue downloads just to audit.
- [ ] Verify DNS resolution, wiki and Forgejo clone/fetch after any application-volume or UID change; test emergency IP-based management if DNS is down.
- [ ] Confirm current Time Machine continues the existing backup chain after SMB/identity changes and can restore a sample.
- [ ] Confirm HBS still selects the exact intended sources after every share/path change; exclude remote mounts, caches and staging; preserve existing B2 history. Check incremental behavior before allowing an unexpected full re-upload.
- [ ] Perform a controlled restart/reboot and outage test only in its maintenance phase, then verify all mounts, credentials, service dependencies and backup schedules. A healthy container alone is insufficient.
- [ ] Record acceptance and rollback evidence without media names/IDs in Git. Update canonical runbooks, inventory and recovery supplements; keep original bound snapshots immutable.

## Decisions to settle before implementation

The user has chosen writable laptop access including managed media. Remaining
choices are: intended private-library users; the recovery/downtime budget; direct
Hetzner versus NAS-mediated everyday access after the pilot; whether one password
across SMB and web apps warrants a separate directory; where that directory lives;
and whether disk capacity pressure justifies a later physical redesign.

Start with the recovery/permission pilot. The observed broad private-root grants
and shared deployment/runtime identity offer a clearer immediate benefit than
rebuilding a functioning RAID group.
