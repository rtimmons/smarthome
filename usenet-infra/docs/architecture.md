# Architecture

Current workflow: native Radarr/Sonarr imports, QNAP Plex NAS/remote libraries,
native selective NAS copies, the NZBGeek Cart feed, and scheduled encrypted
configuration backups are deployed. Read the
[current handoff](../../plan.md) and [native media](native-media.md) for live
acceptance evidence and remaining client checks.

This system intentionally separates a replaceable acquisition host, a canonical
remote catalog, and a disposable local cache:

```text
operator workstation
  | UniFi private LAN route (SSH tunnels remain available)
  v
Hetzner Cloud VM (trusted writer)
  |-- TLS --> Usenet provider and indexers
  |-- synchronous SSHFS native library --> Storage Box writer account
  v
Hetzner Storage Box (canonical catalog)
  BX11 now -> BX21 -> BX31 -> BX41 target
  ^
  | direct SFTP/rclone, read-only subaccount
  |
QNAP (Plex + OliveTin selective copies + read-only remote playback)
```

The Storage Box is the canonical copy. It starts at 1 TB on BX11 and is upgraded
in place as measured use grows; BX41 remains the eventual 20 TB target. The VM
scratch space and QNAP cache may be rebuilt without changing the catalog. The
QNAP is not in the acquisition path, so acquisition and native imports can continue
while it is offline.

## Trust boundaries

| Boundary | Trust and credential rule | Permitted traffic |
| --- | --- | --- |
| Public Internet -> cloud VM | Untrusted. The firewall admits TCP 22 from `admin_ssh_cidrs`, ICMP/ICMPv6, and UDP 500/4500 only from the configured `vpn_peer_ipv4` when present. | Administrative SSH and the selected home gateway’s IPsec tunnel; no public application UI ports. |
| Operator -> cloud applications | Authenticated access over the UniFi private LAN route; SSH tunnels remain available. | Private listener `10.77.0.1:19696` for Prowlarr/Radarr/Sonarr and `10.77.0.1:18080` for SAB. |
| Cloud VM -> providers/indexers | The VM holds the service credentials. | NNTP over TLS and HTTPS only. |
| Cloud VM -> Storage Box | Trusted write path. Only this path receives the main Storage Box credential. | Synchronous SSHFS native imports; legacy objects retained. |
| QNAP -> Storage Box | Untrusted for canonical mutation. The QNAP receives only a subaccount rooted at `catalog` with server-enforced `readonly = true`. | Direct read-only SFTP/rclone pulls. |
| Operator -> QNAP dashboard | An authenticated private interface, reached over the selected LAN/private access path. | Predefined browse, refresh, download, retry, and local-eviction actions only. |
| Git -> runtime | Git is the source of truth for non-secret configuration. | Secrets, private keys, Terraform state, plans, and live app config remain outside Git. |

