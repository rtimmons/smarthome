# NAS storage and access improvement plan

Status: storage proposal with an **October 24, 2026 storage baseline**, revised
on **October 25** against the deployed household identity rollout and fresh
read-only directory, QNAP trust/share/ACL and HTTP/TLS checks. Neither planning
review changed live configuration, credentials, shares, ACLs, media or disks.
The requested laptop access includes **read/write access to managed media**.

**Samba AD on Home Assistant, Authelia browser SSO and QNAP domain membership are
already deployed.** Preserve that architecture; the original Authentik/backend
selection proposal is superseded by the [household identity runbook](operations/household-identity.md).
The remaining order is recovery coverage, storage authorization, runtime-service
separation, writable remote access, clearer names, and physical storage changes
only if justified. Most of the benefit does not require a pool rebuild. Keep
each cutover independently reversible.

## What is actually deployed

### Disks, pool and volumes — October 24 baseline

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

At the October 24 storage inspection, eleven containers were running; containers with health checks reported healthy.
The native cloud ownership check passed. Cloud health reported four SAB warnings,
about 55.7 GiB repair-spool free space, and the intentionally retained historical
holds. These are baseline findings to inspect before a cutover, not reasons to
restart services or clear queues. Current acquisition/playback/backup activity
still needs a fresh check at each maintenance window.

At that inspection, the laptop mounted the Time Machine share. No other SMB mount was
present. Terraform already declares SMB enabled for the **read-only** Hetzner NAS
reader and says it was intended for Finder. This is configuration evidence, not
a current successful laptop mount or a fresh provider-side permissions test.

### Access findings — revised October 25

1. **The private filesystem boundary is broader than the Plex boundary.** The
   `FromDrobo` SMB share grants write access to named human accounts, `hass`, and
   administrators, plus the new domain group `SMARTHOME\nas-users`. The
   private-library root still has explicit `rwx` ACL entries
   for `badmin`, `ryantimmons`, `hass`, and `michaellee`, plus permissive group/other
   and default entries. Descendant permissions and actual logins were not tested.
   Plex's restricted-profile grants do not protect direct SMB or local access.
2. **Domain access groups now exist; storage isolation is still incomplete.**
   QNAP uses `nas-users`, `nas-timemachine` and `nas-multimedia-writers` from AD,
   alongside the preserved local users and built-in groups. The new grants
   reproduce approved household access rather than separating private originals,
   replaceable media and application state. ACL masks/defaults still differ by root.
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
   now reports SMB2 minimum, SMB3 maximum, signing `if_required`, and
   `ntlm auth = ntlmv1-permitted`; inspected shares explicitly disable SMB
   encryption. This records permitted policy, not the protocol/authentication
   actually negotiated by every client. The identity rollout separately proved
   encrypted SMB3 operations with clients requesting encryption; this does not
   prove every Mac/Time Machine session requires or negotiates it.
6. **QNAP now authenticates through AD.** Fresh checks show `security=ADS`, realm
   `AD.HOME.ARPA`, workgroup `SMARTHOME`, and a successful machine-trust check.
   The active directory is on HA; the former NAS DC is stopped with restart
   disabled. Browser SSO uses Authelia, not Authentik. Preserved local recovery
   accounts and service identities remain separate from domain identities.

### Established identity and application access

The [identity runbook](operations/household-identity.md) owns the rollout and
recovery details. The storage plan extends its authorization model; it must not
rejoin the NAS, reprovision the domain, recreate users or replace working SSO.

