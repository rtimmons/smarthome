# NAS access model

Start with the [migration plan](plan-nas-storage-and-access.md) for current work
and sequencing. This document owns the target namespace and access policy;
[protection policy](plan-nas-data-protection.md) owns recovery. Unless explicitly
marked deployed, account/share names and grants below are targets, not tested
live permissions. The [service inventory](nas-service-inventory-2026-10-27.md)
records dated runtime principals and dependencies.

## Share catalog

Use flat, named service datasets and separate archive shares. No AppData umbrella.
`wiki` and `PrivatePlexLibrary` are deployed; the latter replaces the former
proposed name `PrivateLibrary`. Native package state stays at supported package paths.

| Share | Contents / existing source |
| --- | --- |
| `PrivatePlexLibrary` | Private originals relocated from `FromDrobo` on October 28 |
| `Documents` | Explicitly classified shared originals; no current Public payload is assigned here |
| `home` (Ryan) | Canonical AD personal home; destination for both Public folders after privacy/backup pilot; homes enabled on Scratch, personal path unqualified |
| `home` (Michael) | Canonical AD personal home; homes enabled on Scratch, personal path and isolation unqualified |
| `homes` | Administrative parent of all personal homes; not a household-wide share |
| `MediaCache` | Replaceable local movie/TV copies under `FromDrobo` |
| `PlaybackCache` | Disposable rclone cache currently at `FromDrobo/.remote-cache`; service-only local storage |
| `RemoteMedia` | Read-only media-only view of the existing remote mount |
| `RemoteManage` | Writable view of the same media; new gateway requires qualification |
| `RemoteFiles` | General remote files; proposed Ryan-owned scope |
| `Hetzner` | Entire account filesystem, including hidden directories and backups; new full-account gateway |
| `TransferStaging` | Existing Filex staging; proposed shared temporary area |
| `forgejo` | Repositories, database, LFS/attachments, configuration and keys; existing `Container/home-git` |
| `forgejo-backups` | Completed encrypted Forgejo recovery archives; existing `Usenet/Backups/automatic/forgejo` |
| `jellyfin` | Jellyfin database, configuration, plugins and persistent metadata; current `jellyfin-trial` state |
| `media-control` | Catalog/copy state, manifests, receipts and required configuration |
| `filex` | Filex configuration, host keys and persistent state; payloads remain in `TransferStaging` |
| `dns` | Resolver and discovery configuration/state, separated by subfolder ACLs |
| `wiki` | Reproducible published site and runtime configuration; source remains in Git |
| `remote-reader` | Read-only mount service configuration/credentials; no mounted remote content or cache bytes |
| `remote-maintainer` | Configuration/credentials for the proposed media-only writable gateway |
| `hetzner-gateway` | Configuration/credentials for the proposed full-account gateway |
| `backup-control` | Backup scripts, schedules, per-job configuration/credentials and status; distinct job subfolders |
| `infrastructure-backups` | Encrypted NAS/application/cloud recovery artifacts, excluding Forgejo and native HA archives |
| `HomeAssistantBackups` | New dedicated native HA archive destination; currently no HA NAS backup mount |
| `SpaceBlackTimeMachine` | Existing laptop backup share/chain; preserve its name |

### Personal homes

Use each person's resolved AD `home` as the eventual canonical personal scope.
`homes` is the administrative parent, not a shared household folder. Local and
AD usernames are not interchangeable identities. Owner RW, other-owner denial
and scoped backup reads must be tested before moving personal files. Preserve
local recovery and deployment homes/SSH keys. Service homes are separately
inventoried inputs, not automatically human files or application state.

### Shared and remote data

Ryan alone maintains private media; Ryan and Michael maintain general media.
`RemoteMedia` and `RemoteManage` expose the same approved media leaves as R and
RW views; exclude backup and acquisition-staging parents. `Hetzner` deliberately
exposes the full account under explicit R/RW roles, including hidden and backup
files. Human membership in those broad roles remains undecided. Full-account
access bypasses narrower views' restrictions on the same objects; it does not
grant provider billing, NAS administration or B2 credentials. Keep the current
server-enforced read-only backend credential read-only; writable gateways require
separate supported credentials. Preserve managed-media ownership/receipts when
editing remote files.

