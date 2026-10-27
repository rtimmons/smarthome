# NAS shares, accounts, roles and protection

**October 27 reconciliation:** see the [application/account inventory](nas-service-inventory-2026-10-27.md).
Live NAS process metadata confirms the shared 1004:100 runtime mapping, native
Plex root, Jellyfin 0:100 and the privileged remote-reader exception. Existing
AD lookup SIDs resolve; the initial metadata read changed no accounts, IDs or
memberships. The HA
FromDrobo mount is now active and writable, serving the established HA Plex
instance; the old inactive-mount finding below is historical. Preserve `hass`
until its consumers and replacement scopes are qualified. Wiki is the first
runtime pilot; the later checkpoint below records its completed identity switch.
Data paths remain unchanged.

**Wiki account checkpoint, October 27:** repository preparation is committed.
QNAP-local `svc-wiki` now exists (UID 1005; primary `everyone` GID 100,
supplementary `wiki-reader` GID 1000; no administrator membership). Saved settings
deny all seven existing shares and listed applications, without recursive ACL
propagation. Synthetic probes explicitly select 1005:1000: allowed reads and
actual file/share denials passed. A separate saved/restorable grant added only
reader-group access to the current wiki inputs; all site reads and Caddy validation
passed without changing existing ACL entries or ownership.
SMB authentication/denial is not tested. See the [checkpoint and remaining gates](nas-service-inventory-2026-10-27.md#wiki-preparation-and-recovery-checkpoint).
The approved runtime switch is now complete: init and Caddy run as 1005:1000,
with only group 1000, zero capabilities and read-only inputs. Durable wiki-only
overrides preserve that mapping on future deployment. Both HTTP routes and the
unauthenticated TLS/MFA redirect passed; all peer-container start times matched.
See the [runtime checkpoint](nas-service-inventory-2026-10-27.md#wiki-runtime-identity-checkpoint)
for rollback and recovery limits. No service data path has moved.

**Proposed access model, October 25, 2026. No accounts, groups or permissions have
been changed.** This is the concise authorization companion to the
[storage and migration plan](plan-nas-storage-and-access.md). The current-state
inventory at the end records the October 24–25 inspection and identity rollout.
The [October 25 preflight](nas-preflight-2026-10-25.md) adds current home-folder,
legacy-share and backup evidence; its unresolved gates still apply.

Confirmed policy: **Ryan maintains the private library; Ryan and Michael both
maintain general media.** Ordinary access follows **account → role → share**.
An unlisted grant means no access. Administrative recovery is a separate capability.
The model also supports **full Storage Box filesystem access** through explicit
Hetzner account roles; human membership in those broader roles is not yet selected.

## 1. Shares

These are logical access boundaries. The [per-share protection policy](plan-nas-data-protection.md)
defines each tier and B2 profile, including schedule, method, retention, encryption
and restore checks. All existing local shares still inherit one RAID-5 group;
different redundancy requires different backing storage, not just different names.
The target is a flat catalog of named datasets. Application data is a category,
not an `AppData` share; the former `BackupArchives` umbrella is replaced by
`forgejo-backups` and `infrastructure-backups`. Existing household/media share
names in the target catalog stay stable; legacy exports follow the retirement
policy below. New service shares use lowercase hyphenated names and are
ordinary-user SMB-denied by default, with local service mounts and explicit ACLs.

| Share | Contents / existing source | Target storage tier | B2 policy |
| --- | --- | --- | --- |
| `PrivateLibrary` | Private originals under `FromDrobo`; new restricted share | Protected | Local originals |
| `Documents` | Explicitly classified shared originals; no current Public payload is assigned here | Protected | Local originals |
| `home` (Ryan) | Canonical AD personal home; destination for both Public folders after privacy/backup pilot; homes enabled on Scratch, personal path unqualified | Protected | Local originals |
| `home` (Michael) | Canonical AD personal home; homes enabled on Scratch, personal path and isolation unqualified | Protected | Local originals |
| `homes` | Administrative parent of all personal homes; not a household-wide share | Protected | Local originals |
| `MediaCache` | Replaceable local movie/TV copies under `FromDrobo` | Disposable | Rebuild |
| `PlaybackCache` | Disposable rclone cache currently at `FromDrobo/.remote-cache`; service-only local storage | Disposable | Rebuild |
| `RemoteMedia` | Read-only media-only view of the existing remote mount | Provider-managed | Rebuild |
| `RemoteManage` | Writable view of the same media; new gateway requires qualification | Provider-managed | Rebuild |
| `RemoteFiles` | General remote files; proposed Ryan-owned scope | Provider-managed | Remote originals |
| `Hetzner` | Entire account filesystem, including hidden directories and backups; new full-account gateway | Provider-managed | Mixed by subtree |
| `TransferStaging` | Existing Filex staging; proposed shared temporary area | Disposable, conditional | Transient |
| `forgejo` | Repositories, database, LFS/attachments, configuration and keys; existing `Container/home-git` | Protected | Forgejo recovery |
| `forgejo-backups` | Completed encrypted Forgejo recovery archives; existing `Usenet/Backups/automatic/forgejo` | Replica | Forgejo recovery |
| `jellyfin` | Jellyfin database, configuration, plugins and persistent metadata; current `jellyfin-trial` state | Protected | Application recovery |
| `media-control` | Catalog/copy state, manifests, receipts and required configuration | Protected | Application recovery |
| `filex` | Filex configuration, host keys and persistent state; payloads remain in `TransferStaging` | Protected | Application recovery |
| `dns` | Resolver and discovery configuration/state, separated by subfolder ACLs | Protected | Application recovery |
| `wiki` | Reproducible published site and runtime configuration; source remains in Git | Disposable, conditional | Rebuild |
| `remote-reader` | Read-only mount service configuration/credentials; no mounted remote content or cache bytes | Protected | Application recovery |
| `remote-maintainer` | Configuration/credentials for the proposed media-only writable gateway | Protected | Application recovery |
| `hetzner-gateway` | Configuration/credentials for the proposed full-account gateway | Protected | Application recovery |
| `backup-control` | Backup scripts, schedules, per-job configuration/credentials and status; distinct job subfolders | Protected | Application recovery |
| `infrastructure-backups` | Encrypted NAS/application/cloud recovery artifacts, excluding Forgejo and native HA archives | Replica | Application recovery |
| `HomeAssistantBackups` | New dedicated native HA archive destination; currently no HA NAS backup mount | Replica | HA archives |
| `SpaceBlackTimeMachine` | Existing laptop backup share/chain; preserve its name | Replica | Laptop history |

Protected means at least one-disk fault tolerance. Disposable permits eventual
single-disk storage. Replica permits that reduction only after source availability
and independent B2 recovery are proven. Provider-managed means the Storage Box's
own redundancy, with no per-share RAID switch on the NAS.

### Personal homes

QTS exposes a user's personal directory as `home`; the directories reside under
the administrative `homes` share. Ryan and Michael therefore have distinct access
scopes, but not separate physical shares or independent RAID policies by default.
Local and domain identities must be mapped explicitly; matching usernames do not
prove they resolve to the same home. Use the AD home as each person's eventual
canonical personal space. The October 25 preflight supersedes the failed earlier
probe: homes are enabled on Scratch, with `home=%H` and domain template
`/share/homes/DOMAIN=%D/%U`. Only badmin and usenet-deploy local home directories
were observed; human/domain roots were not found at the tested paths. Local
filesystem permissions remain permissive, so owner isolation is not established.
Preserve enabled homes and the deployment home/key: they are a documented
[SSH recovery dependency](../usenet-infra/docs/qnap-bootstrap.md#october-25-ssh-recovery).
Neither homes nor Multimedia is in the current HBS source list.
[QTS home-folder behavior](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/home-folders-69AC09AA.html),
[QTS home-folder volume selection](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/enabling-home-folders-5342F3CB.html).

`home-owner(ryan)` and `home-owner(michael)` each grant RW only to that owner's
resolved directory. They are policy scopes enforced by QTS ownership/ACLs, not
a shared group granting both users access to all homes. Neither grants ordinary
access to the `homes` parent or the other person's files. Backup access is an
explicit read exception; administrators retain their separate recovery authority.
Do not grant media services or the deployment account an ordinary home-data role.
If QTS creates homes for service accounts, inventory them separately from service
application state and shell login directories; do not treat them as human data.
Back up each canonical personal directory once through `homes`, not again through
every `home` view. Different physical redundancy per person would require a
separately designed storage layout, not an ACL change.

### Shared and remote data

`RemoteMedia` and `RemoteManage` are two views of the same data, not two copies.
For these media roles, expose only the approved movie/TV/legacy-media subdirectories,
not the Storage Box's `catalog` root or all of `library`: those parents also contain
backup or acquisition-staging directories. Keep the existing internal reader
mount available to its established consumers while qualifying the narrower views.
`MediaCache` similarly excludes copy receipts and unpublished staging.

`Hetzner` deliberately exposes the **whole account**, including those backup and
staging trees. Full-account RW includes deleting or replacing any writable file
there and reading any credentials stored there. It does not grant Hetzner Console
billing/resource administration, NAS administration, or access to private files
that exist only on the NAS. Narrower share rules do not protect a remote object
from someone who also holds the full-account role. Off-account encryption keys
and independent recovery copies remain separate.

Each named service dataset gets its own QTS-managed share root and explicit
service permissions. Keep application-internal layout inside that root: Forgejo's
repositories, database, attachments and configuration form one recovery unit.
People use Forgejo's Git SSH/HTTPS permissions; membership in `git-users` grants
no direct file access to `forgejo` or `forgejo-backups`. The Forgejo runtime must
not mount its backup share or receive B2 credentials.

`dns` groups one resolver/discovery recovery unit; its subfolder ACLs still
separate the two runtimes. `backup-control` groups recovery-job inputs, with a
different private subfolder per job and no shared runtime-wide grant. These are
bounded datasets, not replacements for an all-application parent. Reuse B2
policy definitions across shares without assuming one bucket or volume per share.

Native Plex, HBS and QTS package state stays at supported package locations;
`package-state(plex)` and `package-state(hbs)` below are explicit non-share scopes.
Their supported exports enter `infrastructure-backups` under Application recovery.
Do not create a fictional `plex` share or move package internals to satisfy the
layout. User-facing SMB exports and local container binds enforce access through
different mechanisms. Preserve required `Container` package paths; legacy
household exports follow the explicit retirement policy below.

### Legacy shares and required platform exceptions

The [retirement and System-label phase](plan-nas-storage-and-access.md#legacy-share-retirement-and-system-label)
defines the supported removal gates and QNAP evidence. These objects are outside
the target household/service dataset catalog, but must remain visible in the
administrative inventory and [exception protection policy](plan-nas-data-protection.md#required-platform-roots).

| Object | Target access / disposition |
| --- | --- |
| `FromDrobo` | No remaining export or ordinary grant after its data cutover |
| `Public` | Retire household use; retain QNAP-required root with administrative recovery and only verified native consumers; no ordinary household/media role |
| `Multimedia` | Remove after dependency qualification, or retain only the exact required application scope; any continuing human access needs an explicit scoped policy |
| Required package/Container paths | Existing bounded package-state roles and verified native principals; no blanket household or cross-service grant |
| `Scratch` → `System` | Volume display alias only; creates no share, account, role or new permission |

The user confirmed both Public data folders are Ryan's private files: migrate
them to his canonical AD home only after privacy and backup qualification, not
to shared `Documents`. Video Station and Multimedia Console were
[removed on October 25](nas-media-retirement-2026-10-25.md) after encrypted state
preservation. Read-only native checks had found zero sources/indexed files and
no additional multimedia consumer. Retained-service checks passed within the
receipt's limits; Multimedia contents/share retirement and remaining client
acceptance are still phase 5c work. Required Container roots remain an evidenced
Container Station exception. Share grants and account permissions were unchanged.
Migrate other originals to owner homes, approved `Documents` scopes or `PrivateLibrary`
according to ownership; only verified replaceable media belongs in `MediaCache`.
Give each exception an owner, exact required principals/operations and backup
source. Do not invent a broad platform-share access group. Review existing
`nas-users`, `nas-multimedia-writers`, local-user and legacy `hass` grants after
replacement access passes; retire obsolete grants without removing unrelated
memberships or deleting a still-used group. Evaluate effective denial, including
inherited/default grants and direct paths. Hiding a share does not establish denial;
avoid blanket group denies that also remove administrative or native service access.

## 2. Human users

| Person | Primary identity | Existing compatibility identity |
| --- | --- | --- |
| Ryan Timmons | AD `SMARTHOME\ryantimmons` | QNAP-local `ryantimmons`, UID 1001 |
| Michael Lee | AD `SMARTHOME\michaellee` | QNAP-local `michaellee`, UID 1003 |

Use the AD identities for new grants. Same-named local accounts are separate
principals; retain their existing grants only until each dependent client is
migrated and tested. Neither person's everyday account is a NAS administrator.

## 3. System accounts

The names in the first column are the **target identities**. The two AD lookup
accounts already exist; other `svc-*` names are proposals. `svc-nas-deploy` is the
target name for the existing deployment account, subject to the migration gates
below; adopting this policy does not rename any live account.

### Service-account naming policy

Use **`svc-<purpose>`**, adding a scope suffix when needed, for every managed
non-human account whose login name we control: NAS/local runtime users, AD
directory bind users, deployment automation, backup destination logins and
machine-only application integrations. Use lowercase ASCII letters, digits and
single hyphens, with a meaningful purpose after `svc-`; examples are
`svc-nas-deploy`, `svc-ha-backup` and `svc-jellyfin-runtime`. Check each target
system's length/character limits and case-insensitive collisions before creating
or renaming anything. Record the realm/host as part of the account identity.

- Separate independently managed purposes and credentials. An LDAP lookup
  identity, application runtime, backup writer and deployment administrator are
  different accounts even when they support the same application. Do not create
  one catch-all `svc-nas` or `svc-homeassistant` with combined access.
- Keep authorization role/group names descriptive of permissions, such as
  `media-readers` and `nas-deployment-operator`; do not add `svc-` to those roles.
  A host's private primary group may match its service account where required.
  The prefix grants no rights and does not isolate processes sharing one UID.
- Human users, personal administrator/recovery identities and Plex viewer
  profiles keep their human identities. A shared interactive login must first
  be classified as human or machine use; adding `svc-` does not resolve shared
  human credentials. Noninteractive accounts get no browser/SMB/shell login
  unless their job requires that specific protocol.
- Preserve vendor-managed users, machine accounts, required package/root
  identities and provider-assigned usernames when renaming is unsupported.
  Record each exception's actual principal, purpose, effective privileges,
  constraint, owner and review trigger. Use a `svc-*` inventory/credential label
  where editable; never present that label as a working provider login.
- Existing compliant names (`svc-authelia`, AD `svc-jellyfin`) stay unchanged.
  Keys, tokens, provider resource IDs, share names and backup repositories do not
  need renaming or rotation just to satisfy an account-name policy. Keep secrets
  and exact credential references in the private inventory, not this document.

| Target identity | Purpose | Current identity / implementation |
| --- | --- | --- |
| `svc-nas-deploy` (target rename) | Repository-driven NAS deployment and maintenance | Existing QNAP-local `usenet-deploy`, UID 1004/GID 100, member of `administrators`; dedicated SSH key and pinned host trust |
| `svc-plex` | Plex playback and indexing | Native QTS package; effective runtime UID still to verify |
| `svc-jellyfin-runtime` | Jellyfin playback and indexing | Container UID 0/GID 100 with read/search capability and read-only media binds |
| `svc-media-copy` | Catalog actions and selective NAS copying | Catalog/rclone runtime shares UID 1004/GID 100 |
| `svc-remote-reader` | Read-only Hetzner mount and disposable cache | Mount helper has privileged capabilities; existing provider reader credential |
| `svc-remote-maintainer` | Writable Hetzner gateway | New runtime and provider writer credentials; not deployed |
| `svc-hetzner-gateway` | Full-account Hetzner filesystem gateway | New runtime with a full-account backend credential; distinct from media-only writer |
| `svc-filex` | Transfer staging | Local runtime UID 1004; SFTP login `filex-staging` is an application login, not a separate NAS UID |
| `svc-dns` | DNS resolver | Runtime UID 1004 |
| `svc-discovery` | DNS discovery state | Runtime UID 1004 |
| `svc-wiki` | Serve the published static wiki | QNAP-local runtime 1005:1000 (`wiki-reader`), group 1000 only; published inputs read-only; October 27 runtime checkpoint passed within its recorded limits |
| `svc-forgejo` | Git service | Runtime UID 1004 |
| `svc-forgejo-backup` | Capture consistent full Forgejo recovery archives | Existing separate host-owned stopped-state job; target identity separation still to qualify |
| `svc-settings-backup` | Infrastructure/application capture, encryption, off-host upload and readback | Backup container UID 0/GID 100; excludes the separately scoped Forgejo producer in the target model |
| `svc-originals-backup` | HBS originals/laptop backup | Native HBS package and existing B2 credential; effective runtime UID still to verify |
| `svc-archive-b2` | Upload verified Forgejo and infrastructure archives to B2 | Proposed distinct archive-upload job, with a separate destination credential/scope for each archive family |
| `svc-hetzner-backup` | Protect canonical remote originals and other non-excluded account data in B2 | Proposed cloud backup runner; excludes replaceable media and qualified duplicate replicas |
| `svc-ha-backup` | HA writes/reads/prunes its native archives on the NAS | Proposed dedicated QNAP-local destination login; current automatic backups use HA local storage only |
| `svc-ha-backup-replica` | Copy HA archives to an independent destination | Proposed separate replication job/credential; no off-host HA backup agent currently selected |
| AD `svc-authelia` | Authelia directory lookups | Existing AD account; no NAS-share or directory-administration role |
| AD `svc-jellyfin` | Jellyfin directory lookups | Existing AD account; distinct from `svc-jellyfin-runtime`; no NAS-share or directory-administration role |

Runtime accounts normally belong on the host running the service. They do not
all need AD accounts or SMB passwords. For native packages and privileged mount
helpers, first verify supported identity controls; preserve required exceptions
until narrower identities, mounts and capabilities pass testing. Sharing a UID
does not provide isolation merely because two roles have different names.

Administrative and compatibility principals remain explicit:

| Principal | Current role | Target handling |
| --- | --- | --- |
| QNAP `badmin`, UID 1000 | Local administrator / recovery | Keep separate from everyday Ryan login; verify emergency access |
| QNAP `admin`, UID 0 | Built-in administrator | Preserve recovery configuration; login enablement was not verified |
| Wiki runtime 1005:1000 | `svc-wiki` / `wiki-reader` runtime phase complete | Normal capture and authenticated network denials remain; named-share move requires storage gates |
| QNAP `hass`, UID 1002 | Legacy integration account with broad `FromDrobo` access | Identify actual consumers; replace with explicit scopes before removing access |
| `guest`, `httpdusr`, `[sshd]` | QTS built-ins | No new data roles; guest denied on all six inspected SMB shares |
| AD administrator and machine principals | Directory administration and NAS trust | Preserve existing identities/trust; no new household data roles |

### NAS deployment identity

Assign `usenet-deploy` the distinct **`nas-deployment-operator`** role now in the
model; keep `platform-admin` for recovery administrators. QTS SSH required
administrator membership in the [deployment bootstrap](../usenet-infra/docs/qnap-bootstrap.md).
Thus this separation records purpose and accountability, not a claim that the
current deployment credential cannot read data or change ACLs. Its effective
administrative power remains broad even without household data-role membership.
Retain a separate, tested local recovery login independent of AD/SSO.

First move runtime services off UID 1004 using per-service variables and scoped
ownership. Merely renaming the account, or changing the shared `qnap_uid` variable,
does not separate those services. Keep the existing login working throughout.
Then migrate to `svc-nas-deploy` through a supported QTS account change, verifying
UID/GID/SID, memberships and effective access before and after. If preserving
identity is unsupported, retain `usenet-deploy` as a documented exception until
an explicit account-replacement and ownership plan passes its recovery gates.

Before any rename, map ignored `QNAP_SSH_TARGET`, Ansible `ansible_user` and
UID/GID variables, durable controller inputs, authorized-key/login-home paths,
SSH restrictions, cron/backup jobs, numeric Compose owners, ACLs and recovery
instructions. Test the new login with the same dedicated access key and pinned
host key, deployment preflight and a scoped operation, then refresh encrypted
recovery supplements. Preserve immutable snapshots and the separate Git signing
identity. Roll back the login and references together if acceptance fails; do
not delete/recreate the user or recursively chown data to make a name match.

### Service-account migration

This is a staged identity migration, separate from the FromDrobo path moves.
The table records disposition; it does not authorize bulk renames or imply that
every proposed account needs to be created immediately.

| Existing identity / use | Target / disposition | Migration gate |
| --- | --- | --- |
| QNAP `usenet-deploy`, UID 1004 | `svc-nas-deploy`; retain `nas-deployment-operator` | Split runtime ownership first, then preserve identity through a supported rename; otherwise record an exception pending replacement |
| Runtimes sharing UID 1004 | Individual `svc-media-copy`, `svc-filex`, `svc-dns`, `svc-discovery`, `svc-forgejo` as applicable | Allocate supported non-conflicting IDs; separate shared variables; transfer only each service's enumerated state ownership and mounts |
| QNAP `hass`, UID 1002 | Split verified consumers into `svc-ha-<purpose>` accounts; retire if unused | Inventory callers and scopes first; `svc-ha-backup` is only for native backup storage, never a rename that inherits broad FromDrobo rights |
| Filex application login `filex-staging` | If machine-only, target `svc-filex-transfer`; if used interactively, select a human-account design | Verify actual clients and application support; keep distinct from the `svc-filex` OS runtime; do not change both layers in one cutover |
| AD `svc-authelia`, AD `svc-jellyfin` | Keep existing names, SIDs, credentials and lookup-only roles | Already compliant; no account recreation, OIDC relinking or new NAS grants |
| Native Plex/HBS users, privileged helpers and QTS built-ins | `svc-plex` / `svc-originals-backup` are target labels where supported; retain required vendor identities otherwise | Verify supported runtime controls; document effective UID/capabilities and exceptions rather than renaming built-ins or claiming isolation |
| Hetzner provider users and B2 credentials | Prefix editable service credential labels; preserve provider-issued logins/IDs | Keep backend scopes, consumers and key references mapped; no provider-resource replacement solely for naming |
| New gateway, HA archive and backup jobs | Use their listed `svc-*` identities from initial provisioning | Assign only the account's explicit source/destination roles; validate recovery independent of AD where required |

1. **Inventory and checkpoint.** Record each old name, realm/host, UID/GID/SID,
   owner, purpose, role memberships, home, protocol privileges, credential
   references, consumers, ACLs and backup/recovery dependencies in a private
   migration ledger. Include ignored/durable controller inputs, Compose users,
   LDAP bind DNs, SMB mounts, application logins, scheduled jobs and provider
   credentials. Mark each row unchanged, rename, split/replace, retire or exception.
   Save a consistent settings export and verify independent recovery access.
2. **Pilot names and permissions.** Check platform support and collisions with
   synthetic accounts/data. Separate per-service UID/GID settings from the current
   shared `qnap_uid` before assigning new runtime IDs. Validate both intended
   access and denial, home creation, new-file inheritance, restart behavior and
   backup capture. Keep existing compliant AD lookup identities unchanged.
3. **Separate runtimes one at a time.** Start with a qualified low-dependency
   service; migrate its supported identity, scoped state ACLs/ownership and mounts
   while preserving paths and application IDs. Where a replacement is needed,
   stage its narrow permissions first and switch only that consumer during an
   agreed pause. Keep the prior identity and saved settings available for rollback;
   do not run old and new writers concurrently or leave broad compatibility access
   indefinitely. Privileged/native-package exceptions stay explicit.
4. **Migrate integration and deployment logins.** Reconcile every `hass`/Filex
   caller separately, then rename the deployment login after shared runtime use
   is removed. Prefer supported identity-preserving renames, verify numeric/SID
   identity afterward and update every name-based consumer in the same cutover.
   If replacement is necessary, define the ACL/home/credential mapping explicitly;
   do not silently delete/recreate an account or assume matching names/IDs restore
   access. Preserve the independent recovery login and pinned SSH trust.
5. **Verify and refresh recovery.** Test each affected protocol with synthetic
   files, expected denials, one normal application/backup cycle and a scoped
   restart. Verify fresh encrypted exports include the accepted identity map and
   consumer settings, and restore an isolated sample using the new account
   mapping. Preserve old backup decryption keys and historical identities needed
   to restore ownership; update recovery supplements without rewriting snapshots.
6. **Retire or roll back.** Once all consumers pass, revoke superseded grants and
   credentials for replaced/retired principals, disable their old logins, and
   verify those credentials can no longer establish new access; explicitly handle
   existing sessions/tokens. A pure rename keeps its accepted dedicated key or
   credential; test rejection of the old login name without revoking the key
   still used by the renamed account.
   Keep its data and recovery records through the agreed rollback window before
   considering deletion or ID reuse. If a check fails, pause the affected writer,
   restore that account's saved identity/ownership and consumer configuration,
   reconcile any new writes, and revalidate access/backup. Do not roll back the
   domain join, unrelated accounts or the entire NAS.

Completion means every managed non-human principal has either a working `svc-*`
identity or a documented platform exception, with consumer tests and recovery
evidence. A changed display label or untested replacement account is insufficient.

## 4. Accounts → roles

Role names below describe the target policy. Shared human roles should be backed
by AD security groups, personal homes by owner ACLs, and service roles by scoped
host groups/ACLs and mounts. Roles do not automatically nest in one another.
`service-state(dataset)` names exactly one of the real service shares below;
it is not a shared group opening every application's state. Parameterized archive
and backup-control roles likewise grant only the named family or job subfolder.

| Account | Target roles |
| --- | --- |
| AD Ryan | `home-owner(ryan)`, `private-media-maintainers`, `media-maintainers`, existing `nas-timemachine`; proposed `remote-file-maintainers(ryan)` and `transfer-users` |
| AD Michael | `home-owner(michael)`, `media-maintainers`; proposed `transfer-users` |
| QNAP `usenet-deploy` → target `svc-nas-deploy` | `nas-deployment-operator`; no routine playback, household-file or backup-job role |
| `svc-plex` | `private-media-readers`, `media-readers`, `package-state(plex)` |
| `svc-jellyfin-runtime` | `media-readers`, `service-state(jellyfin)` |
| `svc-media-copy` | `media-copy`, `service-state(media-control)` |
| `svc-remote-reader` | `remote-reader`, `playback-cache-writer`, `service-state(remote-reader)` |
| `svc-remote-maintainer` | `remote-gateway-writer`, `service-state(remote-maintainer)` |
| `svc-hetzner-gateway` | `hetzner-account-maintainers`, `service-state(hetzner-gateway)` |
| `svc-filex` | `transfer-users`, `service-state(filex)` |
| `svc-dns` | `dns-runtime` |
| `svc-discovery` | `dns-discovery`, `dns-config-reader` |
| `svc-wiki` | `wiki-reader` |
| `svc-forgejo` | `service-state(forgejo)`; no backup-share or B2 grant |
| `svc-forgejo-backup` | `forgejo-backup-source-reader`, `forgejo-capture-control`, `archive-writer(forgejo)`, `backup-control(forgejo-capture)` |
| `svc-settings-backup` | `infrastructure-backup-source-reader`, `archive-writer(infrastructure)`, `backup-control(infrastructure-capture)` |
| `svc-originals-backup` | `originals-backup-reader`, `home-backup-reader`, `b2-backup-writer(originals)`, `b2-backup-writer(laptop-history)`, `package-state(hbs)` |
| `svc-archive-b2` | `archive-readers(forgejo)`, `archive-readers(infrastructure)`, `b2-backup-writer(forgejo)`, `b2-backup-writer(infrastructure)`, `backup-control(archive-b2)` |
| `svc-hetzner-backup` | `hetzner-account-readers`, `b2-backup-writer(remote-originals)`; cloud-host state, no local NAS service-share grant |
| `svc-ha-backup` | `ha-backup-writer` |
| `svc-ha-backup-replica` | `ha-backup-readers`, `b2-backup-writer(home-assistant)`, `backup-control(ha-replica)` |
| AD `svc-authelia`, AD `svc-jellyfin` | `directory-lookup` only |
| Separate NAS recovery administrators | `platform-admin`; outside ordinary data grants |
| Unassigned until ownership is decided | `document-readers(scope)`, `document-maintainers(scope)`, additional `remote-file-maintainers(scope)` memberships, `backup-operators` |
| Human full-account membership not yet selected | `hetzner-account-readers`, `hetzner-account-maintainers` |

Ryan retains `git-users` and `arr-users`; Michael retains his existing NAS
compatibility groups. Those application groups grant no storage rights. The
new media role does not change Catalog, Jellyfin, Plex or Seerr application access.
Existing `nas-users` grants are temporary compatibility grants, not a parent of
the new private or media roles. Ryan's proposed general-file scope implements
the earlier request for general remote RW access. Shared transfer memberships
remain a proposal separate from the confirmed private/general-media decision.
The originals/laptop HBS jobs also receive their scoped B2 destination roles;
source access and remote write/retention authority are listed separately in the
[backup-job mapping](plan-nas-data-protection.md#job-owners-and-access).

## 5. Roles → share permissions

**R** = list/read/traverse. **RW** = R plus create, modify, rename and delete.
RW does not itself grant permission administration; access to credentials depends
on whether they are stored within the granted scope. **—** = no grant.
These are additive allow rules: validate effective access across all
memberships, local compatibility identities and alternate exports.

| Data role | PrivateLibrary | MediaCache | RemoteMedia | RemoteManage | TransferStaging | Time Machine |
| --- | --- | --- | --- | --- | --- | --- |
| `private-media-readers` | R | — | — | — | — | — |
| `private-media-maintainers` | RW | — | — | — | — | — |
| `media-readers` | — | R | R | — | — | — |
| `media-maintainers` | — | RW | R | RW | — | — |
| `media-copy` | — | RW | R | — | — | — |
| `remote-gateway-writer` | — | — | — | RW | — | — |
| `transfer-users` | — | — | — | — | RW | — |
| `nas-timemachine` | — | — | — | — | — | RW |
| `originals-backup-reader` | R | — | — | — | — | R |

The remaining shares and backend roles have explicit scopes:

| Role | Share / exact scope | Permission |
| --- | --- | --- |
| `home-owner(person)` | That person's resolved `home` directory only | RW; no other home or aggregate `homes` browsing |
| `home-backup-reader` | Explicit canonical personal directories under `homes` | R for backup; exclude unclassified service homes until inventoried |
| `playback-cache-writer` | `PlaybackCache` only | RW for the remote reader; no human SMB grant |
| `document-readers(scope)` | Assigned subtree of `Documents` | R |
| `document-maintainers(scope)` | Assigned subtree of `Documents` | RW |
| `remote-file-maintainers(scope)` | Assigned subtree of `RemoteFiles` | RW |
| `hetzner-account-readers` | Entire `Hetzner` account filesystem | R, including backup/configuration files stored there |
| `hetzner-account-maintainers` | Entire `Hetzner` account filesystem | RW, including backup/configuration files stored there |
| `ha-backup-writer` | `HomeAssistantBackups` only | RW, including native archive readback and retention deletion |
| `ha-backup-readers` | `HomeAssistantBackups` only | R |
| `b2-backup-writer(scope)` | Assigned B2 job repository/prefix | Upload/readback and required bounded retention operations; no other share or B2-account administration |
| `b2-restore-readers(scope)` | Assigned B2 recovery repository/prefix | Read/list for recovery; decryption keys held separately; no prune authority |
| `service-state(dataset)` | Exactly one of `forgejo`, `jellyfin`, `media-control`, `filex`, `remote-reader`, `remote-maintainer`, `hetzner-gateway`, as assigned above | RW on required mutable state; configuration/credentials mounted R where supported; no other service or backup share |
| `dns-runtime` | `dns/resolver` only | R on deployed config, RW on required runtime state; no discovery-state grant |
| `dns-discovery` | `dns/discovery` only | RW on discovery state; no resolver configuration write grant |
| `dns-config-reader` | Enumerated generated resolver config in `dns/resolver` | R for discovery; no credential-wide directory access |
| `wiki-reader` | `wiki` publication and runtime config | R; deployment operator publishes; sources stay in Git |
| `package-state(service)` | Supported native Plex or HBS package paths, as assigned | Required package state access; a non-share exception, not a grant on other services |
| `forgejo-backup-source-reader` | Entire consistent `forgejo` recovery set | R on repository objects, database, LFS/attachments, configuration and keys |
| `forgejo-capture-control` | Forgejo service lifecycle only | Pause/start for consistent capture through a qualified bounded helper; no general Docker socket in Forgejo |
| `infrastructure-backup-source-reader` | Enumerated recovery inputs in `jellyfin`, `media-control`, `filex`, `dns`, the three remote-service shares, `backup-control`, and supported QTS/Plex/HBS exports | R for consistent encrypted capture; no Forgejo source or media payload grant |
| `archive-writer(forgejo)` / `archive-readers(forgejo)` | `forgejo-backups` | RW for capture/pruning / R for upload or recovery |
| `archive-writer(infrastructure)` / `archive-readers(infrastructure)` | Assigned NAS/application/cloud streams in `infrastructure-backups` | RW for capture/replica/pruning / R for upload or recovery; job ACLs restrict each writer to its stream |
| `backup-control(job)` | `backup-control/<job>` for the exact job named above | RW on status/journals; R on deployed config/keys; no other job's credential scope |
| `originals-backup-reader` | Approved originals in `Documents` in addition to the data matrix | R; archive ingestion belongs to the separate uploader in the target model |
| `backup-operators` | Encrypted `forgejo-backups`, `infrastructure-backups` and `HomeAssistantBackups` | R; restore to an isolated destination, no ordinary overwrite authority on source shares |
| `remote-reader` | Internal reader mount and its backend | R on backend; local disposable cache uses the separate `playback-cache-writer` scope |
| `directory-lookup` | No NAS share | No share access; read-only directory lookup |
| `nas-deployment-operator` | NAS configuration, deployed service definitions and managed state | Administrative deployment capability; current QTS administrator membership can override share ACLs, so no data-isolation guarantee |
| `platform-admin` | NAS recovery and permission administration | Broad administrative exception, including recovery access to `homes`; no implied everyday data role |

`platform-admin` can change ACLs and may take ownership or mount data. It is an
administrative exception, not an ordinary RW role or a privacy boundary against
the NAS administrator. The current deployment operator has this same technical
bypass capability; its distinct role is an operational boundary. Decryption/recovery
keys are separate from backup-read roles.
The current root backup container and host-owned Forgejo scheduler can exceed
these target file grants. Qualify separate identities and bounded lifecycle
controls before claiming isolation; a newly named role does not remove root or
Docker-management capability. Keep HBS's existing archive selections until the
replacement upload path and historical/new-path restores pass.

Managed-media RW is filesystem permission, not a second import workflow. Both
maintainers must preserve Arr bookkeeping, hardlinks and NAS-copy receipts, using
native actions where possible and reconciling any direct edits as the main plan describes.
Plex's target private-media access is read-only; its owner/restricted-profile policy still
controls which viewers can see it. Michael's general-media role grants no private access.

### Plex users, libraries and runtime identities

**Five libraries do not require five Plex system accounts.** The current QNAP
Plex server has one runtime identity, which must read all five source libraries.
Plex accounts and managed profiles are viewer identities; library grants are
applied inside Plex. They are separate from SMB users and AD storage roles.
[Plex library access](https://support.plex.tv/articles/201105738-creating-and-managing-server-shares/).

| Library | Source share/view | Viewer role |
| --- | --- | --- |
| Private library, ID 1 | `PrivateLibrary` | `plex-private-viewers` |
| NAS movies, ID 2 | Published movies in `MediaCache` | `plex-general-viewers` |
| NAS TV, ID 3 | Published TV in `MediaCache` | `plex-general-viewers` |
| Remote movies, ID 4 | Movie/legacy-media paths in `RemoteMedia` | `plex-general-viewers` |
| Remote TV, ID 5 | TV paths in `RemoteMedia` | `plex-general-viewers` |

| Plex identity | Target viewer roles | Status |
| --- | --- | --- |
| Ryan's existing server-owner account | Private and general viewing; existing server administration | Preserve original identity |
| Existing managed general-viewing profile | `plex-general-viewers` only | Already restricted to IDs 2/3/4/5; retain ID 1 denial |
| Michael's selected Plex account/profile | `plex-general-viewers` only | Exact account/profile linkage still to inventory; do not invent a new account |
| `svc-plex` | No viewer role; filesystem `private-media-readers` + `media-readers` | Proposed name for the single existing server runtime |

The viewer-role names are policy labels, not a claim that Plex consumes these
AD groups. Multiple people/profiles may have access to the same library. If the
private and general servers must be isolated at the operating-system level,
that needs separately managed server instances with different runtime identities
and source mounts. It is separate migration work, not a consequence of having
multiple libraries; preserve current IDs, metadata and watched state meanwhile.

### Remote credentials are a separate authorization layer

Provider account labels below identify existing resources or proposed purposes;
they are not new AD users. Exact provider usernames/keys remain in private inputs.

| Provider credential / principal | Used by | Role and allowed backend |
| --- | --- | --- |
| Existing `qnap-reader` | NAS reader, copy jobs and cloud-backup pull | Current R on catalog, including encrypted cloud archives; preserve while separating human exports |
| Existing `nas-settings-backup` | Settings and Forgejo backup jobs | RW only in the existing confined NAS-settings backup tree |
| Existing B2 backup credential | HBS | Preserve current backup destination; verify provider permissions before claiming least privilege |
| Existing cloud acquisition writer | Cloud SAB/Arr mount and established jobs | Existing provider writer; not a NAS-share user; broader current scope requires separate review |
| Proposed media gateway writer credential(s) | `svc-remote-maintainer` | RW only on approved canonical media roots; no backup/config/acquisition-staging grant |
| Optional direct human media credential(s), one set per person | Ryan and Michael, if direct access is enabled | Same media-only RW scope; independent credentials and revocation |
| Proposed general-files credential(s) | Future `RemoteFiles` gateway/owner | RW only in Ryan's assigned general-file root; additional memberships undecided |
| Full-account backend credential | Proposed `svc-hetzner-gateway`; optional separately authorized direct clients | Full Storage Box filesystem RW; NAS roles can expose R or RW to individual users |
| Proposed B2 destination credentials, one scope per backup job | Originals, laptop, settings, HA and remote-originals backup jobs | Only the corresponding B2 repository/prefix; separate from Hetzner data credentials; retention permissions must match the selected tool |

For media-only roles with disjoint roots, use separately confined subaccounts
rather than granting their common `catalog` parent. QNAP AD groups govern NAS SMB; they do
not revoke direct Hetzner credentials or propagate individual ACLs through a
shared gateway credential. Keep the server-enforced playback reader read-only.

Hetzner documents complete directory access for the main user and subtree access
for subaccounts. Plan the full-account gateway around a credential with verified
whole-account scope; do not claim the existing confined reader can supply it.
The current Terraform configuration disables external reachability and SMB for
the main account. Qualify a gateway transport through the existing cloud/VPN path
or deliberately revise network settings in its own pilot before promising a
direct laptop/NAS root mount. No provider setting or key changed during planning.
[Hetzner account scopes](https://docs.hetzner.com/storage/storage-box/general/).

### Home Assistant and the distinct backup systems

Fresh read-only metadata on **October 25** shows native HA automatic backups are
configured **daily**, retaining **three automatic copies**, with only
`hassio.local` selected. The latest run started at **4:57 a.m. Eastern** and
completed at **5:09 a.m.** Its protected partial archive contains HA Core,
all **26 installed apps** (including AD/Authelia) and `/ssl`; database inclusion
is enabled. `/share` is absent from that archive. There is no Supervisor backup
network mount; the sole `FromDrobo` CIFS mount is an **inactive media mount**.
This verifies configuration/archive metadata, not decryption or an independent restore.

| Backup system | Producer and contents | Destination / boundary |
| --- | --- | --- |
| HA native daily backup | HA Core/Supervisor; Core/database, all apps and `/ssl` in the observed archive | Currently local HA storage only; proposed `HomeAssistantBackups` plus the dedicated B2 HA-archive policy |
| Talos `addon-state` export | Repository apps and all of `/share`; deliberately excludes HA Core and `/ssl` | On-demand native partial archive plus controller download; intentionally unencrypted, no automatic pruning; not the daily recovery backup |
| Identity-specific HA export | Cold backups of directory, directory-route, Authelia and home-acme plus `/ssl` | Point-in-time native export encrypted with age and verified off-host; not a whole-HA or recurring schedule |
| NAS/application and Forgejo jobs | Supported QTS/Plex/HBS and application exports; Forgejo's full repositories/database/state captured separately | `infrastructure-backups` and `forgejo-backups`, plus the existing confined Hetzner tree; neither creates native HA backups |
| Cloud settings job | SAB/Arr and cloud service state | Separate encrypted cloud-backup tree, with a NAS replica; not HA state |
| HBS originals/laptop job | Selected private/Public originals, laptop history and encrypted settings archives | Existing B2 job; HA native archives are not proven included |
| Time Machine | The laptop's backup process | `SpaceBlackTimeMachine`; unrelated to HA native restore |

Keep a dedicated `HomeAssistantBackups` share and `svc-ha-backup` destination
login. A QNAP-local service login is proposed so connecting to HA's recovery
destination does not depend on the AD service hosted by HA itself. It gets no
`FromDrobo`, private-media, service-data or other archive-share access. Do not reuse
the broadly authorized legacy `hass` account. Native HA still produces the
archives; this login only controls access to their storage destination.

The replication role reads those archives and writes only its designated B2
destination. If an additional replica is stored on Hetzner, a full account
maintainer can also access it; a distinct prefix there does not make it independent
of that role. Hetzner data roles do not carry B2 credentials.
Record native encryption/emergency-kit custody, local versus off-host retention,
last successful upload and isolated restore evidence separately. Native daily
coverage now includes the identity apps locally; recurring off-host coverage and
the `/share` state gap remain to qualify. Do not run a cold backup just to inspect
configuration, because it briefly stops the affected apps.

See [HA backup configuration](https://www.home-assistant.io/common-tasks/general/backups/),
[network backup storage](https://www.home-assistant.io/common-tasks/os/#network-storage),
the [Talos backup contract](operations/addon-state-backups.md), and the
[identity recovery runbook](operations/household-identity.md).

## Current state and migration delta

The October 27 service ledger is the latest application checkpoint. Its explicit
observed/configured/proposed labels supersede any inference that naming a role
has already deployed or tested it. No new service-share paths were returned for
wiki, Forgejo or the two archive shares. Expected denials remain to be tested on
both host/container and SMB paths; retained administrative bypass is explicit.

The fresh October 25 preflight found seven path-bearing SMB shares, adding the
enabled `homes` parent to the earlier six-share inventory. `home` is a dynamic
owner view. The configuration also contains a
`TMBackup` section with no path returned; it is not counted as a qualified data
share and needs clarification before cleanup.

| Current share | Location / purpose | Intended replacement |
| --- | --- | --- |
| `FromDrobo` | Main data volume; private originals, local media, remote mount and staging mixed together | Physical data split into `PrivateLibrary`, `MediaCache`, `PlaybackCache`, `TransferStaging`; remote views relocated through a mount cutover |
| `home` / `homes` | Enabled on system volume; local admin/deployment homes observed; human/domain paths and effective isolation unqualified | Owner-scoped AD homes with B2 coverage; preserve deployment SSH dependency and distinct local homes |
| `Public` | System volume; two Ryan-owned data folders, about 9.95 GiB, plus system metadata | Move both folders to Ryan's qualified AD home with backup continuity; retire household access; retain minimal required platform root |
| `Multimedia` | System volume; Samples/system metadata remain; Video Station and Multimedia Console removed after encrypted state preservation | Classify contents and retire the share through supported controls; complete remaining retained-app/client acceptance |
| `Container` | System volume; application state | Named `forgejo`, `jellyfin`, `media-control`, `filex`, `dns`, `wiki`, remote-service and `backup-control` shares; required native package paths remain |
| `Usenet` | Main data volume; settings archives | `forgejo-backups` and `infrastructure-backups`, plus any separately inventoried remaining contents |
| `SpaceBlackTimeMachine` | Dedicated laptop-backup volume | Keep existing share |

Current AD memberships and share grants are already deployed:

| Account | Existing roles |
| --- | --- |
| AD Ryan | `nas-users`, `nas-timemachine`, `git-users`, `arr-users` |
| AD Michael | `nas-users`, `nas-multimedia-writers` |
| AD `svc-authelia`, AD `svc-jellyfin` | Directory lookup; no NAS access roles |

| Existing role | FromDrobo | Public | Multimedia | Container | Usenet | Time Machine |
| --- | --- | --- | --- | --- | --- | --- |
| `nas-users` | RW | R | R | — | — | — |
| `nas-timemachine` | — | — | — | — | — | RW |
| `nas-multimedia-writers` | — | — | RW | — | — | — |
| `git-users`, `arr-users`, directory lookup | — | — | — | — | — | — |

Preserved local grants bypass that AD-only table: local Ryan and Michael both
have `FromDrobo` RW and `Public` R; local Ryan has Time Machine RW and Multimedia
R; local Michael has Multimedia RW. `hass` has `FromDrobo` RW and Public/Multimedia
R. The local administrators group includes `admin`, `badmin` and `usenet-deploy`
and has broad grants on the six earlier data shares plus the `homes` parent.
Homes' SMB administrative restriction does not establish local filesystem
isolation. These are configuration observations;
only the documented domain fixture tests establish tested SMB behavior.

Before applying the target model, save grants/SIDs/ACLs, qualify synthetic role
tests, and remove unintended private access through **both** legacy local grants
and the broad `FromDrobo`/`nas-users` route. Check new-object inheritance and all
aliases, File Station, mounts, snapshots and recycle views. Retain domain trust,
emergency access, the Time Machine chain and original Plex identities. No account
deletion, rejoin or recursive ownership rewrite is implied by this inventory.
The [FromDrobo data-migration phase](plan-nas-storage-and-access.md#fromdrobo-data-migration)
defines physical destinations, consumer cutovers, verification and rollback;
restricted aliases alone do not complete that migration.
The [service-data and archive migration](plan-nas-storage-and-access.md#service-data-and-archive-migration)
separately cuts over `Container` data and `Usenet` recovery artifacts; no service
share is complete until its mounts, permissions, export and B2 restore are tested.

Evidence: [identity rollout](operations/household-identity.md),
[NAS/Plex layout](../usenet-infra/docs/nas-plex-layout.md),
[backup scopes](../usenet-infra/docs/scheduled-backups.md), repository Compose
definitions and the dated read-only inspection summarized in the storage plan.
