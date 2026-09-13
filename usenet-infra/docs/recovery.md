> Current recovery entry points: [checkout recovery](checkout-recovery.md) for
> local files and Git history/stashes; [scheduled backups](scheduled-backups.md)
> for deployed cloud/QNAP/Plex schedules and verified archives;
> [current handoff](../../plan.md) for scope and remaining work. The manual formats
> and earlier isolated drills below remain references. NAS-loss protection is
> deferred, and full-machine replacement is separate from checkout readiness.

# Recovery

The full published-source clean-clone secrets/state drill passed: 24 vault
entries restored, 15 NAS bundle entries and six keypairs verified, and zero new
files restored on repeat. See the [September 11 report](../recovery/drills/20260911T194408Z.json).
That drill did not repeat application startup; the original bound inventory’s
full-machine `deletion_safe: false` remains unchanged. The later
[checkout recovery drill](checkout-recovery.md) passed its narrower preservation
and readiness check. Recheck current files, Git state and publication before a
later checkout deletion; neither result proves whole-machine replacement.
Start with [secrets and state recovery](secrets-recovery.md) and the current
[`plan.md`](../../plan.md) handoff. Do not delete the checkout based only on a
metadata check or a successful ciphertext transfer.

Both legacy backup decryption keys are escrowed in the small vault. The operator
selected QNAP storage for the outer master-encrypted recovery package and
confirmed the master is in 1Password and on paper. This protects Mac/cloud loss;
the NAS is not an independent backup of its own disks. Whole-Home-Assistant
recovery and native UniFi restore remain separately unproven.

