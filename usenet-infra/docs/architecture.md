# Architecture

```text
Seerr (Plex sign-in) -> Radarr / Sonarr -> SAB -> Storage Box native library
                           ^                      |
                        Prowlarr                  | read-only SFTP
                                                  v
                                  QNAP: Plex + selective verified NAS copies
```

The CX43 cloud VM acquires and processes explicitly requested media. Its 300 GB
repair volume holds incomplete downloads; completed staging and canonical Movies/TV
share a synchronous SSHFS filesystem on the BX21 Storage Box. Arr owns imports
and completed-source cleanup. RSS, direct carts and the former custom workers
are disabled. See [native workflow](native-media.md) for limits and path mappings.

Plex runs on QNAP with separate remote and NAS libraries. A read-only rclone mount
provides remote playback. OliveTin invokes the native/catalog backends for
explicit, verified local copies and owned-copy eviction. It has no Docker socket,
free-form shell, canonical writer credential or whole-library sync. Existing
catalog manifests remain readable because their media and copies still exist.

## Trust boundaries

| Boundary | Control |
| --- | --- |
| Internet to cloud | SSH only from configured administrator CIDRs; IPsec only from the configured home gateway; no public app ports |
| Operator to cloud UI | Private UniFi route or pinned SSH tunnel, application/proxy authentication |
| Cloud to canonical storage | Dedicated writer key, verified host pin, synchronous SSHFS |
| NAS to canonical storage | Server-enforced read-only subaccount, read-only playback mount |
| NAS settings backups | Separate writer subaccount confined to `catalog/.backups/nas-settings` |
| NAS copy dashboard | Authenticated private access; predefined actions, dropped capabilities, read-only container root |
| Filex | Operator login, dedicated staging, read-only canonical roots, verified transfers and recoverable quarantine |
| Git | Nonsecret source; private inputs, keys, state, plans and live app databases remain ignored/encrypted |

Systemd binds SAB/Arr to required mounts. Underlying mountpoints are mode 0000.
Plex's general profile has IDs 2/3/4/5 only; private ID 1 and staging are excluded.
See [NAS layout](nas-plex-layout.md), [LAN access](lan-ui.md) and [Filex](filex.md).

## Infrastructure and recovery

Independent Terraform roots own cloud compute, canonical storage, the confined
NAS backup account, and disposable recovery-drill resources. Keep their states
separate. Canonical storage and the repair volume use deletion protection;
review any capacity change rather than enabling unattended scaling. Never apply
an old saved plan or let a VM rebuild replace storage.

Cloud and NAS schedules encrypt configuration, independently read back off-host
ciphertext, and retain receipts. Media and unfinished downloads are outside the
settings backup scope. Original SOPS-bound recovery snapshots stay immutable.
See [scheduled backups](scheduled-backups.md), [recovery](recovery.md) and
[Terraform](../terraform/README.md). The static private wiki is an end-user guide;
it contains no live data or control API.
