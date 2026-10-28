# NAS storage and access improvement plan

**Later October 27 wiki-only exception:** see the [named-share migration ledger](nas-wiki-share-migration-2026-10-27.md). The user authorized the wiki move and its necessary repository backup-worker mount change after independent recovery verification. General NAS readiness gates remain closed; HBS is unchanged.

**October 27 application checkpoint:** the [bounded service inventory and migration
ledger](nas-service-inventory-2026-10-27.md) reconcile current NAS/cloud runtimes,
HA consumers and recovery streams. Start with its wiki preparation/rehearsal
pilot, keeping identity and path cutovers separate. Production moves remain
blocked: the user confirms no later disk-2 repair or power qualification, UPS is
still disabled, and retained snapshot recovery remains unqualified. Fresh reads
also found stale Forgejo/cloud recovery and unhealthy DNS discovery. The
[backup repair follow-up](../usenet-infra/docs/backup-repair-2026-10-27.md) now
records fresh verified off-host archives for both services and restored Forgejo
scheduling after an approved capture stop. Subsequent unattended captures and DNS
discovery diagnosis remain prerequisites for dependent cutovers.
The current HBS seed belongs to concurrent backup work and must remain undisturbed.

Status: storage proposal with an **October 24, 2026 storage baseline**, revised
on **October 25** against the deployed household identity rollout and fresh
read-only directory, QNAP trust/share/ACL, HTTP/TLS and HA backup metadata checks,
then the [NAS preflight](nas-preflight-2026-10-25.md) using SSH and Safari.
These reviews changed no live configuration, credentials, shares, ACLs, media or
disks. The requested laptop access includes **read/write access to managed media
and support for roles with full Hetzner account filesystem access**.

**Samba AD on Home Assistant, Authelia browser SSO and QNAP domain membership are
already deployed.** Preserve that architecture; the original Authentik/backend
selection proposal is superseded by the [household identity runbook](operations/household-identity.md).
The remaining order is recovery coverage, storage authorization, runtime-service
separation, writable remote access, named service/archive and legacy-share data
migrations, and physical pool changes only if justified. Most of the benefit does
not require a pool rebuild. Keep
each cutover independently reversible.

The [shares, accounts and role matrices](plan-nas-access-model.md) define the
proposed authorization model and distinguish it from current grants. The user
has selected **Ryan as private-library maintainer and both Ryan and Michael as
general-media maintainers**. The companion also maps Plex viewer roles per library
and distinguishes native HA backups from NAS/cloud settings and media backups.
It includes owner-scoped personal homes and the existing `usenet-deploy` account's
distinct deployment role, with `svc-nas-deploy` as its migration target under the
`svc-` service-account naming policy.