The QNAP catalog alias does not enforce permissions. The Hetzner subaccount
restriction is the remote security boundary; the playback mount is also read-only. Hetzner documents subaccount home-directory and read-only controls in
[Storage Box overview](https://docs.hetzner.com/storage/storage-box/general/),
and the provider exposes those controls on
[`hcloud_storage_box_subaccount`](https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/storage_box_subaccount).

## Deliberate data flow

1. A person selects movies or monitored TV through Radarr/Sonarr. Existing
   interactive/automatic searches and 15-minute RSS checks remain enabled. The
   separate [NZBGeek Cart feed](nzbgeek-cart.md) sends new cart entries directly
   to SAB every 15 minutes; these Default-category jobs are not Arr-owned and
   need an explicit library-import route. Preserve its held/processed-entry state.
2. SAB downloads, verifies, repairs and unpacks on cloud scratch. Both Arr apps
   see that same completed scratch at `/data/complete`.
3. For Arr-owned jobs, Completed Download Handling imports to the real Storage Box library,
   separately mapped to `catalog/library/Movies` or `catalog/library/TV`.
   Systemd requires the synchronous SSHFS mount before starting these apps;
   the unmounted directory remains mode 0000. Successful imports allow native
   client cleanup. Failed jobs remain; automatic redownload is disabled.
4. The retired publisher timer stays disabled. The five legacy objects/manifests
   and their hard-linked native adoptions remain intact. New native imports do
   not produce legacy manifests, and no second mover touches Arr scratch.
5. Plex on the NAS reads canonical media through a read-only rclone mount with
   a bounded streaming cache. Native watch/partial scans and hourly scanning
   discover media; the copy interface does not own scanning.
6. OliveTin offers deployed native and legacy selective NAS copies. Both preserve
   staging, verification, capacity reserves and atomic publication. Native movie
   copy/repeat/Plex indexing and its live status graph are accepted; a real TV
   transfer remains untested. See [native media](native-media.md) and the
   [live receipt](../recovery/drills/native-copy-live-20260913.json). No whole-library sync runs.
7. Local removal acts only on a managed NAS copy. Neither backend receives
   remote writer credentials or invokes remote deletion.

## Dashboard boundary

The dashboard is declarative OliveTin configuration, not an alternative transfer
engine. Catalog metadata supplies item cards and action arguments; backend
validation remains mandatory even after UI validation. There is no free-form
shell, general rclone command field, Docker socket, or remote writer credential.
The runtime receives only the numeric QNAP UID/GID, required cache/state paths,
read-only source/configuration mounts, and the read-only Storage Box identity.
Capabilities are dropped and the container root filesystem is read-only.

The dedicated NAS SSH deployment account may require QNAP administrator-group
membership. That host authority is separate from what the dashboard container
receives: it gets no NAS supplementary groups or host-control socket. Closing
the browser must not cancel a running pull; runtime acceptance verifies that
behavior and persistence of execution history. See [QNAP bootstrap](qnap-bootstrap.md)
for the private access and authentication setup.

HybridMount remains an optional experiment. Its caching model must not replace
manifest validation, deliberate selection, or verified local publication. A
failed read-only WebDAV mount is not grounds to grant write access.

The legacy catalog manifest schema records a stable ID, category, canonical remote
path, provenance, authorization basis, acquisition time, byte count, and a
SHA-256 hash for every file. See the
[schema](../config/catalog.schema.json) and
[catalog tool](../scripts/catalogctl.py). Native titles are discovered from the
canonical library instead; `state/native-items` holds local ownership and integrity
receipts. Those receipts are not disposable or regenerated by listing a directory.

## Infrastructure ownership and protection

Terraform is split into independent roots and states:

- [`terraform/cloud`](../terraform/cloud) owns the replaceable VM, explicit
  Primary IPv4 and IPv6, SSH key, and firewall.
- [`terraform/storage`](../terraform/storage) owns the canonical Storage Box,
  its current capacity tier, and the QNAP read-only subaccount.

The roots must not share a state file or backend key. The storage root uses
both Hetzner delete protection and Terraform `prevent_destroy`; its subaccount
also uses `prevent_destroy`. Saved plans and state contain Storage Box
passwords even though Terraform marks them sensitive, so storage state must be
encrypted, access-controlled, and backed up separately. A VM rebuild must
never include a storage-root apply.

Changing initial Storage Box SSH keys is also deliberately excluded from
Terraform reconciliation: the provider documents that the API cannot update
them and a change would force replacement. Key rotation is performed through
`authorized_keys`, with the server fingerprint checked against
[Hetzner's published host keys](https://docs.hetzner.com/storage/storage-box/general/).
See the [Terraform runbook](../terraform/README.md) for the break-glass rules.

## Capacity growth

The approved capacity ladder is BX11 (1 TB), BX21 (5 TB), BX31 (10 TB), then
BX41 (20 TB). BX11 is the initial tier; BX41 is the target when the catalog
actually needs it. Hetzner lists those capacities on the official
[BX11](https://www.hetzner.com/storage/storage-box/bx11/),
[BX21](https://www.hetzner.com/storage/storage-box/bx21/),
[BX31](https://www.hetzner.com/storage/storage-box/bx31/), and
[BX41](https://www.hetzner.com/storage/storage-box/bx41/) pages.

Health checks warn at 80% used capacity. The operator investigates growth and
applies a reviewed upgrade to the next tier before usage reaches 90%; there is
no unattended scaling or purchase. Hetzner supports scaling Storage Boxes and
permits a downgrade only when total use is below the smaller tier's capacity.
Snapshots consume Storage Box capacity, so they count toward that decision.
See Hetzner's [storage scaling comparison](https://docs.hetzner.com/storage/general/which-storage-is-right-for-me/)
and [snapshot documentation](https://docs.hetzner.com/storage/storage-box/snapshots/).

With hcloud provider 1.68.0, changing only `storage_box_type` is an in-place API
`ChangeType` action: it does not require Terraform replacement. Location and
initial SSH-key changes do require replacement, so a capacity plan must be
isolated and reviewed for any action other than the type update. The official
[provider 1.68.0 implementation](https://github.com/hetznercloud/terraform-provider-hcloud/blob/v1.68.0/internal/storagebox/resource.go#L432-L447)
shows this behavior. Although Hetzner describes type changes as supported, its
current tier-scaling documentation does not give an explicit zero-downtime or
zero-risk guarantee; retain independent backups and verify the catalog after
each upgrade.

## Exposure and failure containment

- Backend application ports bind to loopback. An authenticated reverse proxy
  serves the existing private LAN/VPN listeners; public application UIs remain
  closed. The firewall rules above match [current cloud IaC](../terraform/cloud/main.tf).
- A lost VM loses scratch and possibly jobs in flight, not the canonical
  catalog.
- A lost QNAP disk loses cached copies, not the canonical catalog.
- QNAP compromise exposes catalog reads but its credential cannot modify or
  delete remote content. The main writer credential must never be copied to the
  QNAP.
- Storage Box RAID and optional snapshots improve local resilience but are not
  an independent backup. Hetzner explicitly describes Storage Boxes as RAID
  storage and snapshots as copies on the same Storage Box; irreplaceable
  material still needs a separate backup domain. See the
  [Storage Box overview](https://docs.hetzner.com/storage/storage-box/general/)
  and [snapshot documentation](https://docs.hetzner.com/storage/storage-box/snapshots/).

Operational details live in the
[cloud Compose notes](../compose/cloud/README.md) and
[QNAP Compose notes](../compose/qnap/README.md). Recovery procedures are in
[recovery.md](recovery.md).
