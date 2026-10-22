# UniFi SSH access

The **Cloud Gateway Max** at `192.168.1.1` is the active console and router.
The USG 3P and Cloud Key Gen2 Plus at the former `192.168.1.180` are retired
from active service. Do not reconnect them to obtain diagnostic data.
Use [Network setup](unifi-network-setup.md) for topology and the
[post-migration checklist](unifi-post-migration.md) for deployment status.

## Access matrix — verified October 22, 2026

| Target | Address | User | Accepted SSH access |
| --- | --- | --- | --- |
| Cloud Gateway Max console | `192.168.1.1` | `root` | Owner enabled console SSH and installed the approved key; fresh key login and permissions verified |
| AP Bedroom, U6+ | `192.168.1.128` | `ubnt` | Existing owner-key login and device MAC verified |
| U7 Pro XG | `192.168.1.67` | `ubnt` | Existing owner-key login and device MAC verified |
| Switch Server Closet | `192.168.1.158` | `ubnt` | Existing owner-key login, device MAC and host fingerprint verified |

All four connections use the existing **Ryan Timmons - 1Password id_rsa**
identity, fingerprint `SHA256:9JU2+KYI9hjik0LUgE7/B7g7zzE9dXbLDWpDLeEUKik`.
No private key was exported, new identity created or AP/switch credential changed.
The Max has exactly one authorized key, restricted with
`from="192.168.1.0/24",no-agent-forwarding,no-X11-forwarding`.
This key does not authorize root login from Lehigh, the cloud VPN or the printer
network. A broader source range requires its own reviewed change.

The ordinary command sandbox still denies network access. Use the approved
network-capable executor for these checks; do not interpret sandbox failures as
credential failures or use a GUI terminal to bypass the restriction.

## Prefer the supported control plane

Use the Max's Network UI and version-specific **Integrations** API for saved
configuration, client records, events and audit activity. The existing
[read-only MCP launcher](../../network-infra/unifi-mcp/README.md) provides
verified native reads against Max/site `default`. SSH corroborates effective
state and provides a recovery path independent of the Network application.
MCP remains viewer/read-only/dry-run, with mutations and debug tools disabled.

Console SSH and **Device SSH Authentication** are separate configurations.
Restoring a Network backup does not establish that console SSH host keys or
authorized keys moved to a replacement. Do not transplant the Cloud Key's
filesystem or database-port assumptions onto the Max.

## Workstation identity and host trust

The Mac uses its existing 1Password SSH agent. The ignored repository-local
`.ssh/unifi-owner.pub` selects only the approved public key; the private key
stays in 1Password. `.ssh/unifi_known_hosts` pins the verified host public keys
and leaves the Mac's general `known_hosts` unchanged, including the former
appliance's entry at `192.168.1.1`.

| Address | Pinned host-key type | SHA-256 fingerprint |
| --- | --- | --- |
| `192.168.1.1` | Ed25519 | `SHA256:rNZqH5s5CZMTKtkJbO1EpcjlVQwtLt/tf86+3J9+75E` |
| `192.168.1.128` | Ed25519 | `SHA256:4sWtMzPX9eYtIvE2a9C+9vI3w1KV231tm489M30TqEc` |
| `192.168.1.67` | Ed25519 | `SHA256:IH4SVyY3sf0fdMFNJ9A6gskXWgihHdAMaQw5Z6tNezQ` |
| `192.168.1.158` | RSA | `SHA256:qlJ/Lpj7KO+aKXp8LLIwXzX0PoTCK0w+3AP0k18H2RU` |

The Max and AP fingerprints were read through the authenticated native UniFi
Debug consoles before accepting the network scans. The switch's native Debug
session remained at Connecting. Its candidate RSA key instead matched the
controller's recorded `x_ssh_hostkey_fingerprint`, fetched from the loopback
API over the already verified Max SSH channel. The controller's recorded MD5
fingerprint was compared with the candidate key, then its SHA-256 fingerprint
was pinned. After login, the switch's own host-key output and MAC matched.
The switch negotiated `rsa-sha2-256`; no SHA-1 authentication exception or
host-check bypass was required.

On another workstation, obtain only the intended public identity from the agent
and compare its fingerprint above. Scan each host's public key into a temporary
file, compare the fingerprint with this reviewed record and the current trusted
console, then install only the matching entry into the dedicated host file.
A scan alone does not establish trust. Stop on a mismatch and investigate
replacement hardware or key rotation before changing a pin. Keep both local
files ignored and mode `600`; never commit a public-key blob or private key.

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

Use `root` only for the Max; adopted APs and the switch use `ubnt`. Their
administrative users report UID 0, so limit diagnostic commands to reads.
Acceptance used fresh SSH processes, public-key authentication and matching
device identities. Verbose connection evidence stays private under ignored
`build/unifi-ssh-20261022/`; do not publish raw configuration or session logs.

## Network-boundary acceptance

After enablement, this Mac actually joined `sintheta-printer` and obtained a
new `192.168.6.0/24` lease. TCP/22 was blocked to the Max at both gateway
addresses, both APs and the switch. The allowed HA TCP/8099 health request
returned HTTP 200 and fresh HA mDNS resolved. Unrelated LAN, gateway, Internet
and cloud-private controls stayed blocked. The Mac returned to trusted Wi-Fi,
its temporary printer preference was removed and the independent restoration
watchdog exited cleanly. No label was printed.

A separate read-only probe from the existing cloud host could reach a public
HTTPS control but could not open the Max's public WAN TCP/22. This verifies the
tested IPv4 WAN path from that external source, not an IPv6 or every-source
exposure audit. No firewall policy or port forward was added for SSH.

## Console setup, persistence and rollback

The observed Network `10.6.106` path is **Settings > Management > General >
SSH**. Ryan accepted the enablement notice and completed password setup
privately, then installed the single approved key through the native Max Debug
console. The directory and authorized-key file are root-owned, modes `700` and
`600`. Owner password entry is not an agent-run password-login test.

Preserve the configured owner recovery credential and existing authentication
policy. Do not disable password or keyboard-interactive access merely because
a key login passed. Recheck key access after a UniFi OS update, restoration or
replacement; this acceptance does not claim reboot, firmware-update or
replacement-hardware persistence. Keep an authenticated UI session available
while changing access. The local public key is the installation source;
System Config exports must not be assumed to restore console authorized keys.
A fresh full post-SSH Max export (167,888 bytes) was encrypted off-device and
authenticated-decryption verified; all earlier recovery copies remain intact.

To roll back the Max addition, first retain working native UI access. Remove
only the approved public-key entry, preserving all other entries, then uncheck
**Management > General > SSH** and apply. Confirm TCP/22 refuses a trusted-LAN
connection while HTTPS, DNS and application paths still work. Do not change
Device SSH Authentication or the AP/switch keys as part of this rollback.
The dedicated local host file avoids any need to remove the old gateway's
unrelated global host entry.

For transient discovery failures, preserve the failure before reprovisioning;
continue with [Bonjour/Apple TV troubleshooting](unifi-apple-tv-remote.md).

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