Every proposed share also has a [B2 backup and redundancy policy](plan-nas-data-protection.md):
schedule, authoritative source, capture method, retention, encryption, restore
checks and eventual storage tier. These are proposed policies alongside the
dated deployed baseline, not new backup jobs or RAID changes.
The target share catalog is flat: `forgejo`, `jellyfin`, `media-control` and other
named datasets replace the proposed `AppData` parent. `forgejo-backups` and
`infrastructure-backups` replace the proposed `BackupArchives` umbrella. These
are real share boundaries with defined service access, not just renamed subfolders.
Retire `FromDrobo` and household use of `Public`/`Multimedia`; remove the latter
shares only where QNAP supports it. Relabel the existing `Scratch` volume
`System`. Required platform roots remain explicit, restricted exceptions under
the [legacy-share retirement phase](#legacy-share-retirement-and-system-label).

The latest preflight resolves the firmware (QTS 5.2.11), home-folder enablement
and current HBS sources. All four disks report Good, but retained logs show
recurring **disk-2 SATA link/I/O errors through October 24**. Investigate these
before production moves or stress tests. The scrub scheduler is **off**, with no
retained completed-scrub record. The main data volume's only snapshot is from
September 2024 with no schedule, the other volumes have none, and UPS support is
disabled. These are readiness gaps, not authorization to start tests or change
settings. Both Public data folders belong to Ryan and
will move to his qualified private AD home. Video Station and Multimedia Console
were [retired on October 25](nas-media-retirement-2026-10-25.md) after encrypted
state preservation. The native inventory found no additional multimedia consumer;
retained-service checks passed within the recorded limits. The Multimedia share
and its contents remain to classify and retire. A scrub was deferred pending
disk-2 diagnosis and recovery review.

## Next bounded change and open follow-up

**October 27: wiki runtime identity preparation implemented locally.** New
`qnap_wiki_uid` / `qnap_wiki_gid` inputs default to the existing shared values.
Publication and rollback pass them through Compose's existing contract. Synthetic
checks cover independent overrides, rejected candidates, retained-identity
rollback and same-release identity changes; unchanged repeats do not restart.
Deployment credentials and production paths are unchanged. The account, narrow
read grants and approved runtime-only switch are now complete within the ledger's
limits. Durable wiki-specific overrides select 1005:1000 and enable reader ACLs.
The scope, checks and rollback remain in the
[wiki pilot](nas-service-inventory-2026-10-27.md#first-pilot-wiki-preparation-then-separate-identity-and-path-checkpoints).

The [wiki recovery/account checkpoint](nas-service-inventory-2026-10-27.md#wiki-preparation-and-recovery-checkpoint)
now records verified off-NAS release preservation and independent source
restore/build. Local `svc-wiki` / `wiki-reader` exist with saved share/application
denials. Actual synthetic file/share-root denials and exact ACL rollback passed.
A separate read grant preserved all old ACL metadata and enabled all current site
reads plus Caddy validation as 1005:1000. The opt-in publisher step repeats only
those read grants on future releases. The live init/Caddy processes are healthy
at 1005:1000, with unchanged content and peer-service start times. Both HTTP ports
and the TLS/MFA redirect passed; a new encrypted controller recovery checkpoint
verified pointers, ACLs, inventory and source bundles. Normal unattended NAS
capture/restore remains open. The runtime identity phase is complete; the
named-share migration remains blocked by the storage gates.

The later [wiki verification follow-up](nas-service-inventory-2026-10-27.md#wiki-backup-and-network-verification-follow-up)
proved that the latest scheduled archives still contain the old runtime and
pre-account native snapshot. Current native settings and the verified wiki
recovery inputs now have an independently downloaded/decrypted manual Hetzner
checkpoint. Valid-credential network checks also passed: SMB refused session
setup before any share connection, and SSH denied the password login. Individual
authenticated share ACLs were not exercised. The next unattended capture remains
separate from the gated named-share move.

**Open future action:** [qualify unattended cloud/Forgejo captures and cron persistence](../usenet-infra/docs/backup-repair-2026-10-27.md#future-actions-unattended-recovery-qualification).
Review after the next eligible normal runs; October 28 after 17:30 Eastern is the
suggested initial review window. This can proceed independently of offline wiki
preparation. Include the new wiki mapping and a native QTS snapshot containing
its account/group in that review; outer archive freshness alone is insufficient.
The later wiki-only exception allowed its named-share checkpoint; next verify the unattended backup cycle. Other service moves still require the storage gates.
Preserve the currently qualified runtime and do not combine it with another
service migration or household cleanup.

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
| Private originals | `/share/FromDrobo/loljk`; Plex library ID 1 | Keep the root unchanged until the explicit migration cutover; preserve files, library ID, metadata, watched state, privacy and offsite backup coverage throughout |
| Optional NAS media copies | `/share/FromDrobo/Movies/video`, `/share/FromDrobo/TV Shows/library` | Copy ownership receipts, exact published paths, staging boundaries and Plex IDs 2/3 |
| Canonical Hetzner media | Existing BX21 Storage Box, 5 TiB; about 61% used | Arr-owned native library, legacy manifests/hardlinks, snapshots and independent settings-backup scopes |
| NAS remote view | Existing read-only rclone/SFTP mount at `/share/FromDrobo/Remote/files` | Server-restricted reader identity, mount propagation, Plex IDs 4/5 and Jellyfin source mounts |
| Playback cache | `/share/FromDrobo/.remote-cache` | Disposable; 20 GiB target, 100 GiB reserve, 24-hour age policy |
| Transfers | `/share/FromDrobo/FilexStaging` | Separate from canonical libraries; verified transfers, quarantine and disabled purge |
| Application state | `/share/Container/usenet`, plus `/share/Container/home-git` | Media apps, DNS, static wiki, Filex, backup configuration and Forgejo state |
| Native packages | Plex, HBS and Container Station on `CACHEDEV1_DATA` | Package installation paths and QTS system configuration |
| Settings archives | `/share/Usenet/Backups/automatic` | Separate confined off-host backup credential and recurring ciphertext readback |
| Other originals | Two selected folders under `Public`, confirmed Ryan-owned; about 9.95 GiB | Move to Ryan's canonical AD home only after isolation and B2 qualification; retain existing source history |
| Personal home folders | Enabled on Scratch; `home=%H`, parent `/share/CACHEDEV1_DATA/homes`; local admin/deployment homes observed | Preserve deployment SSH recovery dependency; human AD homes and isolation unqualified; homes absent from current HBS selection |
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
   a NAS administrator. Media-copy, Filex, DNS and Forgejo containers still reuse
   UID 1004/GID 100. Wiki was separated to 1005:1000 on October 27 while keeping
   deployment ownership unchanged. Their inspected containers do not automatically inherit the
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

The latest read-only preflight found NAS settings status `ok` at **4:16:47 p.m.
Eastern on October 25**, with all three scopes reporting remote ciphertext
verification. Forgejo's receipt reports success and verification at **7:28:35 p.m.
on October 24**. These supersede the earlier status readings; no backup or restore
was triggered by this preflight. Earlier independent settings restores remain
separate evidence in the recovery runbooks.

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

A fresh October 25 read-only HA check confirms **daily native automatic backups,
three-copy retention, and only local HA storage selected**. The latest protected
archive completed at **5:09 a.m. Eastern** and includes Core, all 26 apps (including
AD/Authelia) and `/ssl`; database inclusion is enabled. It excludes `/share`.
No NAS backup mount is configured. The existing `FromDrobo` CIFS mount has usage
`media` and is inactive, so it is not evidence of HA backups reaching the NAS.
Native daily identity coverage therefore exists locally; recurring off-host
coverage and a current independent restore remain to qualify.

Treat `HomeAssistantBackups` as a separate archive destination with its own
writer, replica credentials, encryption/emergency-kit custody and retention.
The on-demand [Talos add-on export](operations/addon-state-backups.md) contains
repository apps plus `/share`, deliberately omits Core and `/ssl`, and is
unencrypted. The age-encrypted identity-specific HA export is another separate
point-in-time artifact. None should be represented as interchangeable with the
native daily backup or the NAS settings archive.

AD, Authelia, the directory route, ACME and the HTTPS proxy now depend on the
same HA host. Loss of HA affects new domain logins and browser SSO. Keep native
local recovery administration, separately reachable management and off-host
backups. Never restart the retired NAS DC or recreate the rejected NAS VM as
an outage shortcut; a future second DC needs supported replication and a
distinct identity/address on a suitable independent host.

The [scheduled-backup runbook](../usenet-infra/docs/scheduled-backups.md) records
B2 coverage for the private originals, two selected Public folders, encrypted
settings archives and the current laptop backup. Fresh October 25 inspection
confirmed those five sources, nightly 02:00/latest-30-version policy and disabled
client-side encryption; homes and Multimedia are absent. Separate maintenance
documented a Good HBS Quick Check, inbox-confirmed QNAP email delivery and an
isolated B2 restore of encrypted Forgejo archives/receipts with byte comparison.
Private-original/ACL and Time Machine restores, actual failure-event delivery
and new per-share policies remain to qualify. Do not infer media recovery from
a settings-file restore; see the [preflight scope and limits](nas-preflight-2026-10-25.md#backup-findings).

## Target storage and namespace

Use purpose and recovery requirements for names. Separate shares, credentials,
backup selection and capacity policy even where data initially stays on one pool.
Names below are proposed. The requested FromDrobo split includes real data
destinations and a separate cutover phase; an alias can be an intermediate step.
Create one share per independently managed dataset/recovery unit, with structured
folders inside it. A share does not require a separate volume, pool or B2 bucket.
Existing household/media names remain stable; new service names use lowercase
hyphens. Default ordinary household SMB access to service/archive shares is denied;
applications use local binds, and human Git access stays inside Forgejo.

| Proposed share / area | Purpose | Access | Protection and placement |
| --- | --- | --- | --- |
| `PrivateLibrary` | Private original collection | Ryan maintains; Plex and backup services read; Michael has no private role | Protected tier; Local originals B2 policy |
| `Documents` | Explicitly classified shared originals; no current Public payload assigned here | Named household groups | Protected tier; Local originals B2 policy |
| `home` (Ryan) | Ryan's canonical AD home, including both Public folders after qualification | `home-owner(ryan)` RW; scoped backup reader | Protected tier; Local originals B2 policy; one canonical source |
| `home` (Michael) | Michael's personal space under QTS `homes` | `home-owner(michael)` RW; scoped backup reader | Protected tier; Local originals B2 policy; one canonical source |
| `homes` | Administrative parent of personal home directories | Recovery administrators; backup reads selected homes; no household-wide RW | Same backing volume/tier; Local originals selection covers each home once |
| `MediaCache` | Selective, replaceable NAS movies/TV | Ryan and Michael maintain; playback reads; copy service writes | Disposable tier eventually; Rebuild policy, no B2 media copy |
| `PlaybackCache` | Disposable rclone cache, separate from selected NAS copies | Remote-reader service RW; no human SMB grant | Disposable tier; Rebuild policy; protect configuration separately |
| `RemoteMedia` | Existing read-only canonical media view | Media readers and playback services | Provider-managed redundancy; Rebuild policy; no duplicate backup of the view |
| `RemoteManage` | Read/write canonical media mount | Ryan and Michael through the AD media-maintainer group | Provider-managed redundancy; same Rebuild policy as the read-only view |
| `RemoteFiles` | General writable remote files | Proposed Ryan-owned scope; additional owners undecided | Provider-managed redundancy; Remote originals B2 policy |
| `Hetzner` | Entire Storage Box filesystem, including media, staging, hidden files and backup trees | Explicit full-account R or RW roles; human members not yet selected | Provider-managed redundancy; Mixed by subtree B2 policy, covering each authoritative path once |
| `TransferStaging` | Manual incoming/outgoing files and quarantine | Transfer owner and Filex | Conditional Disposable tier; Transient policy, no B2 while another verified source exists |
| `forgejo` | Repositories, database, LFS/attachments, configuration and keys; existing `Container/home-git` | `svc-forgejo` RW; dedicated capture reader; no household SMB grant | Protected tier; Forgejo recovery B2 policy |
| `forgejo-backups` | Completed encrypted Forgejo recovery archives; existing `Usenet/Backups/automatic/forgejo` | Forgejo backup job RW; archive uploader/recovery readers R; Forgejo runtime denied | Replica tier; Forgejo recovery B2 policy |
| `jellyfin` | Jellyfin database, configuration, plugins and persistent metadata; current `jellyfin-trial` state | Jellyfin runtime RW; scoped capture reader; no household SMB grant | Protected tier; Application recovery B2 policy |
| `media-control` | Catalog/copy state, manifests, receipts and required configuration | Media-copy service RW; scoped capture reader | Protected tier; Application recovery B2 policy |
| `filex` | Filex configuration, host keys and persistent state; payloads remain in `TransferStaging` | Filex runtime uses its state only; scoped capture reader | Protected tier; Application recovery B2 policy |
| `dns` | Resolver and discovery configuration/state, separated by subfolder ACLs | Resolver and discovery roles get distinct scopes; deployment publishes configuration | Protected tier; Application recovery B2 policy |
| `wiki` | Reproducible published site and runtime configuration; source remains in Git | Wiki runtime R; deployment publishes; no runtime write grant | Disposable, conditional tier; Rebuild B2 policy |
| `remote-reader` | Read-only mount service configuration/credentials; no mounted remote content or cache bytes | Reader service has its own scoped state; backend remains R | Protected tier; Application recovery B2 policy |
| `remote-maintainer` | Configuration/credentials for the proposed media-only writable gateway | Media gateway service only; no full-account credentials | Protected tier; Application recovery B2 policy |
| `hetzner-gateway` | Configuration/credentials for the proposed full-account gateway | Full-account gateway service only; ordinary media roles denied | Protected tier; Application recovery B2 policy |
| `backup-control` | Backup scripts, schedules, per-job configuration/credentials and status; distinct job subfolders | Each job gets only its own control scope; recovery administrators | Protected tier; Application recovery B2 policy |
| `infrastructure-backups` | Encrypted NAS/application/cloud recovery artifacts, excluding Forgejo and native HA archives | Infrastructure capture/replica jobs write assigned streams; uploader/recovery readers R | Replica tier; Application recovery B2 policy |
| `HomeAssistantBackups` | Native HA backup archives | Dedicated HA writer, replica reader and recovery operators | Replica tier; HA archives B2 policy; preserve native archive/encryption semantics |
| `SpaceBlackTimeMachine` | Current laptop recovery | Existing local grants plus `SMARTHOME\nas-timemachine`; recovery admin | Replica tier; Laptop history B2 policy; keep name, account realm and existing backup chain |

Forgejo's repositories, database, LFS/attachments and configuration belong in the
same application recovery unit. Its runtime gets `forgejo`, not `forgejo-backups`;
the capture job reads live state and writes encrypted archives, and a separate
uploader reads those archives for B2. The shared Application recovery profile
covers other named service datasets through `infrastructure-backups`, with
per-stream source lists and freshness checks. It is not a settings-only backup.
`dns` and `backup-control` have explicit per-runtime/per-job subfolder ACLs; their
common recovery policy does not grant every participant access to the whole share.

Native Plex/HBS/QTS package paths remain supported non-share exceptions. Preserve
them in the application backup inventory and export to `infrastructure-backups`;
do not move package internals or create an `AppData` replacement to force every
source into a new share. Wiki publication can use Rebuild only after its Git/build
inputs are independently recoverable. New gateway shares are provisioned with
their corresponding gateway, not as empty claims of deployed coverage.

Initially expose `PrivateLibrary` as a QTS-managed share of the existing private
root, if supported by the installed firmware, preserving Plex ID 1 and its source
path. Remove unintended access through the old `FromDrobo` export at the same
cutover: a restricted new share does not fix an accessible old path. Inventory
every alias, NFS export, File Station path, snapshot/recycle view and service mount.
Test preserved local accounts and domain accounts separately. Do not assume that
adding a private AD group removes old local ACEs or the broad `nas-users` grant.
This is an interim permission cutover. The later data-migration phase gives the
private collection its own backing root outside `FromDrobo` while retaining its
Plex library identity and qualified backup history.

Personal `home` views are distinct permission scopes backed by QTS's `homes`
share, not separate per-person pools. Verify whether homes are enabled before
planning a move. Select the actual AD home for each person, map any separate
local-account home explicitly, and test mutual denial plus recovery access.
Enabling home folders can affect both local and domain users; classify any
service homes separately. See the [home policy](plan-nas-access-model.md#personal-homes)
for roles and the backup source map.

The existing internal Hetzner reader also retrieves encrypted cloud backups.
Human-facing `RemoteMedia`/`RemoteManage` must expose only approved media roots,
not all of `catalog` or `library`; those parents also contain backup or acquisition
staging. Preserve the internal reader's existing consumers while qualifying the
new narrower exports and separately confined writer credentials.
The separate `Hetzner` export intentionally exposes the complete account to its
full-account roles, including remote copies of backups. These broader grants
override the protection afforded by narrower remote views for those members.

Pilot permissions before moving data. Relabel `Scratch` to `System` through
QTS's volume-alias control in a separate checkpoint; preserve the existing volume,
QTS-managed `CACHEDEV*` identifiers, mount paths, package state and RAID layout.
The [FromDrobo migration](#fromdrobo-data-migration) separates originals, selected
copies, transfer staging and playback cache into independent share roots. Prefer
same-filesystem renames, with private originals moved only after their recovery
and consumer gates pass. No recursive collection copy/hash/chmod is needed merely
to plan this. Moving the remote view requires its own mount/service cutover.

Keep the current RAID-5 pool initially. It already has substantial unallocated
thin-pool space, and all four bays are occupied. If more capacity is needed,
compare upgrading the smallest disk through QTS's supported expansion workflow
against a full rebuild or separate cache hardware. A nominal 4 TB replacement
could eventually remove the smallest-disk constraint, but capacity gain and safe
expansion depend on hardware health, model support, backups and the actual QTS
workflow; no purchase or disk change is proposed for the first phase.

If a future rebuild is justified, use the per-share storage tiers to place
originals/apps on a protected pool and disposable data on independent single-disk
storage. Backup-replica shares can also become single-disk candidates after source
availability and independent B2 recovery pass their gates. Different shares or
volumes within the existing pool do not change redundancy. Avoid making multiple disposable disks one
RAID-0/JBOD failure domain without a specific capacity reason. The key decision is
acceptable re-download time and downtime, not whether replaceable files deserve
another copy. Cache replicas still consume capacity even without RAID redundancy.

## Hetzner access from NAS and laptop

**Preserve the current NAS read-only mount and add a distinct maintainer path.**
Keep the Plex/Jellyfin reader and NAS-copy backend read-only. Provide both scoped
media/file roles and separately assignable `hetzner-account-readers` /
`hetzner-account-maintainers` for the entire account. Media-only roles exclude
backup/configuration trees; full-account roles intentionally include them.
Full-account RW is filesystem access, including stored credentials, not Hetzner
Console billing/resource administration or local NAS administrator access.

| Route | Benefit | Cost / limit | Proposed role |
| --- | --- | --- | --- |
| Laptop → Hetzner SMB3, encrypted | Native Finder filesystem; no dependency on NAS/HA uptime or home uplink | Separate provider credential and revocation; macOS must negotiate encryption; WAN/interrupted-write tests required | Optional direct route with explicitly selected scoped or whole-account credentials; current main-account SMB/network settings need qualification |
| Laptop → NAS SMB → separate Hetzner writable mount | Existing QNAP AD membership enforces household groups; provider credentials remain on NAS | NAS, HA directory and home uplink dependencies; remote sees gateway identity; re-export/locking/durability need qualification | Preferred LAN target after a synthetic writable-gateway pilot passes |
| Laptop → encrypted SFTP filesystem client | Uses scoped key and host pin; avoids WAN SMB reachability issues | Requires a supported filesystem client; Finder alone is not an SFTP mount | Fallback if direct SMB cannot meet requirements |

Hetzner supports confined subaccounts and SMB/SFTP access. Its documentation
explicitly says SMB may be unencrypted without additional configuration. Verify
SMB3 encryption on the actual Mac connection; use provider hostnames and a
credential matching the selected role. Hetzner documents whole-directory access
for the main user and subtree access for subaccounts. Existing Terraform disables
main-account external reachability and SMB; a whole-account gateway needs an
approved cloud/VPN transport or an explicit network-settings change during its
pilot. A confined reader cannot stand in for a full-account backend. [Hetzner subaccounts and
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
uses separately tracked Hetzner credentials/keys and bypasses QNAP's group decisions;
AD disablement does not revoke it. Keep a credential/root/revocation inventory,
preserve the server-enforced read-only playback account, and deny backup roots to
media-only writers. Full-account roles can read or modify remote backup files;
a separate prefix is not a denial boundary for them. NAS SMB remains LAN/VPN-only.

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
real maintenance operation. Preserve disabled automatic upgrades, the approved
native Arr RSS policy and existing request scope; direct SAB RSS remains disabled.

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

Adopt **`svc-<purpose>`** for managed non-human logins whose names we control.
Keep human identities, permission-role names, existing compliant service names
and required vendor/provider principals stable. Record unsupported renames as
explicit exceptions; the prefix alone grants no permission or process isolation.
The [naming policy](plan-nas-access-model.md#service-account-naming-policy) and
[account migration](plan-nas-access-model.md#service-account-migration) cover the
full inventory, legacy `hass`, Filex application logins, shared runtime UID 1004,
provider labels, consumer updates, verification, retirement and rollback.

Keep the existing groups and add narrowly scoped storage groups in AD only
when their share pilot is ready. Proposed additions are not current grants:

| Group / principal | Intended rights |
| --- | --- |
| Existing `nas-users` | Preserve approved FromDrobo/Public/Multimedia compatibility; progressively replace broad storage grants after equivalent narrower access passes |
| Existing `nas-timemachine`, `nas-multimedia-writers` | Preserve Ryan's Time Machine scope; retain Michael's Multimedia compatibility until replacement access passes, then retire obsolete grants; do not repurpose these groups |
| Existing `git-users`, `arr-users` | Browser application access only; no implied NAS, private-media or backup rights |
| New `private-media-readers`, `private-media-maintainers` | Ryan maintains; scoped Plex/backup access reads; Michael has no private role; never automatically nest `nas-users` |
| New `media-readers`, `media-maintainers` | Playback reads; Ryan and Michael maintain local/general media and the separate remote-management path |
| New `hetzner-account-readers`, `hetzner-account-maintainers` | R or RW on the entire Storage Box filesystem; human membership selected independently of media roles |
| New household document groups | Access only to designated shared/original areas |
| `home-owner(person)`, `home-backup-reader` | QTS owner ACLs grant RW only to that person's home; a separate backup role reads explicitly selected homes |
| New `backup-operators` | Backup monitoring and isolated restore; source read and destination write scoped separately |
| New `ha-backup-writer`, `ha-backup-readers` | Native HA archive destination and replication-source access; no media or NAS-settings-source access |
| New `b2-backup-writer(scope)`, `b2-restore-readers(scope)` | Separate destination upload/retention and recovery roles per B2 job; no implicit rights from Hetzner data roles |
| Proposed `svc-media-copy`, `svc-remote-reader`, `svc-remote-maintainer` accounts | Separate local-copy, canonical-read and gateway-write roles; inventory existing credentials before provisioning anything |
| Proposed `svc-hetzner-gateway`, `svc-ha-backup`, `svc-ha-backup-replica` | Full-account gateway, HA-only NAS writer and HA archive replication; separate backend credentials/scopes |
| Proposed `svc-forgejo-backup`, `svc-archive-b2`, `svc-hetzner-backup` | Consistent Forgejo capture, verified Forgejo/infrastructure artifact upload and remote-originals backup; separate source and destination roles |
| Per-service DNS/Git/wiki/Filex/playback/backup identities | Only required config/state and explicit media roots; noninteractive where QTS supports it |
| `nas-deployment-operator` | Existing local `usenet-deploy`; target `svc-nas-deploy` after migration gates pass; administrator capability for NAS deployment, separate from runtime and recovery roles |
| Existing `svc-authelia`, `svc-jellyfin` | Dedicated directory lookup identities; preserve no administrative or NAS-share access and no password-write delegation |
| Local emergency administrators | Existing QNAP, Forgejo and Jellyfin recovery identities; independent of Authelia/directory availability |

Keep `usenet-deploy` as the distinct NAS deployment principal; QTS SSH required
administrator membership at bootstrap. Its role remains technically able to
override data ACLs. First move application runtime ownership away from UID 1004;
then qualify a supported rename to `svc-nas-deploy` without changing
UID/GID/SID, access keys or host trust. Inventory connection targets, per-service
ownership variables, jobs, login homes and recovery inputs before any change.
Keep a separately tested local recovery login. The [deployment identity plan](plan-nas-access-model.md#nas-deployment-identity)
defines dependencies and rollback; a new label alone provides no isolation.
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
| 0. Recovery and baseline | Investigate disk-2 link/I/O errors and review older disk faults before production moves/stress tests; qualify disk, scrub/snapshot and UPS readiness; current exports, per-share B2 policies and encrypted-job pilots; recurring off-host identity/Jellyfin coverage; B2/Time Machine restores and alerts; pending human acceptance | Isolated restores; preserve current disks/logs, existing B2 history, identity keys and current AD/Authelia databases |
| 1. Permission pilot | Synthetic share and owner-home tests using narrow AD groups/ACLs; local/domain effective-access matrix; verify emergency admin | Remove only pilot grants/share; do not delete/recreate existing accounts or groups |
| 2. Private isolation | Remove unintended local/domain access through every route; introduce clear share alias; preserve Plex source/ID | Restore exact saved ACL/share policy if authorized access or playback fails; do not roll back the domain join |
| 3. Service-account migration | Apply the `svc-` policy; move one runtime at a time off shared UID 1004, migrate legacy integrations, then the deployment login; retain explicit platform exceptions and recovery access; verify exports before retiring old logins | Restore the affected identity, UID/GID/SID, ACLs and consumer settings; reconcile new writes; preserve domain trust and unrelated services |
| 4. Writable remote access | Qualify AD-authorized NAS gateway; separately scoped direct route if needed; keep playback read-only and managed edits reconciled | Unmount/revoke only new writer routes; preserve existing domain and read-only playback mount |
| 5a. Service-data and archive migration | Split owned `Container` data into named service shares; split archive outputs into `forgejo-backups` and `infrastructure-backups`; update mounts, role ACLs, capture inputs and HBS sources; retain native package paths | Restore that service/job's saved paths and permissions, reconcile writes, reverse a same-volume rename or use the retained cross-volume source; preserve backup history |
| 5b. FromDrobo data migration | Execute the source/destination map below in small cutovers; move local data into independent share roots, relocate the remote mount, qualify homes and remove the overloaded export after acceptance | Reverse same-volume rename and saved references, or switch back to retained cross-volume source after reconciling new writes; no dual writers |
| 5c. Legacy-share retirement and system label | Classify/migrate all Public and Multimedia contents; retire household use, remove supported unused exports, record required QNAP exceptions, and relabel Scratch to System; complete final cleanup checks | Restore affected share definitions/ACLs, supported application configuration and saved references after reconciling writes; reverse only the alias for a label regression; retain data and B2 history |
| 6. Identity continuity and acceptance | Repeat Arr/Catalog browser and TV/native-client acceptance after changes; verify account lifecycle, HA outage recovery and recurring backup restore | Revert only the affected storage/service integration; retain current account IDs, MFA keys and domain trust |
| 7. Optional pool redesign | Place each share on backing storage meeting its redundancy tier; verify B2 coverage, source availability and evacuation before a reduction; disk-level runbook | Rebuild has no instant rollback: retain verified external source until full restore and acceptance |

Allow each changed service and backup to complete its normal cycle before the
next phase. Keep disk layout, group/ACL changes and media path migrations in
different maintenance windows. A regression in privacy, file identity, backup
coverage or application ownership stops progression.

## Service-data and archive migration

The [October 27 inventory](nas-service-inventory-2026-10-27.md#nas-application-boundaries)
now maps current principals, mounts, source/credential references and backup
consumers. Its [wiki pilot](nas-service-inventory-2026-10-27.md#first-pilot-wiki-preparation-then-separate-identity-and-path-checkpoints)
is the first recommended application checkpoint. A successful offline rehearsal
will not qualify production storage health or QNAP effective access.

This is a separate path cutover after the relevant identity/ACL pilot. Keep
container-internal paths stable where possible; change the resolved host binds,
deployment inputs and backup inventory together. Names below are target shares,
not commands or assumed existing paths. Resolve exact private source paths and
backing device IDs first, especially where current state/configuration is mixed.

| Current source / boundary | Target share | Dependencies and acceptance |
| --- | --- | --- |
| `/share/Container/home-git` durable data/configuration and deployment inputs | `forgejo` | Preserve internal layout, repository/user IDs, DB, LFS/attachments, secrets and SSH identity; update Compose and stopped-state capture source together; test clone/fetch/push with a synthetic repository and OIDC/recovery login |
| `/share/Usenet/Backups/automatic/forgejo` | `forgejo-backups` | Preserve archive bytes, status/pending-upload references, readback, producer retention and historical B2/Hetzner recovery; runtime denied; update scheduler output and uploader/HBS selection |
| `/share/Container/usenet/jellyfin-trial` durable configuration/plugin/metadata state | `jellyfin` | Preserve user/library IDs, LDAPS CA and plugin settings, GPU/device access and container paths; distinguish cache/transcode data and prove a consistent export/restore |
| Catalog/copy state, manifests, receipts and required config under `/share/Container/usenet` | `media-control` | Inventory exact shared state subpaths; preserve copy/evict ownership and journals; source media and staging remain in their dedicated shares |
| Filex SFTP keys/configuration and durable application state under the current service root | `filex` | Preserve application login/host key and bindings; transfer payloads remain in `TransferStaging`; do not combine this move with a login rename |
| Resolver/discovery configuration and state under the current service root | `dns` | Map resolver/discovery subfolders and inherited ACLs; preserve generated config flow, discovery state and startup dependency; test resolution before retiring old binds |
| Existing wiki publication root under `/share/Container/usenet/wiki` | `wiki` | Redeploy from verified Git/build inputs; runtime R, publisher controlled; verify canonical HTTPS and recovery routes; preserve unique inputs separately if found |
| Remote-reader config/key/known-host references; new gateway state when provisioned | `remote-reader`, `remote-maintainer`, `hetzner-gateway` | Separate backend credentials by service; update read-only/privileged-helper mounts; keep FUSE data mounts and `PlaybackCache` outside recursive capture |
| Backup definitions, scripts, recipient/configuration, schedules and status inputs | `backup-control` | Inventory each job's private subfolder, key references and scratch; update cron/capture/uploader bindings without exposing another job's credentials; never move recovery escrow into this share |
| Remaining verified NAS/application/cloud streams in `/share/Usenet/Backups/automatic` | `infrastructure-backups` | Preserve per-stream artifacts and status; exclude the already-mapped Forgejo stream and native HA archive destination; qualify currently missing application exports |
| Native Plex, HBS and QTS package paths | Stay at supported locations | Keep required package/Container roots; capture through supported exports into `infrastructure-backups`; no generic service-data share |

1. **Baseline and recovery.** Record exact source-to-destination roots, all local
   binds and SMB/NFS aliases, current/target owner identities, ACLs, open consumers,
   available space and rollback references. Inventory executable paths, shared
   libraries/tools and credential mounts separately from mutable state; avoid
   duplicating untracked configuration without an authoritative owner. Verify
   existing restore points before moving authoritative data.
2. **Prepare the service boundary.** Create QTS-managed destination definitions
   and test role-specific allow/deny rules with synthetic data. Avoid broad
   parent binds, including the backup container's current whole-service-root bind.
   Replace them with enumerated sources/exports. Keep native package paths stable.
   Account migration and path migration get separate checkpoints and windows.
3. **Cut over one service or archive stream.** Finish pending backups/transfers,
   then pause only the affected writer/scheduler. Prefer a same-filesystem rename
   into an absent destination, verifying device/inode and metadata. For a justified
   cross-volume copy, preserve ACLs/ownership/xattrs/hardlinks, verify copied bytes
   and retain a frozen old source. Save and update Compose, Ansible/durable inputs,
   cron, source-export lists and HBS selections as one reviewed mapping. Archive
   payload relocation must not lose pending-upload/status references or silently
   reset retention; keep status in its job's `backup-control` scope where supported.
4. **Prove application and backup behavior.** Restart only the affected service;
   test authorized actions and cross-service/household denial, new-file ownership,
   one normal capture/upload cycle and isolated restore from both old and new
   history. Verify Forgejo's whole application, not only a Git clone. Verify DNS
   and wiki recovery routes before dependent cutovers. Price any B2 full re-seed
   before changing jobs, and retain old selection/history until new coverage passes.
5. **Accept or roll back.** Reconcile post-cutover writes before reversing paths
   and saved configuration; do not leave two active writers. Remove obsolete
   broad aliases and binds only after their last consumer is accounted for.
   Keep old cross-volume data/checkpoints through explicit acceptance. Retire
   only emptied, unreferenced service subtrees; never delete `Container` or
   `Usenet` wholesale while required package or unclassified data remains.

Record accepted roots and restore-path translations in canonical runbooks and
encrypted recovery supplements. Older snapshots remain immutable; restore them
with the accepted mappings rather than redeploying their former shared paths.

## FromDrobo data migration

The end state is multiple QTS-managed local share roots, with separate ACLs,
backup selections and future placement policies. `FromDrobo` is a temporary
compatibility name, not the permanent parent of every new share. Start on the
existing volume/RAID group; a later move to lower-redundancy storage is phase 7.
Proposed `/share/<name>` destinations below are QTS share paths; resolve their
actual backing directories/device IDs before implementing any rename. Do not
hand-edit QTS's share symlinks or assume that creating an alias moves data.

| Current source | Proposed destination / operation | Consumers and protection to carry across |
| --- | --- | --- |
| `FromDrobo/loljk` | Real `PrivateLibrary` root outside `FromDrobo`; prefer same-filesystem directory rename | Plex ID 1, Ryan's access, private-reader ACLs, HBS Local originals selection/history; retain original path until this cutover passes preflight |
| `FromDrobo/Movies` and `FromDrobo/TV Shows` | `MediaCache/Movies` and `MediaCache/TV Shows`, preserving their internal layout | Plex IDs 2/3, Jellyfin, catalog copy/evict paths, manifests and owned-file receipts; keep each staging/publish pair on one filesystem/bind |
| `FromDrobo/FilexStaging` | Real `TransferStaging` root | Filex runtime/SFTP paths, quarantine, pending transfers and purge policy; any sole-copy original gets protected classification before relocation |
| `FromDrobo/.remote-cache` | Service-only `PlaybackCache` root | Remote-reader cache path, 20 GiB target, 100 GiB NAS reserve and 24-hour age policy; cache may be rebuilt after clean shutdown, configuration is backed up |
| `FromDrobo/Remote/files` | Recreate the internal read-only mount at a service-owned mountpoint outside `FromDrobo`; expose only media leaves through `RemoteMedia` | Plex IDs 4/5, Jellyfin, copy backend, encrypted cloud-backup reader, FUSE propagation and startup guards; **do not copy remote contents as local data** |
| Any other `FromDrobo` subtree | Classify owner/source first, then explicitly map to a home, `Documents`, application state or another reviewed destination | Nothing is automatically disposable, shared or owned by the copy/eviction service; unknown contents block retirement of the old root |

The internal remote reader remains broader than its human-facing media view
because it retrieves cloud settings archives too. Put its new mountpoint outside
all recursive local backup selections, retain that archive consumer, and qualify
`RemoteManage`/`Hetzner` independently. Do not move or recursively traverse a live
FUSE mount, or include it in a copy of the old parent. `Container` service data
and `Usenet` archives follow phase 5a above; the FromDrobo split
does not relocate QTS packages, AD or Time Machine as a side effect.

1. **Inventory and dry run.** Use existing indices/accounting first. Privately
   record each canonical source/destination, device/inode, owner UID/GID/SID, ACL
   inheritance, xattrs, hardlink relationships, sizes/reserves, writers, readers,
   backup selection and rollback reference. Classify unrecognized data without
   publishing filenames. Include `.env`/Ansible paths (`qnap_data_root` and
   `qnap_catalog_cache_dir`), generated bind mounts, copy receipts, Plex/Jellyfin,
   Filex, HBS, cron, user mounts and HA's currently inactive FromDrobo media mount.
   Prove the procedure with synthetic directories before touching originals.
2. **Prepare destinations and recovery.** Save consistent settings and a verified
   protected-data recovery checkpoint. Prove independent B2 restoration, budget
   a possible source-path re-seed, and define the maintenance/rollback window.
   Create QTS share definitions and ownership in an order compatible with the
   chosen rename; the rename's actual destination must be absent, not an existing
   populated share root. Validate destination ACL inheritance with fixtures.
   Do not overwrite a QTS-created root or copy its permissive defaults over data.
3. **Move one data class at a time.** Start with qualified staging/cache, then
   selective media copies; private originals follow only after those cutovers and
   their own restore/privacy gates pass. Check active transfers/imports, manual
   pauses, playback, Time Machine and HBS first. Quiesce only affected writers,
   scans and backup jobs; keep Plex automatic trash emptying disabled. Same-volume
   renames retain inodes/hardlinks: verify device/inode and recorded metadata.
   Use a cross-volume copy only for an explicitly justified placement change;
   preserve ownership/ACLs/xattrs and link groups, verify copied bytes in the
   approved migration scope, perform a final writer-frozen delta, and retain the
   original source. Do not hash or recursively rewrite the entire collection
   merely to relabel it. Never allow both locations to accept independent writes.
4. **Switch consumers and protection together.** Update paths in existing Plex
   libraries rather than deleting/recreating libraries; preserve IDs, metadata,
   watched state and profile grants. Carry copy manifests/receipts and supported
   path mappings forward without adopting unrelated files or enabling downloads.
   Update HBS sources/exclusions while retaining old recovery history, then prove
   new-path backup/restore. Relocate the remote mount in its own maintenance
   window, checking propagation, absent-mount guards, read-only provider access
   and every media/settings reader. Temporary old-path aliases must enforce the
   same ACLs and cannot restore broad `FromDrobo` access to private data.
5. **Accept and retire.** Test read/write and denial for both humans, services,
   local/domain identities and alternate access routes; verify new-file ACLs,
   library counts/IDs and private playback on household clients without emitting
   titles. Complete normal application and backup cycles, historical/new-path
   restores and the relevant outage tests. Record any writes since cutover before
   rollback: reverse a same-volume rename with its saved configuration, or
   reconcile changes before switching to a frozen cross-volume source. Retire
   the old export and obsolete references only after every subtree and consumer
   is accounted for. Retain cross-volume source data/checkpoints until explicit
   acceptance and a documented retirement decision; preserve B2 history.

Personal homes are a separate cutover within this phase after their inventory.
They are enabled on Scratch and required for deployment SSH recovery. Map local
and domain homes by identity and owner before merging anything; use a conflict
report rather than overwriting same-named files. Qualify owner isolation and
QTS-generated ACLs with fixtures before placing personal files in human AD homes.
Keep unique data in old homes protected, verify each owner's AD access and the
other user's denial, and add the canonical roots to B2 before retiring local-home
compatibility. Do not move either person's data into a generally shared folder.

Phase 5b is complete only when the data classes have independent real roots,
all consumers and backup sources use the accepted mapping, and the overloaded
`FromDrobo` export is retired. An interim private alias alone is not completion.
Update canonical runbooks and durable controller/recovery supplements at cutover,
including the accepted new cache paths; do not rewrite immutable old snapshots.
An old recovery snapshot must be reconciled to the accepted path map before any
redeployment, never silently restore the previous FromDrobo layout.

## Legacy-share retirement and System label

Phase 5c finishes the legacy layout after destination roles and backup policies
are qualified. It does not authorize deleting unknown files or removing an
application merely to shorten the share list. Keep the dated baseline above;
record the accepted new layout separately after implementation.

### QNAP exceptions and final disposition

QNAP's September 2026 guidance says `Public` is required and cannot be removed.
It documents removal of `Multimedia` through the Multimedia Console dependency
workflow, including uninstalling that application on QTS 5.0 and later. Verify
the installed firmware and application dependencies before applying that workflow.
[QNAP default-share removal](https://www.qnap.com/en-us/how-to/faq/article/how-can-i-remove-the-default-shared-folders-on-my-nas).

| Existing object | Final disposition | Exception / completion gate |
| --- | --- | --- |
| `FromDrobo` | Retire the export and obsolete references after phase 5b | Every subtree/consumer accounted for; no permanent catch-all alias |
| `Public` | Retire household storage and ordinary access; retain the minimal required platform root | Empty of household data, with only inventoried system-required contents/grants; do not force-delete or rename the default root |
| `Multimedia` | Move classified contents and remove the unused share through supported QTS controls | First prove Multimedia Console and its dependents are unnecessary or have supported replacements; otherwise retain only the documented required scope, with ordinary access removed where possible |
| `Scratch` volume | Rename its display alias to `System` | Same backing volume, system designation, mount paths, shares, snapshots and RAID; no `/share/System` export is implied |
| Required native package/Container paths | Retain supported platform locations after phase 5a extracts owned service data | Enumerate actual package requirements and protection; never remove the parent wholesale |
| `home` / `homes` | Keep the chosen owner-scoped home service | Do not disable homes as part of default-share cleanup; preserve Time Machine separately |

October 25 decisions and evidence: the two Public data folders are Ryan's private
files, destined for his canonical AD home after privacy/backup qualification.
Public's cached total is 9.95 GiB. Multimedia has Samples and system metadata
(2.09 MiB cached); contents still need classification. Video Station 5.8.9 and
Multimedia Console 2.11.2 were confirmed unused and then removed through App Center
on October 25, with an encrypted archive of application state preserved off-NAS.
No container bind or host crontab reference to Public/Multimedia was found.
The follow-up read-only dependency check found zero Video Station content sources,
videos and used bytes, an enabled but empty/completed multimedia index, and no
additional installed multimedia consumer in the suite/package inventory. Plex,
HBS and Container Station startup scripts have no direct references to the two
apps. The removal confirmations named no additional consumer. Plex availability,
HBS status, container/backup health and File Station root browsing passed after
retirement; media previews, downloads and client playback remain unqualified.
Classify Samples/system metadata before deleting the share. See the
[preflight evidence](nas-preflight-2026-10-25.md#share-inventory-ownership-and-platform-dependencies)
and [retirement receipt and recovery limits](nas-media-retirement-2026-10-25.md).
Homes are an evidenced platform dependency for the dedicated deployment SSH key,
not an optional default share to disable during cleanup.

Maintain an exception register with the exact share/path, platform or application
requiring it, firmware/package version and supporting evidence, responsible owner,
required principals/operations, data class, backing volume, B2 policy/source,
restore evidence and a next-review trigger. `Public` is a documented platform
exception; the Container Station protected-share registry also requires Container.
Multimedia share removal and the remaining client/preview acceptance remain pending. Unknown
contents or untested access are unfinished work, not an accepted exception.
Any required ordinary-user access must be explicitly approved and scoped; broad
legacy grants do not become permanent merely because a root is retained.

### Data cutover and retirement

1. **Classify all contents and consumers.** Inventory Public/Multimedia roots,
   hidden files, recycle bins and snapshot access privately, using existing
   accounting first. Resolve ownership before selecting destinations: personal
   originals to the owner's home (both current Public folders are Ryan's), shared originals to approved `Documents`
   scopes, private-library content to `PrivateLibrary`, and only proven replaceable
   copies to `MediaCache`. Map service state/archives to their named shares.
   If no existing dataset fits, define its owner, roles and protection before
   adding one. Never classify by the old share's name or assume media is replaceable.
2. **Prepare recovery and path changes.** Record every client mount, app/library
   root, indexing source, task, HBS selection, alias and credential consumer.
   Agree destination roles without copying broad legacy ACLs; preserve ownership
   and retain the ACL export for deliberate reconciliation. These shares currently
   live on the system volume, as does the enabled homes root. Ryan's home move
   may stay on that filesystem, but verify actual resolved AD paths and device IDs.
   Moves to the main data volume are cross-filesystem copies. Apply the copy/verification,
   writer-pause and rollback gates above. Protect unique data before relocation;
   the two existing Public backup selections do not cover every original.
3. **Cut over and prove recovery.** Move one classified subtree at a time, update
   consumers and backup selections, then verify household/application behavior,
   private-data denial and a normal backup cycle with old/new-path restores.
   Preserve existing IDs and source history. Retain frozen old sources/checkpoints
   through acceptance, reconcile new writes before rollback and avoid dual writers.
4. **Retire ordinary access and supported exports.** Remove obsolete local/domain
   grants, mounts, bookmarks, aliases and application defaults after their replacements
   pass. In particular, review `nas-users`, `nas-multimedia-writers` and local
   compatibility grants; do not delete groups with other consumers. Remove an
   unused Multimedia export only after its supported dependency gate passes.
   Preserve Public's required root and any verified native principals. Use QTS
   controls, not manual deletion of share symlinks or configuration entries.
   Do not combine share removal with a delete-underlying-data option; source-data
   disposal gets a separate recorded acceptance after recovery/rollback gates.
5. **Restrict required remnants.** Remove ordinary access as qualified and hide
   retained platform-only shares from browsing where supported. Test direct-path
   SMB, File Station and other enabled protocols; hiding is not an access control.
   Use the exception register for any retained app/data dependency and verify it
   still works. Preserve administrative recovery without blanket deny rules that
   also block required system principals. Check that updates/restores do not
   recreate broad defaults or make retired shares active again.

### Relabel the system volume

Record the existing alias, volume ID/UUID, system designation, device/mount paths,
share bindings, snapshot schedules and package locations. Confirm `System` does
not conflict with another volume alias. Use **Storage & Snapshots → select the
volume → Manage → Actions → Rename Volume Alias**. The read-only Safari inspection
confirmed this control for Scratch on QTS 5.2.11 and found no System alias among
the four volumes; no rename was submitted. Recheck the baseline at cutover.
[QNAP volume-alias procedure](https://www.qnap.com/en-us/how-to/faq/article/how-do-i-rename-the-volume-alias).

Change only `Scratch` to `System`, then compare the saved identifiers, bindings
and schedules and check affected applications/backups. Update active inventory,
monitoring labels and recovery mapping without rewriting dated evidence. A label
regression rolls back by restoring `Scratch`; never recreate, move or format the
system volume to rename it. If the supported control is unavailable, leave the
volume intact and record the relabel as blocked pending a supported method.

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
- [x] Inspect native HA backup schedule, selected agents, latest archive component metadata and Supervisor mounts on October 25: daily local-only protected backup, Core/all apps/SSL included, no NAS backup mount; no backup or restore was triggered.
- [x] Read all four disk-health/SMART panels, current RAID counters, pool alarms and snapshot coverage in October 25 preflight: all disks Good; disk 2 SATA counter 13; main volume one September 2024 snapshot/no schedule; other volumes none; UPS support disabled.
- [x] Inspect retained disk/RAID event and kernel history: distinguish the old slot-2 bad blocks from its August replacement; record recent slot-2 I/O errors and 26 link resets through October 24, older slot-1/4 read errors and August scan/rebuild completions. Confirm scrub scheduler off in Safari and no retained scrub event; correct the earlier configuration-flag inference.
- [ ] Investigate the disk-2 drive/connection path before production migration or stress tests; obtain full drive-internal SMART/error logs, reconcile other historical faults and verify recovery coverage. Then qualify scheduled tests/scrubbing, current snapshot recovery/reserve policy and physical UPS/shutdown behavior. Clean array counters and Good summaries do not clear the logged faults.
- [x] Record cached QTS share sizes and bounded Public metadata; confirm both Public data folders belong to Ryan and QNAP media apps are unused by the household.
- [x] Inspect Multimedia Console's source/index/suite/transcoding pages, installed packages, protected-share registry and retained-app startup references. Video Station had no sources, the index had no files, and no other installed multimedia consumer was found. The subsequent retirement is recorded separately below.
- [x] Retire Video Station and Multimedia Console through App Center after encrypted state preservation; confirm both registry entries absent, retained services healthy and unchanged SMB configuration. See the [October 25 receipt](nas-media-retirement-2026-10-25.md) for incomplete download/preview/playback acceptance. Shares and scrub policy were not changed.
- [ ] Determine used bytes by data class from existing indices/QTS accounting; do not trigger a whole-collection scan/hash merely to plan.
- [ ] Inventory shares/aliases, NFS/AFP/WebDAV/FTP, QTS application privileges, scheduled tasks, package paths, symlinks, open sessions and every client. The SMB session probe required root and was not completed.
- [x] Verify homes enabled on Scratch, actual `home`/`homes` definitions, observed local admin/deployment homes, deployment SSH dependency and absence from HBS selection; supersede the failed earlier home probe.
- [ ] Qualify human local/domain home mapping, generated paths and effective isolation; add canonical personal roots to B2 and prove restore before moving Ryan's files.
- [ ] Resolve the retired laptop volume and its snapshots/hidden references. Retired share absence alone does not authorize deleting a volume.
- [ ] Export QTS settings, share/ACL configuration, UID/GID/SID mappings, Compose and mount definitions, Plex databases/preferences and library/profile IDs, Arr/Seerr settings, copy receipts and backup selection. Store secrets privately and encrypted.
- [ ] Verify fresh cloud/NAS settings archives and off-host readbacks. Preserve the existing local daily HA coverage of directory/directory-route, Authelia, home-acme and SSL/proxy state; add qualified recurring off-host coverage. Separately cover `/share`, controller CA, Forgejo links and Jellyfin settings/plugins/CA; retain AD SIDs/SYSVOL/trust, MFA database and original encryption/session/OIDC keys. Qualify a current isolated restore rather than repeating initial provisioning.
- [ ] Pilot `HomeAssistantBackups` with a dedicated HA-only writer and separate replica role. Verify retention deletion, NAS/AD outage behavior, native encryption/emergency-kit recovery, last off-host upload and an isolated native restore. Keep the on-demand unencrypted Talos export and age-encrypted identity export distinguished from daily native backups.
- [x] Re-read live HBS sources/schedule/retention/options and existing NAS/Forgejo verification receipts; incorporate separate committed October 25 Good Quick Check, Success status and isolated B2 settings-file restore evidence.
- [ ] Complete remaining HBS exclusion review and a private-original sample restore with byte, ownership, ACL and xattr verification; the settings-file ciphertext comparison does not establish this.
- [ ] Restore a Time Machine sample and confirm its encryption/recovery credential. Decide whether backing up the entire Time Machine history to B2 remains worth the cost.
- [x] Incorporate separately committed October 25 QNAP test-email and independent inbox delivery evidence; the old email-transport failure is resolved and the HBS failure rule remains enabled.
- [ ] Qualify actual backup-failure routing during the backup pilot. Decide client-side encryption and independent deletion-resistant backup policy before introducing more writable remote data.
- [ ] Agree acceptable data loss, service downtime and recovery time per class, including whether private originals have another independent copy.
- [ ] Qualify the per-share B2 policy: source/checkpoint age, producer and upload schedule, encryption, retained versions, destination scope, notification delivery, integrity checks and actual restore evidence. Split policies into independent jobs where necessary; do not assume the current single HBS job already implements them.
- [ ] Map overlapping Hetzner views to one authoritative source inventory; protect new/unclassified originals, explicitly exclude replaceable media, and avoid backing up replicas twice. Keep B2 credentials outside the full-account export and price initial/retained data before seeding new coverage.

### Permissions and identity

- [ ] Extend the existing encrypted-SMB3 synthetic matrix for every changed share/group: local and domain roles, list/read/create/rename/delete, private traversal denial, backup/config denial for media-only roles, explicit full-Hetzner access for selected account roles, HA-only backup access, and canonical reader write denial. Preserve both household users' Container/Usenet denial, Michael's Time Machine denial and LDAP-only services' denial on all shares.
- [ ] Test all access routes: SMB, File Station, local container mounts, any NFS export, snapshots/recycle bins, direct Hetzner, and the optional NAS gateway. Hidden share names are not authorization.
- [ ] Verify both existing objects and newly created objects inherit intended group/ACL/mask behavior. Capture exact ACLs before changes; avoid collection-wide chmod/chown.
- [ ] Apply the confirmed private membership (Ryan maintains, scoped Plex/backup services read); prove Michael, other nonmembers and `hass` cannot enter through local or domain paths, including the broad `nas-users` export. Confirm intended users/Plex still work and retain the restricted Plex profile's exact grants to IDs 2/3/4/5 and exclusion of ID 1.
- [ ] Verify service runtime UID/GID, supplementary groups, umask and mounts; ensure no human credentials or deployment admin group are needed for routine jobs.
- [ ] Complete the service-account ledger: each non-human principal has a `svc-*` target or documented vendor/provider exception, realm/host, owner, role scope, current/target IDs, consumers, credential references and rollback. Keep human profiles and permission-role names outside the prefix rule.
- [ ] Migrate `hass` and Filex callers by verified purpose, without carrying broad old grants into new accounts. Preserve already compliant AD lookup users and machine trust; test every affected protocol and new-file ownership before retiring compatibility access.
- [ ] Keep `usenet-deploy` and its `nas-deployment-operator` role explicit. Before the target `svc-nas-deploy` rename, separate shared runtime ownership, map every login/numeric-owner/controller/recovery reference, verify supported UID/GID/SID preservation, and test independent recovery plus dedicated-key deployment access. Record a platform exception if preservation is unsupported.
- [ ] After each account cutover, verify a normal application/backup cycle, fresh encrypted recovery exports and isolated restoration with the accepted identity map. Revoke replaced credentials and handle existing sessions only after acceptance; retain old-home data and recovery metadata through the rollback window.
- [ ] Test Ryan's and Michael's own-home RW, mutual denial, aggregate `homes` denial, service denial, new-file inheritance and scoped backup/isolated restore. Preserve separate local/domain home data until conflicts and ownership are resolved.
- [ ] Qualify SMB signing/encryption and removal of NTLMv1 with the actual Mac, Time Machine and other clients; save prior settings and change one control at a time.
- [ ] Record domain-qualified SIDs and effective numeric mappings before ACL changes; distinguish same-named local/domain users, inheritance and nested groups. Recheck QNAP machine trust after each affected change without rejoining it.
- [ ] Test planned group removal/account disablement/password changes across SMB tickets, browser/OIDC sessions, Jellyfin tokens, local compatibility accounts and direct Hetzner credentials; confirm revocation reaches each route and escrow reflects intentional changes.
- [ ] In a separate maintenance window, test HA/DC/SSO/DNS/WAN outage and recovery, including new versus existing sessions, directory-route startup before Authelia and local emergency access. Never activate the retired NAS DC. Consider a second independent DC only as separately scoped availability work.

### Paths, storage and writable remote mounts

- [ ] Record each source → destination mapping, filesystem/device identity, required space/reserve, writer, reader, backup and rollback reference before any move.
- [ ] Complete phase 5a's service/archive map: no target `AppData` or `BackupArchives` share, no broad parent container bind, and explicit supported native-package exceptions. Test cross-service denial and each archive pipeline before retiring any old service path.
- [ ] Verify `svc-forgejo` cannot access `forgejo-backups` or B2 credentials; capture can read its complete consistent source, the archive uploader can read only completed archive inputs, and historical/new-path application restores preserve Git objects, database, users and attachments.
- [ ] Execute the FromDrobo data-class cutovers above, including unclassified remainder, private-root backup continuity and remote-mount exclusion from local copies. Preserve same-filesystem staging/publication; retire the old export only after every consumer and B2 source is verified.
- [ ] Record current backing RAID/pool and target tier for each local share. Before moving Disposable or Replica shares to zero-redundancy storage, prove rebuild/source availability and the required B2 restore; verify changed backup paths, inherited ACLs and new-file protection afterward. Provider-backed views do not have a NAS-selectable data RAID level.
- [ ] For same-volume renames, require absent destination and compare device/inode afterward. For a justified cross-volume move, preserve metadata/hardlinks, verify the moved data, and retain the old source until acceptance.
- [ ] Keep TV staging and publish locations in the same bind/filesystem for atomic rename. Preserve manifests and ownership receipts; do not adopt unrelated files into eviction ownership.
- [ ] Keep NAS 100 GiB reserve, cloud 30 GiB reserves, 100 GiB release limit, current repair volume and retired-worker disablement.
- [ ] Test startup with storage unavailable and reconnect after interruption: refuse dependent work, preserve mode-0000 unmounted cloud directories, prevent writes into empty local mountpoints, and do not empty Plex trash.
- [ ] Verify FUSE/shared-mount propagation, remount behavior and dependent-container visibility using a pilot before any production mount move.
- [ ] Test writable remote large-file transfers, checksum readback of synthetic files, interrupted copy, rename/replace, hardlink behavior, filename/metadata semantics, concurrent users, full destination/cache and laptop sleep/wake.
- [ ] Verify server-side reader write denial remains effective; media-only writers cannot reach backup/config roots, while explicitly selected full-account roles can access the whole Hetzner filesystem. Test whole-account and scoped gateways separately using synthetic fixtures and policy metadata. Record direct-human and gateway-service credentials, roots and revocation; AD logout/disablement is not provider credential revocation.
- [ ] Define manual managed-media reconciliation: native records, manifests, link relationships, NAS receipts and both media servers agree after each operation; no unexpected downloads or deletes.

### Application and household acceptance

- [ ] Before each cutover, check downloads/postprocessing/imports, manual pauses, NAS transfers, Plex/Jellyfin sessions, Time Machine and HBS activity. Preserve active work and stop only affected services.
- [ ] Compare Plex library IDs/roots, profile grants and private visibility before/after. Keep automatic trash emptying disabled. Test actual household TV clients and owner/restricted profiles privately.
- [ ] Map each Plex viewer/account/profile to library grants (private ID 1 versus general IDs 2/3/4/5); verify Michael's exact profile/account linkage. Keep the single server runtime's required read access distinct from viewer rights. Separate server runtimes only if operating-system isolation is deliberately selected as additional work.
- [ ] Verify Jellyfin's existing user ID/`ryan` alias, LDAPS trust, disabled automatic user/admin creation, library policy, Moonfin request link and local recovery admin. Complete actual TV/native-client sign-in/playback after directory migration; recheck scans/transcoding/GPU access after storage/runtime changes, with private media still absent.
- [ ] Complete the still-pending human Arr/Catalog HTTPS MFA/OAuth flows; retain Catalog's owner-only actions, Arr group/gateway checks and anonymous API denial. Verify native Seerr requests/availability, Arr mappings/history, copy/evict receipts, Filex quarantine and held jobs without enqueuing downloads just to audit.
- [ ] Verify DNS, wiki and Forgejo SSH/HTTPS clone/fetch after application-volume/UID changes; preserve Forgejo's linked user and repository IDs. Test recovery management independently of HA browser SSO. Retained LAN HTTP/ports/ingress remain separate access boundaries.
- [ ] Record the Mac's actual SMB account realm and verify Time Machine continues the existing backup chain with a sample restore. Successful domain SMB fixture access does not prove the active backup migrated from its local account.
- [ ] Confirm HBS still selects the exact intended sources after every share/path change; exclude remote mounts, caches and staging; preserve existing B2 history. Check incremental behavior before allowing an unexpected full re-upload.
- [ ] Perform a controlled restart/reboot and outage test only in its maintenance phase, then verify all mounts, credentials, service dependencies and backup schedules. A healthy container alone is insufficient.
- [ ] Record acceptance and rollback evidence without media names/IDs in Git. Update canonical runbooks, inventory and recovery supplements; keep original bound snapshots immutable.

### Final cleanup and exceptions

- [ ] Reconcile every legacy subtree with an accepted destination or verified QNAP exception; no unclassified Public/Multimedia/FromDrobo contents remain. Personal/shared/private ownership and protection are explicit.
- [ ] Confirm FromDrobo is retired; Public has no household data/use and only required platform scope; Multimedia is removed or has an evidenced, narrowly scoped dependency exception. Check all exports, direct paths, aliases and local mounts.
- [ ] Confirm the former Scratch volume displays System with unchanged volume identity, system designation, backing RAID, mount paths, package locations and snapshot/backup schedules. Record any unsupported relabel as unresolved, not completed.
- [ ] Remove obsolete share grants and client/application defaults after replacement access passes; verify both local and domain users, guest denial, required service access and admin recovery. Retained platform-only shares must not grant household access merely through a broad group.
- [ ] Verify B2 covers every migrated original and required exception dataset at its new canonical source; prove historical/new restores and notifications. Retain old B2 history and checkpoints; do not treat a share disappearing as authorization to purge its data.
- [ ] Reconcile live/durable deployment, monitoring and recovery inputs against the final paths. Historical docs and immutable snapshots may retain old names only with an explicit restore mapping; no active consumer may silently recreate the old catch-all layout.
- [ ] Record each retained QNAP exception's owner, evidence, principals, backup policy and next-review trigger. During the planned restart test and after relevant QTS/app updates or restores, recheck share creation, permissions, mounts, applications and backup selection.
- [ ] Record final acceptance and separate source-data disposal decisions. The final catalog consists of the named datasets plus documented platform exceptions; backing-volume deletion and lower-redundancy redesign remain separate work.

## Decisions to settle before implementation

The user has chosen writable laptop access including managed media. Identity
selection and hosting are complete: use existing Samba AD/Authelia on HA and
QNAP domain membership. Ryan maintains the private library; both Ryan and Michael
maintain general media. Ryan's proposed general remote-file scope provides the
requested general RW access; full-account R/RW roles additionally cover the whole
Hetzner filesystem. Both existing Public folders are Ryan-owned, and the unused
QNAP media apps should retire after dependency checks. Remaining choices are
full-account role membership, ownership of any newly discovered shared documents,
additional general-file owners, the proposed shared staging memberships, the
recovery/downtime budget, whether the NAS gateway passes writable-filesystem
qualification and direct access is also wanted for travel/recovery, and whether
the proposed B2 retention/cost and lower-redundancy tier gates are acceptable and
capacity pressure justifies a later physical redesign. A second DC is optional
availability work, not a prerequisite for share cleanup.

Start with the application inventory's recovery diagnosis and offline wiki pilot.
Keep household-file ownership and dumping grounds deferred. The shared deployment
and runtime identity can be separated incrementally without rebuilding the pool;
the disk, snapshot and recovery gates still precede production data moves.
