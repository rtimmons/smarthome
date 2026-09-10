# Hetzner Terraform

This directory intentionally contains two independent Terraform roots:

- `cloud/` manages the replaceable acquisition VM, its SSH key, firewall, and explicit Primary IPv4 and IPv6.
- `storage/` manages the canonical Storage Box and the QNAP's read-only subaccount.

Run Terraform separately in each directory. The roots must never share a state file or a remote-backend key. A VM rebuild must not be able to destroy the canonical catalog as an incidental dependency.

## Prerequisites

1. Install a Terraform release in the supported range shown in `versions.tf`.
2. Create a dedicated Hetzner project and a Read & Write API token for it.
3. From `usenet-infra/`, store the token through the non-echoing helper:

   ```sh
   just store-hcloud-token
   ```

The helper writes an ignored, mode-0600 `secrets/hetzner.env`; the Terraform
wrapper refuses a more permissive file and sets a restrictive umask for state
and saved plans. Do not put the API token in Git or in `terraform.tfvars`.

Run `just generate-ssh-keys`, then `just prepare-terraform-vars` to create the
four purpose-specific keypairs and ignored, mode-0600 inputs. Terraform consumes
the cloud administrator, Storage Box writer, and Storage Box QNAP-reader public
keys; the fourth key authenticates the dedicated QNAP administrative account.
The preparation helper restricts cloud SSH to the current public IPv4. If the
operator network later changes, edit only `admin_ssh_cidrs` in the existing cloud
tfvars; do not regenerate the storage passwords.

The provider is constrained to `hetznercloud/hcloud ~> 1.68.0`. Commit each root's generated `.terraform.lock.hcl` after `terraform init` so future runs use the reviewed provider build.

## Cloud root

Copy and edit the example without committing the resulting file:

```sh
cp usenet-infra/terraform/cloud/terraform.tfvars.example usenet-infra/terraform/cloud/terraform.tfvars
./usenet-infra/scripts/terraform-with-token -chdir=usenet-infra/terraform/cloud init
./usenet-infra/scripts/terraform-with-token -chdir=usenet-infra/terraform/cloud plan -out=cloud.tfplan
./usenet-infra/scripts/terraform-with-token -chdir=usenet-infra/terraform/cloud apply cloud.tfplan
```

`cx43` is the default because it supplies 8 shared x86 vCPUs, 16 GB RAM, and 160 GB NVMe at the only price point compatible with the original total-budget target. Cost-optimized capacity is limited, so change `server_type` or `location` if it is unavailable. Measure a representative PAR repair and unpack before deciding whether to pay for `cpx42` (newer shared CPU, 320 GB NVMe) or `ccx23` (four dedicated CPU threads, 160 GB NVMe).

The Ubuntu image lookup explicitly requests x86. The default is the current Ubuntu 26.04 LTS image; change `image_name` only after checking that the replacement is available in Hetzner Cloud.

Only SSH from `admin_ssh_cidrs` and ICMP are permitted inbound. SABnzbd and Prowlarr are deliberately not exposed. The configuration creates both Primary IP families explicitly, keeps them independent of server deletion, and enables provider-side delete protection on the server and addresses. Hetzner requires server delete and rebuild protection to have the same value.

To intentionally destroy or rebuild protected cloud resources, first change the protection attributes to `false`, apply that reviewed change, and only then perform the destructive operation.

## Storage root

Prepare unique passwords and all initial main-account SSH keys before the first apply:

```sh
cp usenet-infra/terraform/storage/terraform.tfvars.example usenet-infra/terraform/storage/terraform.tfvars
./usenet-infra/scripts/terraform-with-token -chdir=usenet-infra/terraform/storage init
./usenet-infra/scripts/terraform-with-token -chdir=usenet-infra/terraform/storage plan -out=storage.tfplan
./usenet-infra/scripts/terraform-with-token -chdir=usenet-infra/terraform/storage apply storage.tfplan
```

The initial `bx11` tier provides 1 TB. To grow, change only
`storage_box_type` to `bx21`, `bx31`, or `bx41`, review the plan for an in-place
update, and apply it. The provider uses Hetzner's change-type action rather than
replacing the box. Upgrade before usage reaches 90%; the operational warning
starts at 80%. A downgrade is possible only when usage, including snapshots,
fits in the smaller tier.

The Storage Box has both Hetzner API delete protection and Terraform `prevent_destroy`. The QNAP subaccount also has `prevent_destroy`. Removing either guard is a deliberate, reviewed break-glass action. Do not use `terraform destroy` as a routine cleanup command in this root.

The main account is not externally reachable and is reserved for the writer on Hetzner Cloud. The QNAP subaccount is externally reachable but rooted at `catalog` and has server-enforced `readonly = true`, preventing it from uploading, modifying, or deleting canonical objects.

### State is secret

The hcloud provider currently requires the Storage Box and subaccount passwords as sensitive resource attributes. Terraform's `sensitive` marking hides values from normal output, but the values still exist in state and in saved plan files.

- Never commit `terraform.tfstate`, `.tfvars`, or `*.tfplan` files.
- Restrict local state and saved-plan permissions to the operator account.
- If state is backed up or moved to a remote backend, encrypt it and tightly limit access.
- Use unique high-entropy passwords even though normal operations use SSH keys. Hetzner does not allow password authentication to be disabled on a Storage Box.

### SSH-key bootstrap and rotation

`hcloud_storage_box.ssh_keys` is creation-only. The provider warns that changing it forces Storage Box replacement and could lose data, so Terraform ignores later changes and `prevent_destroy` supplies a second guard. Rotate the main account's keys through its `.ssh/authorized_keys` instead.

The subaccount resource does not inject an SSH key. After apply, use the main writer credential from a Hetzner host to create `catalog/.ssh/authorized_keys` containing the QNAP public key. Port 23 expects normal one-line OpenSSH format. If port 22 is also used, Hetzner requires the key in RFC4716 format as well. Each subaccount has its own `authorized_keys` file.

Before saving a host key, compare the presented fingerprint with Hetzner's published Storage Box fingerprints. Use the emitted hostname rather than pinning the box's changeable IPv4 or IPv6 address.

For rclone, use SFTP on port 23 so its checksum detection can call the Storage Box's restricted `md5sum`, `sha1sum`, or `sha256sum` commands. Begin conservatively with `--transfers 2 --checkers 4`; Hetzner documents a maximum of ten simultaneous connections and recommends keeping SFTP checkers below eight. Confirm the hashes rclone detects during acceptance testing.