## Service-account naming policy

Managed service accounts use `svc-<purpose>`. Keep runtime identities, directory
lookup, application logins, deployment operators, capture producers and archive
uploaders separate. A runtime does not automatically need an AD account or SMB
password. Preserve provider-issued identifiers and document vendor/package
exceptions instead of recreating identities for naming consistency.

Existing AD `svc-authelia` and `svc-jellyfin` remain lookup-only accounts;
`svc-jellyfin-runtime` is a different proposed OS principal. Wiki's local
`svc-wiki` is UID 1005 with runtime GID 1000 (`wiki-reader`). Its local account's
primary group remains `everyone`/100; the container uses only group 1000.
Credentials use existing SOPS escrow, with no new password-reader container.

### NAS deployment identity

`usenet-deploy` is currently the separate deployment operator in purpose, but
its QTS administrator membership can override data ACLs. Preserve its dedicated
key and login. `svc-nas-deploy` is a later naming target, not a current rename.
Local recovery administrators remain separate from daily human identities.

### Service-account migration

Separate runtime UID/GID variables and transfer only each service's enumerated
state before considering a deployment-account rename. Save realm, UID/GID/SID,
ACLs, mounts, cron and credential references privately. Test each supported
identity change independently of path relocation and preserve rollback.
Do not bulk chown shared trees, replace existing AD accounts or change the shared
`qnap_uid` to simulate isolation. Inventory actual `hass` consumers before
removing its broad access. Native Plex/HBS and privileged mount helpers retain
explicit exceptions until supported narrower identities are qualified.

## Accounts → roles

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

`git-users` and `arr-users` grant application access, not NAS filesystem rights.
Unassigned roles stay unassigned; current compatibility groups are not implicit
members of new private roles. Separate backup destination credentials from source
roles; provider/B2 policies must enforce their own scopes.

## Roles → share permissions

R = list/read/traverse. RW also permits create/modify/rename/delete, not permission
administration. — = no grant. Test combined memberships and alternate paths;
these tables are policy, not proof that existing ACLs already enforce it.

| Data role | PrivatePlexLibrary | MediaCache | RemoteMedia | RemoteManage | TransferStaging | Time Machine |
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

The target model for `PrivatePlexLibrary` grants Ryan's maintainer role RW and
Plex's private-reader role R; ordinary Michael/general-media, guest, lookup and
unrelated service roles receive no grant. Backup reading can be temporarily
inactive under the approved migration exception. Administrators/native root
processes remain explicit bypass exceptions. Preserve the tree's metadata during
the rename; inventory and fix excess filesystem ACLs as a separate checkpoint,
without claiming SMB denial establishes host/container isolation.

The October 28 path checkpoint explicitly approved RW for existing **local**
`ryantimmons` and `badmin`, with native administrator exceptions, guest denied,
and access-based visibility enabled. The user subsequently approved AD Ryan RW
on this share and a separate additive root/default filesystem ACL entry.
Encrypted SMB3 synthetic create/readback/delete passes for AD Ryan; AD Michael
remains denied at authenticated tree connect. All existing ACL entries were
preserved, with no recursive changes. Existing descendant access was not tested;
broad filesystem grants still need separate review.

## Plex viewer boundaries

One Plex runtime can read several libraries. Preserve private library ID 1,
general IDs 2/3/4/5, metadata, watched state and the existing owner identity.
The managed general-viewing profile must remain denied ID 1; Michael's exact
native Plex profile linkage must be verified, not recreated. Viewer roles are
Plex policy labels, not automatic AD group synchronization. General library roots
must not include the private share or a broad parent exposing it. OS-level
separation between private and general playback would require separate server
instances; that is not part of the path migration.

## Access acceptance

Check SMB and QTS application grants, effective local ACLs, container binds and
native-process authority separately. Test intended read/write operations with
synthetic files where useful and expected denials without listing private media.
Qualify SMB encryption/signing compatibility before global changes. Keep native
app API/client authentication intact; Authelia does not cover every compatibility
HTTP/ingress route. A session refusal using a SOPS credential is not independent
proof of password correctness or an authenticated per-share denial.
