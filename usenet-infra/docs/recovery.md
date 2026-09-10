# Recovery

The recovery model is simple: Git recreates non-secret configuration, the
Storage Box holds the canonical catalog, and encrypted backups restore stateful
application configuration and Terraform state. The VM scratch area and QNAP
cache are disposable.

Do not begin a recovery with `terraform destroy`, a blind storage-root apply,
or a bidirectional sync. First determine which state still exists and protect
the Storage Box from mutation.

## Recovery material to maintain

Keep the following outside the machines they recover:

- This repository and a reviewed revision identifier.
- Encrypted, access-controlled backups of the independent Terraform `cloud`
  and `storage` states. Storage state and saved plans contain the main and QNAP
  Storage Box passwords.
- The Hetzner project/API-token recovery procedure and the IDs of the server,
  firewall, SSH key, Primary IPs, Storage Box, and Storage Box subaccount. Do
  not put tokens or passwords in this document.
- Encrypted backups of `/srv/usenet/config/sabnzbd` and
  `/srv/usenet/config/prowlarr`. These directories contain both application
  state and provider/indexer secrets. Back them up on a schedule and before an
  upgrade; test a restore periodically.
- Offline copies of the operator, Storage Box writer, and QNAP public keys.
  Private keys belong in the secret store, not Git or Terraform state.
- The QNAP-specific `rclone.conf`, private key, pinned `known_hosts`, and actual
  `/share/...` path choices in the secret/configuration backup.

Keep the primary encrypted application-config backup outside both the VM and
Storage Box. An additional convenience copy may live outside the `catalog`
directory on the Storage Box, where the catalog-rooted QNAP subaccount cannot
read it, but that copy is not independent recovery coverage.

## Lost cloud VM

1. Confirm in Hetzner Console that the existing Storage Box, its current tier,
   and its canonical data still exist. It may be BX11, BX21, BX31, or BX41. Do
   not run the `storage` Terraform root.
2. In `terraform/cloud`, restore its encrypted state and run `terraform plan`.
   Review any replacement carefully. If the cloud state is unavailable, follow
   [Lost Terraform state](#lost-terraform-state) before applying.
3. Recreate or repair only the cloud resources. The explicit protected Primary
   IPs should remain stable across a planned server replacement.
4. Run the host provisioning playbook, then restore
   `/srv/usenet/config/sabnzbd` and `/srv/usenet/config/prowlarr` with the
   configured PUID/PGID ownership and restrictive permissions.
5. Restore the writer's Storage Box SSH key and a `known_hosts` entry verified
   against [Hetzner's published fingerprints](https://docs.hetzner.com/storage/storage-box/backup-space-ssh-keys/).
6. Start the [cloud Compose stack](../compose/cloud/compose.yaml). Reach the UIs
   only through SSH tunnels; confirm no service listens publicly.
7. Test Eweka over TLS, the fill provider, and each indexer without enabling an
   unattended acquisition rule.
8. Run `catalog-status`, inspect local failure records, and inspect remote
   `.incoming` content. Do not publish or delete an incomplete item until its
   source, hashes, and manifest state are understood.
9. Promote a small authorized test item, verify it from the read-only endpoint,
   and leave the canonical library untouched otherwise.

Outcome: jobs that existed only on VM scratch may be lost, but the published
catalog remains available.

## Lost QNAP configuration

1. Stop the old Container Station application if any fragments still run. Do
   not manage the same stack simultaneously from the GUI and command line.
2. Recreate the dedicated shared folders and the absolute `/share/...` paths
   documented for this NAS. Restore the QNAP Compose files from Git.
3. Restore only the QNAP subaccount's key, rclone configuration, and verified
   Storage Box host key. Never copy the main writer credential to the NAS.
4. Confirm in Hetzner Console/Terraform that the subaccount is rooted at
   `catalog`, externally reachable, SSH-enabled, and read-only.
5. Start the [QNAP Compose stack](../compose/qnap/compose.yaml). Run
   `catalog-list` and `catalog-status` before requesting any large pull.
6. Prove the safety boundary during acceptance testing: reading a known item
   must work, while an attempted write to a disposable test name through the
   QNAP credential must be rejected. Do not target an existing catalog object.
7. Selectively run `catalog-pull` for wanted items. Local item-state records
   are regenerated after each verified pull.

The catalog manifests are remote, so loss of QNAP local state does not erase
catalog identity or hashes.

## QNAP disk failure

1. Replace or repair the affected NAS storage using the QNAP-supported process.
2. Recreate the cache and staging shared folders with enough free space and the
   expected container UID/GID permissions.
3. Restore the QNAP configuration as above.
4. Run `catalog-list`; select only the content wanted locally and pull it again.
   Each pull stages under `.partial`, verifies byte counts and SHA-256 hashes,
   then atomically installs the cache directory.
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
3. Restore the latest encrypted SABnzbd/Prowlarr config backup, permissions, and
   ownership. Start the services and inspect logs.
4. Confirm provider hosts, TLS ports, fill-server priority, indexer endpoints,
   categories, incomplete/complete paths, and API connectivity. Re-enter a
   credential from the secret manager if the backup predates a rotation.
5. Confirm the services still bind only to `127.0.0.1`; use SSH tunnels for UI
   checks.
6. Reconcile any jobs completed after the backup manually. Do not automatically
   promote an unknown directory: generate and review its provenance and hashes
   first.

## Recovery acceptance

A drill is complete only when:

- Terraform plans show no unintended destruction or replacement.
- SABnzbd and Prowlarr are unreachable directly from the public Internet.
- A small authorized job completes locally and is deliberately promoted.
- The published manifest and remote bytes verify.
- The QNAP credential reads and pulls the item but cannot create, overwrite, or
  delete a disposable remote test name.
- `catalog-evict` removes only the QNAP cache copy.
- The remote catalog object still verifies after eviction.
- Git and logs contain no credentials.