| Interface | Deployed identity / authorization | Preservation requirement |
| --- | --- | --- |
| QNAP SMB | `SMARTHOME` AD on HA; verified household domain logins | Preserve domain/account SIDs, QNAP machine trust, idmap and local recovery access |
| Existing share grants | Both household users: FromDrobo RW and Public RO; Ryan: Multimedia RO and Time Machine RW; Michael: Multimedia RW and Time Machine denied | Preserve this approved access until each replacement share has an explicit policy; neither household user gets Container/Usenet access |
| Browser identity | Authelia on HA, LDAPS to `dc1.ad.home.arpa`, OTP and publicly trusted `*.home.rytim.com` HTTPS | Preserve original storage/session/OIDC keys, MFA database, CA trust and ACME state |
| Forgejo | `git-users`, Authelia OIDC/MFA, linked existing account | Keep original user/repository IDs, SSH keys and local recovery login; fresh browser sign-in previously passed |
| Arr/SAB browser | `arr-users`, Authelia MFA on every browser/API path at the HTTPS origins; HA-only cloud gateway credential | Keep service API routes/keys and numeric recovery access; authenticated browser acceptance remains pending in the runbook |
| Catalog/OliveTin | Native confidential OAuth plus outer Authelia MFA; verified `ryantimmons` action ACL | Keep owner-only actions, exact callback and local recovery credential; human OAuth acceptance remains pending |
| Jellyfin/Moonfin | Verified LDAPS using `svc-jellyfin`; existing Ryan profile/`ryan` alias retained | Keep original user ID, library/admin policy, Moonfin request link and hidden local recovery admin; native APIs do not use browser MFA |
| Plex, Seerr and HA | Existing native authentication; Seerr retains approved Moonfin request account | Preserve account IDs, client sessions, API keys and HA ingress; no blanket SSO redirect over native APIs |
| Standalone LAN tools | Ryan-only MFA at new HTTPS entrances; old LAN HTTP/direct ports and ingress remain | Treat compatibility paths as separate LAN access boundaries, not universal SSO enforcement |

Fresh October 25 checks found 295 directory objects with no database errors,
working Kerberos DNS discovery, valid QNAP trust, and all 45 existing HTTP/TLS
route checks passing. They checked anonymous gates and native API denial without
signing in or inspecting media. They do not complete the pending human Arr/Catalog
flows or prove Roku/TV sign-in after the Jellyfin directory migration. The
encrypted SMB create/read/write/delete and denial checks are the October 24
rollout's recorded evidence; no new SMB fixtures were created for this review.

### Recovery evidence and limits

The October 24 NAS settings status was `ok`, with three archive scopes and last success
at **11:09 a.m. Eastern on October 24**. Earlier independent settings restores and
recurring off-host readback are documented in the existing recovery runbooks.
The October 24 investigation read that status; this review did not repeat a
backup or restore.

The identity rollout additionally passed independent AD/cold-HA restores,
including domain/account identity, SYSVOL ACLs, password material and QNAP
member-machine trust material;
Authelia MFA/configuration recovery; post-link Forgejo recovery; and pre/post-AD
Jellyfin decrypt checks. Current credentials have separate SOPS escrow, with
authenticated restore tests. These are completed point-in-time qualifications,
not proof of recurring off-host coverage for the new HA identity apps, SSL state,
private controller CA or Jellyfin. Add that recurring coverage explicitly and
test a current restore after relevant changes. Credential escrow is not a backup
of AD databases, MFA enrollment or application account links.

AD, Authelia, the directory route, ACME and the HTTPS proxy now depend on the
same HA host. Loss of HA affects new domain logins and browser SSO. Keep native
local recovery administration, separately reachable management and off-host
backups. Never restart the retired NAS DC or recreate the rejected NAS VM as
an outage shortcut; a future second DC needs supported replication and a
distinct identity/address on a suitable independent host.

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
| `RemoteManage` | Read/write canonical media mount | Explicit AD media-maintainer group through QNAP | Separate Hetzner gateway writer subaccount; snapshot/recovery and application reconciliation required |
| `RemoteFiles` | Optional general writable remote files | Explicit owner/group | Separate confined subaccount; define independent backup before storing originals |
| `TransferStaging` | Manual incoming/outgoing files and quarantine | Transfer owner and Filex | Quota, retention policy and completion verification; excluded from Plex |
| `AppData` | Application databases and settings | Per-service principals and administrators | RAID, application-consistent snapshots/backups; retain existing paths initially |
| `BackupArchives` | Encrypted settings archives | Backup services/operators | Local staging plus off-host verified copy; separate from general media writers |
| `SpaceBlackTimeMachine` | Current laptop recovery | Existing local grants plus `SMARTHOME\nas-timemachine`; recovery admin | Keep name/destination now; separately verify the Mac's actual account realm and backup chain |

