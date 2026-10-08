# Recovery

Git supplies current nonsecret source; encrypted archives supply application
state and private inputs; the Storage Box holds canonical media. Start with
[secrets recovery](secrets-recovery.md) for the SOPS vault and bound snapshots,
[checkout recovery](checkout-recovery.md) for local Git/ignored work, and
[scheduled backups](scheduled-backups.md) for current cloud/NAS/Plex settings.
Preserve original bound evidence and recovery identities unchanged.

Do not start with `terraform destroy`, a blind storage apply or bidirectional
sync. Identify the lost component and protect surviving storage first. Settings
backups exclude media, unfinished downloads, Plex artwork and installation
binaries. NAS originals and replacement NAS boot are outside the chosen scope.
[Validation](validation.md) records the isolated restore/startup tests and limits.

## Verify before restoring

From the repository root, using the existing dedicated decryption identities:

```sh
just usenet-backup-verify /absolute/archive.tar.age
just usenet-backup-restore /absolute/archive.tar.age /absolute/new/cloud-restore
just usenet-backup-qnap-verify /absolute/qnap.tar.age
just usenet-backup-qnap-restore /absolute/qnap.tar.age /absolute/new/qnap-restore
```

Use a new private destination, never running state. Cloud and QNAP archives have
distinct formats; neither is a master `recovery-bundle` archive. Verify every
manifest member and SQLite snapshot, expected app/credential coverage and receipt
hashes. Ciphertext upload/readback alone does not prove decryption or coverage.
Keep decrypted content, exact media paths and raw manifests out of Git/output.
Use [Filex recovery](filex-recovery.md) for its nested bundles and operator escrow.

## Lost cloud VM

1. Inspect the surviving canonical Box and repair volume. Restore the cloud
   Terraform state, review its plan and recreate only intended cloud resources.
   Preserve current BX21/repair-volume inputs, Primary IP identities and delete
   protection. Never apply an old saved plan or replace storage as a side effect.
2. Restore current configuration, databases, writer key and pinned hosts with
   original private permissions. Include Seerr, Filex, the native ownership marker,
   all 44 historical journals and disposition/integrity receipts. Preserve SAB
   global/per-job pauses and Arr monitoring. Keep acquisition isolated during review.
3. Bootstrap the cloud role with `cloud_start_compose: false` until storage
   units and accepted configuration are restored. Install current helpers and
   pinned images. Configure the library service,
   then [reconstruct current storage units](repair-spool.md). Verify device UUID,
   underlying mode-0000 directories, completed-path mapping and actual mounts.
   Do not replay remote/hybrid/spool migrations. Old archives can contain retired
   executables; never enable publisher/cart/admission/maintenance timers.
4. Start SAB/Arr only through their mount-dependent systemd services. Restore
   the scoped VPN/private proxy and confirm backend ports stay loopback-only.
   Verify authenticated APIs, native ownership, limits, journal preservation and
   disabled direct feeds. Do not submit a diagnostic download or resume old jobs.
5. Reconcile exact existing Arr/SAB identities before allowing explicit requests.
   Unknown or lost scratch is not permission to reacquire, publish or delete it.
   Check scheduled backups and independently restore the new accepted checkpoint.

For a replacement-server rehearsal, use isolated fixture storage and credentials
with acquisition/egress blocked. Follow the [drill boundary](replacement-drill-20260922.md).
Its October 8 success does not prove live NAS/VPN/provider integration.

## Lost QNAP configuration or cache

Restore settings and authentication to a new private directory first. Preserve
`qnap_data_root: /share/FromDrobo`, `qnap_catalog_cache_dir: /share/FromDrobo/Movies`,
`qnap_native_tv_copy_enabled: true` and `qnap_backup_offhost_required: true` in
current inventory. Restore the canonical read-only identity separately from the
confined NAS-backup writer. Do not grant canonical write access to repair a mount.

Keep Plex library IDs and profile grants from [NAS layout](nas-plex-layout.md).
General roots must exclude private media and staging. Do not empty Plex trash
when storage is unavailable. Settings archives contain Preferences and databases,
not originals, artwork or a Plex installation.

For the dashboard, preserve auth, sessions, action history, verification/failure
receipts and `state/native-items`. Rebuild generated presentation from source;
its cache is disposable. Verify existing copy identity and bytes before treating
restored receipts as ownership on a rebuilt volume. Pull only selected missing
copies from canonical storage; never adopt unrelated files or sync the collection.

A dashboard failure does not require restarting Plex or the NAS. Inspect its
container, authenticated route and refresh heartbeat, then redeploy only the
presentation/backend while no transfer is active. Preserve transfer locks and
staged files until their operation records have been reconciled.

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
