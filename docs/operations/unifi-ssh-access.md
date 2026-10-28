# UniFi SSH access

The **Cloud Gateway Max** at `192.168.1.1` is the active console and router.
The USG 3P and Cloud Key Gen2 Plus at the former `192.168.1.180` are retired
from active service. Do not reconnect them to obtain diagnostic data.
Use [Network setup](unifi-network-setup.md) for topology and the
[post-migration checklist](unifi-post-migration.md) for deployment status.

## Verified access — October 22, 2026

| Device | SSH target | Pinned host key |
| --- | --- | --- |
| Cloud Gateway Max | `root@192.168.1.1` | Ed25519 `SHA256:rNZqH5s5CZMTKtkJbO1EpcjlVQwtLt/tf86+3J9+75E` |
| AP Bedroom | `ubnt@192.168.1.128` | Ed25519 `SHA256:4sWtMzPX9eYtIvE2a9C+9vI3w1KV231tm489M30TqEc` |
| U7 Pro XG | `ubnt@192.168.1.67` | Ed25519 `SHA256:IH4SVyY3sf0fdMFNJ9A6gskXWgihHdAMaQw5Z6tNezQ` |
| Switch Server Closet | `ubnt@192.168.1.158` | RSA `SHA256:qlJ/Lpj7KO+aKXp8LLIwXzX0PoTCK0w+3AP0k18H2RU` |

All four use the existing **Ryan Timmons - 1Password id_rsa** identity,
`SHA256:9JU2+KYI9hjik0LUgE7/B7g7zzE9dXbLDWpDLeEUKik`. The private key stays in
1Password; ignored `.ssh/unifi-owner.pub` selects only that identity and
`.ssh/unifi_known_hosts` pins the host keys. Keep both files mode `600`.
The Mac's global host file, including the old gateway entry, is unchanged.

Max/AP fingerprints were read through trusted native Debug. The switch scan
matched the controller's recorded MD5 fingerprint retrieved over verified Max
SSH; its own host-key output and MAC then matched. The switch negotiated
`rsa-sha2-256`, without a SHA-1 exception. On another workstation, compare the
selected identity and candidate host keys with this record and a trusted console
before installing pins. Stop on a mismatch; a scan alone is not trust.

Prefer supported UI/API and [approval-gated MCP](../../network-infra/unifi-mcp/README.md)
for configuration/client reads; SSH corroborates effective state. MCP remains
subject to the repository approval policy; debug tools remain disabled. Use the approved network
executor when the ordinary sandbox denies TCP; do not bypass it with GUI terminals.

## Verification commands

Run from the repository root with the existing agent available:

```sh
ssh-add -l
ssh-keygen -lf .ssh/unifi-owner.pub
ssh-keygen -lf .ssh/unifi_known_hosts

(
for target in root@192.168.1.1 ubnt@192.168.1.128 ubnt@192.168.1.67 ubnt@192.168.1.158; do
  ssh -i .ssh/unifi-owner.pub -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=yes -o UserKnownHostsFile=.ssh/unifi_known_hosts \
    -o GlobalKnownHostsFile=/dev/null -o ForwardAgent=no \
    -o ConnectTimeout=5 -o ConnectionAttempts=1 "$target" 'id; uptime' || exit 1
done
)
```

These administrative accounts report UID 0. Keep routine diagnostics read-only.
Private acceptance logs remain under `build/unifi-ssh-20261022/`.

## Network-boundary acceptance

Fresh key logins and device identities passed on all four devices. From an
associated printer-network Mac, SSH to all four (including both Max gateway
addresses) was blocked while HA TCP/8099 health and fresh mDNS worked. Trusted
Wi-Fi and temporary preferences were restored. An external cloud-host probe
had a working HTTPS control and could not open Max IPv4 WAN TCP/22. This is
current key/path acceptance, not owner-password, reboot/update or replacement
recovery testing.

## Console setup, persistence and rollback

Max console SSH is enabled at **Settings > Management > General > SSH**
(Network `10.6.106`), separately from adopted **Device SSH Authentication**.
The owner completed password/key installation. The Max has one approved key,
root-owned directory/file modes `700`/`600`, and options
`from="192.168.1.0/24",no-agent-forwarding,no-X11-forwarding`.
This key cannot authorize root from printer, Lehigh or cloud VPN sources.
No AP/switch credential or firewall rule changed.

Preserve the owner recovery credential and authentication policy. Recheck after
OS updates/restores; System Config exports must not be assumed to restore
console authorized keys. A fresh full post-SSH Max export was encrypted and
authenticated-decryption verified; retain all earlier copies.

For rollback, retain authenticated UI access, remove only the approved key entry,
then uncheck console SSH and apply. Confirm trusted-LAN TCP/22 refuses while
HTTPS, DNS and application paths still work. Leave adopted-device SSH settings
and unrelated keys intact. Do not reconnect retired hardware for diagnostics.

## Troubleshooting

- **Operation not permitted before connection:** executor restrictions; do not
  diagnose credentials or change live SSH settings from this result.
- **Connection refused:** inspect the relevant console/device SSH setting.
- **Timeout:** check the selected LAN address, route and intended firewall path.
- **Permission denied:** check the correct console/device user and intended
  authorized key. Do not cycle through unrelated identities.
- **Changed host key:** verify appliance identity and fingerprint, then update
  only that stale host entry.

Home Assistant uses its separate repository-local SSH identity and hostname
procedure in [AGENTS.md](../../AGENTS.md). The UniFi agent settings above do not
apply to Home Assistant.

[Ubiquiti SSH documentation](https://help.ui.com/hc/en-us/articles/204909374-Connecting-to-UniFi-with-Debug-Tools-SSH).