The subsequently deployed Radarr/Sonarr state is covered by supplemental NAS
snapshot `20260911T201003Z-bcb62179eb783aef`: 601 files and four verified SQLite
databases. Upload, download, decryption and decryption using the clean-clone's
restored cloud-admin identity all passed. Follow the separate
[discovery backup restore procedure](discovery.md#operation-and-recovery).
This archive uses the existing escrowed cloud-admin recipient and the cloud
backup format; the original master-bundle snapshot and SOPS-bound inventory
remain unchanged. Use a published revision containing the discovery source and
public receipt when reproducing this increment from a fresh clone.

The recovery model is simple: Git recreates non-secret configuration, the
Storage Box holds the canonical catalog, and encrypted backups restore stateful
application configuration and Terraform state. The VM scratch area and QNAP
cache are disposable.

Do not begin a recovery with `terraform destroy`, a blind storage-root apply,
or a bidirectional sync. First determine which state still exists and protect
the Storage Box from mutation.

## Recovery material to maintain

Preserve these materials through the documented vault/archive chain. Replica
locations and loss boundaries are in [scheduled backups](scheduled-backups.md);
NAS-local archives do not provide NAS-loss protection:

- This repository and a reviewed revision identifier.
- Encrypted, access-controlled backups of the independent Terraform `cloud`
  and `storage` states. Storage state and saved plans contain the main and QNAP
  Storage Box passwords.
- The Hetzner project/API-token recovery procedure and the IDs of the server,
  firewall, SSH key, Primary IPs, Storage Box, and Storage Box subaccount. Do
  not put tokens or passwords in this document.
- Encrypted cloud configuration backups including SAB, Prowlarr, Radarr and
  Sonarr state, provider/indexer credentials, and the private NZBGeek Cart feed
  and processed-entry history. Host-owned daily backups run with hourly retry;
  a manual checkpoint can preserve later settings before an upgrade. See
  [scheduled backup scope](scheduled-backups.md).
- Offline copies of the operator, Storage Box writer, and QNAP public keys.
  Private keys belong in the secret store, not Git or Terraform state.
- The QNAP-specific rclone environment/configuration, private key, pinned `known_hosts`, and actual
  `/share/...` path choices in the secret/configuration backup.
- OliveTin runtime authentication material, session/configuration state and
  persistent execution history, plus the private access/TLS settings. Keep the
  declarative dashboard configuration and catalog scripts at the same reviewed
  repository revision. Runtime-generated catalog snapshots are disposable;
  remote manifests and local verification/failure state are not. Preserve
  `state/native-items` ownership receipts alongside the NAS files they describe.

For the dashboard, the concrete backup is its protected auth JSON plus
`QNAP_DASHBOARD_STATE_DIR`: `runtime/sessions.yaml` preserves sessions and
`logs/results` / `logs/output` preserve action records/output. Rebuild generated
`runtime/config.yaml` from the checked-in template and current catalog through
the adapter. Do not edit the generated file as configuration source.

The implemented cloud capture uses SQLite's backup API and integrity checks,
permits an idle or fully paused SAB queue with no post-processing, and rejects
files, databases, or remote manifests that change during capture. It does not stop application
containers. The separate QNAP capture helper is also implemented and locally
tested; its first live capture and isolated application-startup restore passed. It
uses the existing cache/refresh locks and rejects state that changes during
capture instead of stopping unrelated services.

Scheduled cloud ciphertext is stored at Storage Box `catalog/.backups/cloud`
and fetched to the NAS with the read-only account. NAS/Plex ciphertext stays
local to the NAS; it is not uploaded. These deployed copies protect the stated
cloud/checkout-loss scope, not NAS loss. Preserve the original bound snapshots
and separately retained archives; do not substitute an unverified newer file.

## Manual cloud configuration backup

From the repository root:

```sh
just usenet-backup-cloud
just usenet-backup-verify /absolute/path/to/archive.tar.age
just usenet-backup-restore /absolute/path/to/archive.tar.age /absolute/path/to/new-recovery-directory
```

`backup-cloud` installs only backup support, captures idle or fully paused cloud
state with no post-processing,
encrypts on the VM, transfers ciphertext to ignored `usenet-infra/backups/`,
then decrypts and checks the allowlisted inventory, every SHA-256, and SQLite
integrity locally. It publishes the verified ciphertext exclusively and removes
the remote temporary ciphertext only after successful local publication.
Private plaintext verification directories are cleaned up. A failed transfer
or verification retains the encrypted source on the VM for recovery.

The September 10 capture used for the isolated restore drill includes both indexer keys, Prowlarr's
rotated application key, login/client settings, restored Direct Unpack setting,
and current cloud catalog/health scripts. It verified 589 files and two SQLite
databases. The archive is
`usenet-infra/backups/cloud-20260910T225152Z-SIfVfDwC.tar.age`, mode `0600`,
with SHA-256
`07df7ddf0ec8153b5ba5c99f458bce609c6439a2ff1bfd6b34a04c5b43d07088`.
The earlier `cloud-20260910T214707Z-NCk4sDjo.tar.age` and
`cloud-20260910T223402Z-ZgJAGgVx.tar.age` archives are preserved but superseded.
They predate NZBFinder setup and Prowlarr's application API-key rotation.
The superseded `cloud-20260910T224543Z-ru5710KX.tar.age` archive is also
preserved; it predates the Direct Unpack correction.
The newer pre-VPN capture is
`cloud-20260911T001750Z-UCxzKhOY.tar.age`, ciphertext SHA-256
`c7871385ec9de9d82530accd87b0384016298855b6bb5e64f143529bc0a8309d`;
it also verified 589 files and two databases. The separate VPN/UniFi/USG archives
are enumerated in the [recovery inventory](../recovery/inventory.json) and
[secrets/state recovery](secrets-recovery.md); those root/controller settings are
outside the application backup scope.
If restoring either pre-rotation archive, rotate the restored
Prowlarr application API key before use and synchronize its protected local
dependants; do not reuse the old key. Keep older encrypted archives for
recovery history.
The backup-only play's second run reported `ok=7 changed=0`, with no application
restart. Normal cloud configuration also installs this backup support.

Capture paths are relative to `/srv/usenet`:

| Included | Scope |
| --- | --- |
| Application configuration | `config/sabnzbd`, `config/prowlarr`, `config/radarr`, `config/sonarr`, `config/rclone`, `config/catalog`, `config/catalog.env`, and its defaults |
| Operational state | `state/catalog` and the single-submission `state/sab-smoke-test.json` receipt |
| Recovery implementation | `scripts`, `libexec`, `compose/cloud`, and `compose/discovery` |
| Storage identity | Writer private key, verified Storage Box `known_hosts`, and the backup's public recipient |
| Remote metadata | Catalog manifests only, copied under `metadata/manifests` |

Bulk catalog objects, downloads, incomplete/completed scratch content, logs,
caches, prior backups, and SQLite journals are excluded. SQLite databases are
captured as standalone consistent copies. Terraform states, controller secrets
and private decryption key, and QNAP configuration are outside this cloud
archive's scope and require separate recovery material.

Encryption uses checksum-pinned age 1.3.2 binaries. The existing dedicated
cloud SSH private key remains on the workstation; only its public recipient
is installed on the VM. Keep a recoverable copy of that exact private key
separately, including after SSH-key rotation. Independent recovery of these
identities passed the clean-clone and scheduled-archive checks. Offline
verification/restoration needs the archive, that
private key, the cached verified age binary, Python, and the repository helper;
no cloud access is required once those materials are available.

`backup-verify` retains no plaintext. `backup-restore` requires a new absolute
destination and does not overwrite live files or start applications. It waits
for complete authenticated decryption before extraction, rejects unsafe paths,
links, and unexpected members, and creates `0600` files and `0700` directories.
`MANIFEST.json` preserves original UID, GID, and modes for deliberate human
reintegration; those permissions are not automatically applied. Restore the
appropriate application ownership and executable modes before using the files.
The separate offline cloud and QNAP application-startup drills below passed.
Neither replaced a live VM or NAS.

The commands above are manual checkpoints alongside the deployed host-owned
[schedules](scheduled-backups.md). Verify a new checkpoint after material
configuration changes; never resume or remove SAB jobs to satisfy backup admission.

## Verified offline cloud application restore drill

On 2026-09-10, the latest `cloud-20260910T225152Z-SIfVfDwC.tar.age` archive
passed a separate startup drill on the workstation's existing rootless Podman
runtime. Its exact pinned SABnzbd `5.1.3-ls272` and Prowlarr
`2.5.2.5491-ls158` image tags ran as native Linux/arm64 images. The live cloud
uses x86_64, so this verifies restored application configuration and startup;
it does not replace a full cloud VM recovery exercise.

The drill used this isolation and verification procedure:

1. Pull the pinned images before restoring any secrets. Decrypt through
   `backup-restore` into a fresh private directory and verify its 589 files,
   two SQLite databases, and archive checksum.
2. Copy only the two application configuration directories into unique
   disposable volumes. Give SABnzbd empty scratch space. Start unique containers
   with `--network=none`, no published ports, no restart policy, and container
   logging disabled. Verify those restrictions before startup. Mount no writer
   key, decryption key, complete archive tree, or Docker socket.
3. Query each application's loopback API from inside its isolated network
   namespace, reading its saved API credential only in memory. Record only
   allowlisted results. SABnzbd reported version 5.1.3, an empty queue, and one
   history item. Prowlarr reported version 2.5.2.5491, both expected enabled
   indexers, one enabled SABnzbd client, and preserved Forms authentication.
   Both applications accepted the restored local API credentials.
4. Stop both containers cleanly. Copy configuration to a second private
   directory and check SQLite integrity and retained settings. Use writable
   disposable database copies for SQLite journal handling after shutdown;
   never modify the original archive or source restore directory. Both
   databases passed. All rows in Prowlarr's Config, Users, Indexers,
   DownloadClients, AppSyncProfiles, Applications, IndexerProxies, and Tags
   tables were unchanged, as were SABnzbd's history and RSS tables. Every
   Prowlarr XML setting and 49 selected SABnzbd credential/provider/category,
   path, and safety values were preserved.
5. Remove only the named drill containers and volumes and both temporary
   plaintext trees. Cleanup passed. Retain only the encrypted archive and
   sanitized evidence, here `build/usenet-restore-startup-20260910.json`.

No live cloud application, port, canonical catalog object, or NAS service was
used or changed. The restored applications had no acquisition or indexer
egress. Provider/indexer communication was deliberately unavailable; existing
live connection tests cover that separately. This did not restore Terraform
state, replace the VM, perform a new download, or prove QNAP recovery.

## Manual QNAP configuration backup

The QNAP helper is implemented and has passed 17 focused local tests, including
actual age encryption and isolated restoration. The first live NAS capture
and authenticated verification passed, as did isolated application-startup
restoration. From the repository root:

```sh
just usenet-backup-qnap
just usenet-backup-qnap-verify /absolute/path/to/archive.tar.age
just usenet-backup-qnap-restore /absolute/path/to/archive.tar.age /absolute/path/to/new-recovery-directory
```

The first live archive contains 32 files and excludes media:
`usenet-infra/backups/qnap-20260910T234609Z-gr0zzbi0.tar.age`, SHA-256
`6858b4a9127ce0860acb226fa3f7592ab1bcadfd50cd6bf607b59f284df78a20`.
Capture and complete authenticated local decryption/checksum verification
passed. Runtime inventory confirms `config.yaml` and `sessions.yaml` are both
included and no hidden runtime files are missing from the allowlist.

Capture includes the stack's Compose/environment files, scripts/schema,
protected dashboard authentication, generated runtime configuration and
sessions, full action results/output history, catalog item/failure/operation
state, native ownership/integrity receipts under `state/native-items`, and the
reader key and pinned host key. Media objects, staged downloads,
and Docker client/build caches are excluded. Preserve the selected deployment
paths and numeric ownership in the recovery material.

A temporary container uses the existing pinned image, a read-only filesystem,
and no network. It opens the existing shared cache/refresh locks read-only and
checks its inventory and every hash before and after capture. Independent
OliveTin history changes cause a refusal; retry when idle. Plaintext streams
through memory and SSH to the workstation's pinned age binary. Ciphertext is
published only after complete authenticated decryption and in-memory checksum
verification. Normal capture/verification leaves no plaintext on disk.

An explicit restore requires a new absolute directory and creates files mode
0600 and directories mode 0700. Its manifest retains original ownership and
modes; reviewed deployment must reapply appropriate owners and executable bits
before using the restored stack. The helper rejects unexpected SQLite files,
unsupported custom layouts, more than 25,000 files, or more than 128 MiB. These
bounds and stable-capture checks are deliberate failure conditions, not a
reason to omit changed configuration silently. The separate deployed NAS
scheduler uses the current helper; see [scheduled backups](scheduled-backups.md)
for archive-capture evidence and freshness.

## Verified offline QNAP application restore drill

The 32-file `qnap-20260910T234609Z-gr0zzbi0.tar.age` archive passed a separate
startup drill on 2026-09-10. `backup-qnap-restore` extracted a verified copy into
a new private directory. Only copies of dashboard/catalog state, scripts,
the versioned template, and dashboard authentication were placed into isolated
volumes. The production environment file and Storage Box reader key remained
unmounted. Original backup bytes were unchanged.

The existing pinned OliveTin 3000.19.0/rclone 1.75.1/Python 3.14.7 dashboard
image ran on local Linux/arm64 as UID 1004/GID 100, with read-only root, all
capabilities dropped, no new privileges, network disabled, and no published
ports. The effective test environment used an empty local catalog fixture and
fresh empty cache. Private copied files received the runtime ownership/modes
needed for startup; the original restored tree was not modified.

OliveTin returned ready HTTP 200, refreshed the empty fixture successfully,
and denied anonymous history with HTTP 403. Its startup loader reported all
three saved action results loaded, zero skipped, and no session-load error.
After clean shutdown, opaque authentication bytes, saved session bytes, and
all six history result/output files exactly matched the archive. No password
was requested, read, changed, or used for a test login; this checks preservation
and startup, not a fresh password-login attempt.

All temporary plaintext trees and the exact test containers/volumes were
removed. Sanitized evidence is
`build/usenet-qnap-restore-startup-20260910.json`; its ignored reproducible
harness is `build/qnap-restore-startup-drill.py`. The live NAS was untouched.
This proves application configuration/session/history restoration on arm64;
it does not replace the x86_64 NAS. The separate live CLI drill already proved
that the authorized test item can be pulled, independently hashed, and safely
evicted while the dashboard is stopped, with remote files/manifests unchanged.

## Lost cloud VM

1. Confirm in Hetzner Console that the existing Storage Box, its current tier,
   and its canonical data still exist. It may be BX11, BX21, BX31, or BX41. Do
   not run the `storage` Terraform root.
2. In `terraform/cloud`, restore its encrypted state and run `terraform plan`.
   Review any replacement carefully. If the cloud state is unavailable, follow
   [Lost Terraform state](#lost-terraform-state) before applying.
3. Recreate or repair only the cloud resources. The explicit protected Primary
   IPs should remain stable across a planned server replacement.
4. Restore SAB, Prowlarr, Radarr and Sonarr configuration and the relevant
   service definitions from the reviewed source/backup, preserving dedicated
   identities, ownership and private permissions. Preserve SAB pauses, Cart RSS
   state and Arr monitoring; inspect jobs before allowing resumed acquisition.
5. Restore the writer key and verified host pin, then establish the synchronous
   Storage Box mount. Verify `usenet-library.service` and its real Movies/TV
   directories before starting Arr through `usenet-discovery.service`. Preserve
   `Requires`/`BindsTo` mount dependencies and mode-0000 unmounted protection;
   never replace a failed mount with an ordinary writable directory.
6. Restore the existing private LAN route/proxy and loopback backend bindings.
   Use the LAN application URLs; the documented SSH tunnel is an optional
   recovery access path. Confirm there are no public application UI listeners.
7. Check provider/indexer connectivity and the saved Cart feed without submitting
   a job. Its Default-category jobs bypass Arr ownership. Restore acquisition
   only after reviewing actual queue/history and the intended import route.
8. Keep the retired publisher disabled. Inspect canonical native-library and
   local operation metadata without moving unknown scratch or republishing Arr
   content. Reconcile lost or completed jobs using Arr’s supported workflow.
9. Validate any user-selected fresh completion through import, cleanup and Plex
   discovery under the [current acceptance scope](../../plan.md#closure-and-merge-criteria).
   Do not enqueue a diagnostic job or manually promote Arr-owned scratch merely
   to finish a recovery checklist.

Outcome: jobs that existed only on VM scratch may be lost, but the published
catalog remains available.

## Lost QNAP configuration

1. Stop the old Container Station application if any fragments still run. Do
   not manage the same stack simultaneously from the GUI and command line.
2. Recreate the dedicated shared folders and the absolute `/share/...` paths
   documented for this NAS, preserving the separate movie/TV sources and
   staging paths. Restore the QNAP Compose files from Git. Verify Plex ID 3
   still scans `TV Shows/library` before enabling the native TV copy gate.
3. Restore only the QNAP subaccount's key, rclone configuration, verified
   Storage Box host key, dashboard authentication/runtime state, and native
   ownership receipts. Restore correct numeric ownership and restrictive
   permissions. Never copy the main
   writer credential to the NAS.
4. Confirm in Hetzner Console/Terraform that the subaccount is rooted at
   `catalog`, externally reachable, SSH-enabled, and read-only.
5. Start the [QNAP Compose stack](../compose/qnap/compose.yaml) through the
   [QNAP runbook](../compose/qnap/README.md). Confirm private binding and
   authentication before using the dashboard. Run `catalog-list`/`catalog-status`
   and `native-list`/`native-status` before requesting any large pull; confirm
   that execution history from the backup is readable.
6. Prove the safety boundary during acceptance testing: reading a known item
   must work, while an attempted write to a disposable test name through the
   QNAP credential must be rejected. Do not target an existing catalog object.
7. Refresh the dashboard and select only wanted titles, or use `native-pull`
   (`catalog-pull` for legacy items). Existing native files require their
   matching ownership receipt and verified directory identity/bytes; listing
   does not regenerate that authority. Preserve unmatched files for recovery
   review rather than adopting, overwriting or deleting them.

Legacy manifests remain remote. Native ownership receipts are NAS state and must
be restored and validated; their presence alone does not authorize a changed
directory or replacement volume. A new copy into an absent destination produces
a new verified receipt.

## Dashboard unavailable

The UI is not required for recovery. From `usenet-infra/` on the workstation,
with the dedicated QNAP SSH connection settings restored:

```sh
just catalog-list
just catalog-status
just catalog-pull "item-id"
just catalog-evict "item-id"
just native-list
just native-status
just native-pull "native-<id>"
just native-evict "native-<id>"
just qnap-health
```

These use the same guarded legacy/native backends as the dashboard.
An eviction still removes only the NAS copy; it never invokes remote deletion.
Do not introduce direct rclone copy/delete actions to bypass an unavailable UI.

Inspect only this project's Compose service status and logs, validate its
configuration, and restore the pinned image plus ignored authentication state
as described in [QNAP Compose](../compose/qnap/README.md). Keep published
addresses private during repair. If login material was lost, create replacement
runtime credentials through the supported setup and invalidate old sessions;
do not weaken authentication to get the page working.

On an interrupted pull, inspect catalog status before retrying. The shared lock
prevents parallel mutation. An abandoned transfer is reported failed/stalled;
retry retains hash-verified staged files and repeats full verification before
publication. Keep unresolved failure/history records for diagnosis. A browser
window closing does not establish that a server-side transfer stopped.

## QNAP disk failure

1. Replace or repair the affected NAS storage using the QNAP-supported process.
2. Recreate the cache and staging shared folders with enough free space and the
   expected container UID/GID permissions. Preserve the Plex source/staging
   separation and 100 GiB reserve.
3. Restore the QNAP configuration as above.
4. Run `native-list` and `catalog-list`; select only wanted titles for new copies.
   Restored native receipts refer to the former volume’s directory identity,
   so preserve them for review and do not use them to adopt replacement files.
   The guarded pull verifies bytes and publishes into an absent destination.
5. If a failed pull left staging data, retry without `--inplace`. rclone can
   avoid retransferring completed files, but an interrupted partial file may
   restart from zero.

The Storage Box remains canonical throughout. Never use a sync command whose
destination deletions could be inferred from an empty replacement disk.

## Lost Terraform state

The two roots are independent. Treat them independently and recover the
`storage` root first only when its state is the one that is missing.

### General procedure

1. Stop all Terraform applies and revoke any exposed state/backend credential.
2. Prefer restoring the newest encrypted state backup. Verify that its lineage,
   serial, and resource IDs match the live Hetzner project, then run
   `terraform plan` without applying.
3. If no usable backup exists, inventory live resources in Hetzner Console/API
   and record exact numeric IDs. Copy the relevant `.tfvars.example` to an
   ignored `.tfvars`, provide the original sensitive values through the normal
   secret workflow, and initialize the root.
4. Import every live resource into the exact address used by this repository.
5. Run `terraform plan`. Resolve configuration/state differences until the
   reviewed plan contains no unintended replacement, deletion, protection
   disablement, or second Storage Box.
6. Back up the recovered state immediately and rotate any password/token that
   may have been exposed.

### Storage imports

An empty storage state makes Terraform propose creating a new Box; it does not
discover or adopt the existing canonical Box. Do **not** apply that plan.
Import the live resources instead:

```sh
terraform -chdir=usenet-infra/terraform/storage init
terraform -chdir=usenet-infra/terraform/storage import \
  hcloud_storage_box.catalog "$STORAGE_BOX_ID"
terraform -chdir=usenet-infra/terraform/storage import \
  hcloud_storage_box_subaccount.qnap_reader \
  "$STORAGE_BOX_ID/$STORAGE_BOX_SUBACCOUNT_ID"
terraform -chdir=usenet-infra/terraform/storage plan
```

The compound subaccount import ID is documented by the official
[`hcloud_storage_box_subaccount` resource](https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/storage_box_subaccount).
The Box itself imports by numeric ID per the
[`hcloud_storage_box` resource](https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/storage_box).
The configuration's `prevent_destroy` and provider-side delete protection
remain mandatory after import.

Before the post-import plan, make the configured `storage_box_type` match the
live tier. Otherwise Terraform will legitimately propose an in-place upgrade or
downgrade immediately after import. Capacity changes are never part of state
recovery; perform them later as a separate reviewed operation.

### Cloud imports

Import live cloud resources if preserving their identities matters:

```sh
terraform -chdir=usenet-infra/terraform/cloud init
terraform -chdir=usenet-infra/terraform/cloud import hcloud_ssh_key.admin "$SSH_KEY_ID"
terraform -chdir=usenet-infra/terraform/cloud import hcloud_primary_ip.ipv4 "$IPV4_ID"
terraform -chdir=usenet-infra/terraform/cloud import hcloud_primary_ip.ipv6 "$IPV6_ID"
terraform -chdir=usenet-infra/terraform/cloud import hcloud_firewall.server "$FIREWALL_ID"
terraform -chdir=usenet-infra/terraform/cloud import hcloud_server.acquisition "$SERVER_ID"
terraform -chdir=usenet-infra/terraform/cloud plan
```

If the VM is truly gone, import the still-live protected Primary IPs, firewall,
and SSH key before allowing Terraform to create only the missing server. Never
guess IDs. A no-change or explicitly understood plan is the recovery gate.

## Interrupted capacity change

Do not recreate the Storage Box. A BX11/BX21/BX31/BX41 type change is an
in-place Hetzner API action and the Terraform provider waits for that action.
If the operator or Terraform process was interrupted:

1. Check the live Storage Box ID, type, status, used bytes, and action history in
   Hetzner Console/API.
2. Restore the storage state backup if state was lost, or refresh and plan from
   the existing state. Import the existing Box if necessary.
3. Set the configured type to the live result and require a no-replacement plan
   before taking another action.
4. Verify catalog manifests and representative hashes, then QNAP read-only
   listing and pull behavior.
5. Retry an upgrade only after the prior action has conclusively succeeded or
   failed. Never use delete/recreate as a resize mechanism.

Hetzner allows downgrade only when total use is below the target tier. Snapshot
data consumes quota, and BX11/BX21/BX31/BX41 have 10/20/30/40 snapshot slots
respectively. Preserve or reduce excess snapshots before downgrading. See the
official [scaling rules](https://docs.hetzner.com/storage/general/which-storage-is-right-for-me/),
[snapshot behavior](https://docs.hetzner.com/storage/storage-box/snapshots/),
and the provider's
[in-place type update](https://github.com/hetznercloud/terraform-provider-hcloud/blob/v1.68.0/internal/storagebox/resource.go#L432-L447).

## Lost application configuration

1. Stop the affected Compose services to avoid writes during restore.
2. Preserve the failed configuration directory for forensics; do not overwrite
   the only copy of it.
3. Restore the affected SAB/Prowlarr/Radarr/Sonarr configuration, permissions and
   ownership. Verify the real library mount and systemd mount dependencies before
   starting Arr; use the [native media](native-media.md) recovery invariants.
4. Confirm provider/indexer endpoints, strict TLS, categories, scratch/library
   paths and API connectivity. Preserve the enabled Cart RSS feed and its
   processed-entry history, pauses and Arr monitoring. Cart jobs do not become
   Arr-owned simply because their files are on completed scratch.
5. Verify loopback backend bindings and the authenticated private LAN proxy;
   the SSH tunnel remains an optional access path.
6. Reconcile jobs completed after the backup through the owning application.
   Keep the retired publisher disabled, and preserve unknown scratch for review.
   Do not reset feed history, enqueue tests or run a second mover to force success.

## Recovery acceptance

Choose the drill’s scope through the
[closure and merge criteria](../../plan.md#closure-and-merge-criteria). Record only
what that drill actually establishes:

- A source/state restore verifies archive integrity, identities, required files,
  ownership and application configuration without changing canonical media.
- A cloud startup check verifies mount-before-Arr dependencies, private proxy
  access, saved acquisition/Cart state and the disabled publisher. Restored
  queue/history must be reviewed before acquisition resumes.
- A NAS restore verifies native ownership receipts, separate source/staging roots,
  read-only canonical access, authentication and retained action history. General
  Plex roots/profile grants must remain separate from the private library.
- A fresh media acceptance, when authorized, follows a user-selected Arr-owned
  completion through import/cleanup, selective NAS copying and Plex discovery.
  A Cart download needs its intended import route verified separately. Legacy
  promotion tests are limited to independent items, never Arr-owned scratch.
- Any destructive-state or machine-replacement drill requires reviewed scope;
  Terraform must not propose unintended Storage Box replacement or deletion.
  NAS-loss protection remains deferred.

Use [validation](validation.md) for accepted and pending outcomes, and retain a
sanitized dated receipt. The existing clean-clone, checkout and isolated startup
drills prove their recorded scopes; they do not establish a later checkout’s
readiness, full machine replacement or device playback. Preserve immutable
snapshots and historical decryption keys. Do not include credentials or private
library contents in Git or logs.