Initially expose `PrivateLibrary` as a QTS-managed share of the existing private
root, if supported by the installed firmware, preserving Plex ID 1 and its source
path. Remove unintended access through the old `FromDrobo` export at the same
cutover: a restricted new share does not fix an accessible old path. Inventory
every alias, NFS export, File Station path, snapshot/recycle view and service mount.
Test preserved local accounts and domain accounts separately. Do not assume that
adding a private AD group removes old local ACEs or the broad `nas-users` grant.

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
| Laptop → Hetzner SMB3, encrypted | Native Finder filesystem; no dependency on NAS/HA uptime or home uplink | Separate provider credential and revocation; macOS must negotiate encryption; WAN/interrupted-write tests required | Optional direct/travel/recovery route; separate human maintainer subaccount |
| Laptop → NAS SMB → separate Hetzner writable mount | Existing QNAP AD membership enforces household groups; provider credentials remain on NAS | NAS, HA directory and home uplink dependencies; remote sees gateway identity; re-export/locking/durability need qualification | Preferred LAN target after a synthetic writable-gateway pilot passes |
| Laptop → encrypted SFTP filesystem client | Uses scoped key and host pin; avoids WAN SMB reachability issues | Requires a supported filesystem client; Finder alone is not an SFTP mount | Fallback if direct SMB cannot meet requirements |

Hetzner supports confined subaccounts and SMB/SFTP access. Its documentation
explicitly says SMB may be unencrypted without additional configuration. Verify
SMB3 encryption on the actual Mac connection; use provider hostnames and a
dedicated saved credential, not the primary account. [Hetzner subaccounts and
protocols](https://docs.hetzner.com/storage/storage-box/general/),
[SMB access and encryption](https://docs.hetzner.com/storage/storage-box/access/access-smb-cifs/).

The completed QNAP domain join makes the NAS gateway the best fit for shared
household credentials on the LAN. Pilot it before depending on it for managed
writes; if it fails correctness or durability checks, retain playback as-is and
use the separately scoped direct route. Do not add another identity backend just
for remote storage.

For the gateway pilot, establish a separately mounted writable backend with
explicit AD share authorization. QNAP's domain membership authenticates SMB;
Authelia browser cookies/MFA do not. Local QNAP ACLs and individual usernames do
not automatically propagate through a shared provider credential. Direct access
uses a distinct human Hetzner credential and bypasses QNAP's group decisions;
AD disablement does not revoke it. Keep a credential/root/revocation inventory,
preserve the server-enforced read-only playback account, and keep backup roots
outside both writable routes. NAS SMB remains LAN/VPN-only.

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

Use the existing `SMARTHOME` human identities as the authority for new NAS share
grants. Preserve a separate administrative/recovery identity and one runtime
principal per independently managed service. Directory login, browser SSO and
Unix filesystem ownership are different mechanisms: the SSO rollout did not
replace the shared UID 1004 used by NAS containers. Do not map every runtime
process to a human domain account or grant LDAP lookup accounts media access.

Preserve current domain/account SIDs, QNAP machine trust and SID-to-UID/GID mapping.
The local and domain versions of `ryantimmons`/`michaellee` are distinct
principals even when their names match. Record domain-qualified identities in
ACL exports and test both routes before retiring any compatibility grant.
Changing a visible username is not an ownership migration.

Keep the existing groups and add narrowly scoped storage groups in AD only
when their share pilot is ready. Proposed additions are not current grants:

| Group / principal | Intended rights |
| --- | --- |
| Existing `nas-users` | Preserve approved FromDrobo/Public/Multimedia compatibility; progressively replace broad storage grants after equivalent narrower access passes |
| Existing `nas-timemachine`, `nas-multimedia-writers` | Preserve Ryan's Time Machine and Michael's Multimedia scope; do not repurpose these groups |
| Existing `git-users`, `arr-users` | Browser application access only; no implied NAS, private-media or backup rights |
| New `private-media-readers`, `private-media-maintainers` | Explicit private access after the owner selects members; never automatically nest `nas-users` |
| New `media-readers`, `media-maintainers` | General media read access and separate remote-management write access |
| New household document groups | Access only to designated shared/original areas |
| New `backup-operators` | Backup monitoring and isolated restore; source read and destination write scoped separately |
| Proposed `svc-media-copy`, `svc-remote-reader`, `svc-remote-maintainer` roles | Separate local-copy, canonical-read and gateway-write roles; inventory existing credentials before provisioning anything |
| Per-service DNS/Git/wiki/Filex/playback/backup identities | Only required config/state and explicit media roots; noninteractive where QTS supports it |
| Existing `svc-authelia`, `svc-jellyfin` | Dedicated directory lookup identities; preserve no administrative or NAS-share access and no password-write delegation |
| Local emergency administrators | Existing QNAP, Forgejo and Jellyfin recovery identities; independent of Authelia/directory availability |

Keep a distinct NAS deployment administrator if QTS requires admin membership for
SSH/container management. First move application runtime ownership away from it;
do not remove the working recovery/deployment login as an incidental cleanup.
Cloud SAB/Arr shared-write and hardlink requirements need a deliberate group/umask
design; splitting their IDs blindly is not an improvement.

**Identity selection and hosting are settled.** Samba AD runs in HA's isolated
directory app, with the directory-route app retaining `192.168.1.10` and
`dc1.ad.home.arpa`. Authelia uses verified LDAPS and the HTTPS proxy/ACME services
on HA. QNAP is a member file server. Do not introduce Authentik, rebuild the AD
domain or move it back onto the NAS as part of storage cleanup. The existing
architecture follows [Authelia's AD integration](https://www.authelia.com/integration/ldap/activedirectory/)
and [Caddy forward-auth](https://www.authelia.com/integration/proxies/caddy/);
installation and recovery remain owned by the household identity runbook.

Preserve native application authorization as well as the outer identity gate:
Catalog's verified owner username/action ACL, Forgejo's explicit account link,
Arr's HA-only gateway credential, and Jellyfin's original account/library policy.
Jellyfin/Moonfin shares the AD password through LDAPS; its playback APIs must not
receive browser MFA redirects. Keep Plex/Seerr's native sign-in, approved Moonfin
request account and HA native authentication/ingress. Preserve service API/SSH
keys rather than replacing them with browser sessions.

Test account disablement, group removal and password changes independently for
SMB sessions/Kerberos tickets, browser/OIDC sessions, Jellyfin tokens, local
compatibility logins and direct Hetzner credentials. Do not assume a one-minute
directory refresh terminates existing application sessions. Authelia's current
configuration disables password reset/change and has no directory password-write
delegation; handle planned changes through the established AD administration
workflow. After a deliberate Ryan AD password change, update the saved Jellyfin
operator credential used by the Moonfin helper, then recapture/verify SOPS as the
identity runbook requires. Never rotate credentials merely to reconcile this plan.

## Staged execution and rollback

| Phase | Deliverable / gate | Rollback boundary |
| --- | --- | --- |
| Established identity baseline | AD/Authelia on HA, QNAP trust, original account links and approved domain share grants already deployed | Preserve current identities and post-join recovery state; no rejoin/reprovision or retired-DC startup |
| 0. Recovery and baseline | Current exports; explicit recurring off-host identity/Jellyfin coverage; remaining B2/Time Machine sample restores and alerts; complete pending human acceptance before changing affected apps | Isolated restores; retain the original identity keys and current AD/Authelia databases |
| 1. Permission pilot | Synthetic share using narrow AD groups; local/domain effective-access matrix; verify emergency admin | Remove only pilot grants/share; do not delete/recreate existing accounts or groups |
| 2. Private isolation | Remove unintended local/domain access through every route; introduce clear share alias; preserve Plex source/ID | Restore exact saved ACL/share policy if authorized access or playback fails; do not roll back the domain join |
| 3. Runtime separation | Move one service at a time to scoped identity and state ownership; address Jellyfin filesystem and GPU access separately | Restore that service's UID/GID, ACLs and config; compatible database checkpoint if required |
| 4. Writable remote access | Qualify AD-authorized NAS gateway; separately scoped direct route if needed; keep playback read-only and managed edits reconciled | Unmount/revoke only new writer routes; preserve existing domain and read-only playback mount |
| 5. Naming and placement | Rename misleading labels; split logical shares; selectively move replaceable/staging paths with all consumers mapped | Reverse same-volume rename and config references while original data remains; no conflicting dual writers |
| 6. Identity continuity and acceptance | Repeat Arr/Catalog browser and TV/native-client acceptance after changes; verify account lifecycle, HA outage recovery and recurring backup restore | Revert only the affected storage/service integration; retain current account IDs, MFA keys and domain trust |
| 7. Optional pool redesign | Capacity/downtime decision and independently verified evacuation; disk-level runbook | Rebuild has no instant rollback: retain verified external source until full restore and acceptance |

Allow each changed service and backup to complete its normal cycle before the
next phase. Keep disk layout, group/ACL changes and media path migrations in
different maintenance windows. A regression in privacy, file identity, backup
coverage or application ownership stops progression.

## Preflight and acceptance checklist

Checked items identify either the dated storage investigation, the documented
identity rollout or fresh October 25 read-only checks. Unchecked items are
remaining gates; historical acceptance does not waive regression checks after
later changes.

### Baseline and recoverability

- [x] Map disk sizes, RAID membership, pool and mounted volumes; record thin allocation.
- [x] Record share roots, root ACLs/defaults, local users/groups, effective Samba policy and container mounts/users.
- [x] Confirm existing read-only remote mount, current laptop destination and native cloud ownership status.
- [x] Read October 24 settings-backup status; record previously documented media-restore and alert gaps.
- [x] Reconcile the completed AD/Authelia rollout, approved domain share grants, existing application links and dated identity restore evidence with the storage plan.
- [x] Recheck HA directory database/DNS status, QNAP machine trust, share grants/private-root ACL, retired DC shutdown and all 45 HTTP/TLS route checks on October 25. No authenticated browser or new SMB-fixture acceptance is implied.
- [ ] Read disk SMART attributes, error history, last RAID scrub, snapshot schedule/retention, pool alarms and UPS shutdown behavior. The non-root probe did not produce SMART data.
- [ ] Determine used bytes by data class from existing indices/QTS accounting; do not trigger a whole-collection scan/hash merely to plan.
- [ ] Inventory shares/aliases, NFS/AFP/WebDAV/FTP, QTS application privileges, scheduled tasks, package paths, symlinks, open sessions and every client. The SMB session probe required root and was not completed.
- [ ] Resolve the retired laptop volume and its snapshots/hidden references. Retired share absence alone does not authorize deleting a volume.
- [ ] Export QTS settings, share/ACL configuration, UID/GID/SID mappings, Compose and mount definitions, Plex databases/preferences and library/profile IDs, Arr/Seerr settings, copy receipts and backup selection. Store secrets privately and encrypted.
- [ ] Verify fresh cloud/NAS settings archives and off-host readbacks. Explicitly schedule directory/directory-route, Authelia, home-acme, HA SSL/proxy state, controller CA, Forgejo links and Jellyfin settings/plugins/CA; retain AD SIDs/SYSVOL/trust, MFA database and original encryption/session/OIDC keys. Qualify a current isolated restore rather than repeating initial provisioning.
- [ ] Recheck live HBS source selection, exclusions, latest success and integrity status; restore a small private sample to an isolated location and verify bytes, ownership, ACLs and extended attributes without displaying content.
- [ ] Restore a Time Machine sample and confirm its encryption/recovery credential. Decide whether backing up the entire Time Machine history to B2 remains worth the cost.
- [ ] Establish working backup failure notifications. Authelia's successful Gmail enrollment delivery does not resolve QNAP HBS/Notification Center's earlier failure. Decide client-side encryption and independent deletion-resistant backup policy before introducing more writable remote data.
- [ ] Agree acceptable data loss, service downtime and recovery time per class, including whether private originals have another independent copy.

### Permissions and identity

- [ ] Extend the existing encrypted-SMB3 synthetic matrix for every changed share/group: local and domain roles, list/read/create/rename/delete, private traversal denial, backup/config denial and canonical reader write denial. Preserve both household users' Container/Usenet denial, Michael's Time Machine denial and LDAP-only services' denial on all shares.
- [ ] Test all access routes: SMB, File Station, local container mounts, any NFS export, snapshots/recycle bins, direct Hetzner, and the optional NAS gateway. Hidden share names are not authorization.
- [ ] Verify both existing objects and newly created objects inherit intended group/ACL/mask behavior. Capture exact ACLs before changes; avoid collection-wide chmod/chown.
- [ ] Select the intended private members explicitly, then prove nonmembers and `hass` cannot enter through local or domain paths, including the broad `nas-users` export. Confirm intended users/Plex still work and retain the restricted Plex profile's exact grants to IDs 2/3/4/5 and exclusion of ID 1.
- [ ] Verify service runtime UID/GID, supplementary groups, umask and mounts; ensure no human credentials or deployment admin group are needed for routine jobs.
- [ ] Qualify SMB signing/encryption and removal of NTLMv1 with the actual Mac, Time Machine and other clients; save prior settings and change one control at a time.
- [ ] Record domain-qualified SIDs and effective numeric mappings before ACL changes; distinguish same-named local/domain users, inheritance and nested groups. Recheck QNAP machine trust after each affected change without rejoining it.
- [ ] Test planned group removal/account disablement/password changes across SMB tickets, browser/OIDC sessions, Jellyfin tokens, local compatibility accounts and direct Hetzner credentials; confirm revocation reaches each route and escrow reflects intentional changes.
- [ ] In a separate maintenance window, test HA/DC/SSO/DNS/WAN outage and recovery, including new versus existing sessions, directory-route startup before Authelia and local emergency access. Never activate the retired NAS DC. Consider a second independent DC only as separately scoped availability work.

### Paths, storage and writable remote mounts

- [ ] Record each source → destination mapping, filesystem/device identity, required space/reserve, writer, reader, backup and rollback reference before any move.
- [ ] For same-volume renames, require absent destination and compare device/inode afterward. For a justified cross-volume move, preserve metadata/hardlinks, verify the moved data, and retain the old source until acceptance.
- [ ] Keep TV staging and publish locations in the same bind/filesystem for atomic rename. Preserve manifests and ownership receipts; do not adopt unrelated files into eviction ownership.
- [ ] Keep NAS 100 GiB reserve, cloud 30 GiB reserves, 100 GiB release limit, current repair volume and retired-worker disablement.
- [ ] Test startup with storage unavailable and reconnect after interruption: refuse dependent work, preserve mode-0000 unmounted cloud directories, prevent writes into empty local mountpoints, and do not empty Plex trash.
- [ ] Verify FUSE/shared-mount propagation, remount behavior and dependent-container visibility using a pilot before any production mount move.
- [ ] Test writable remote large-file transfers, checksum readback of synthetic files, interrupted copy, rename/replace, hardlink behavior, filename/metadata semantics, concurrent users, full destination/cache and laptop sleep/wake.
- [ ] Verify server-side reader denial remains effective and new writers cannot reach backup/config roots. Test QNAP AD group enforcement on the gateway; record the separate direct-human and gateway-service credentials, roots and revocation. AD logout/disablement must not be mistaken for provider credential revocation.
- [ ] Define manual managed-media reconciliation: native records, manifests, link relationships, NAS receipts and both media servers agree after each operation; no unexpected downloads or deletes.

### Application and household acceptance

- [ ] Before each cutover, check downloads/postprocessing/imports, manual pauses, NAS transfers, Plex/Jellyfin sessions, Time Machine and HBS activity. Preserve active work and stop only affected services.
- [ ] Compare Plex library IDs/roots, profile grants and private visibility before/after. Keep automatic trash emptying disabled. Test actual household TV clients and owner/restricted profiles privately.
- [ ] Verify Jellyfin's existing user ID/`ryan` alias, LDAPS trust, disabled automatic user/admin creation, library policy, Moonfin request link and local recovery admin. Complete actual TV/native-client sign-in/playback after directory migration; recheck scans/transcoding/GPU access after storage/runtime changes, with private media still absent.
- [ ] Complete the still-pending human Arr/Catalog HTTPS MFA/OAuth flows; retain Catalog's owner-only actions, Arr group/gateway checks and anonymous API denial. Verify native Seerr requests/availability, Arr mappings/history, copy/evict receipts, Filex quarantine and held jobs without enqueuing downloads just to audit.
- [ ] Verify DNS, wiki and Forgejo SSH/HTTPS clone/fetch after application-volume/UID changes; preserve Forgejo's linked user and repository IDs. Test recovery management independently of HA browser SSO. Retained LAN HTTP/ports/ingress remain separate access boundaries.
- [ ] Record the Mac's actual SMB account realm and verify Time Machine continues the existing backup chain with a sample restore. Successful domain SMB fixture access does not prove the active backup migrated from its local account.
- [ ] Confirm HBS still selects the exact intended sources after every share/path change; exclude remote mounts, caches and staging; preserve existing B2 history. Check incremental behavior before allowing an unexpected full re-upload.
- [ ] Perform a controlled restart/reboot and outage test only in its maintenance phase, then verify all mounts, credentials, service dependencies and backup schedules. A healthy container alone is insufficient.
- [ ] Record acceptance and rollback evidence without media names/IDs in Git. Update canonical runbooks, inventory and recovery supplements; keep original bound snapshots immutable.

## Decisions to settle before implementation

The user has chosen writable laptop access including managed media. Identity
selection and hosting are complete: use existing Samba AD/Authelia on HA and
QNAP domain membership. Remaining choices are intended private-library members,
the recovery/downtime budget, whether the NAS gateway passes writable-filesystem
qualification and direct access is also wanted for travel/recovery, and whether
capacity pressure justifies a later physical redesign. A second DC is optional
availability work, not a prerequisite for share cleanup.

Start with the recovery/permission pilot. The observed broad private-root grants
and shared deployment/runtime identity offer a clearer immediate benefit than
rebuilding a functioning RAID group.
