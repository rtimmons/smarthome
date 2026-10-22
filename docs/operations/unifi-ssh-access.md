# UniFi SSH access

The **Cloud Gateway Max** at `192.168.1.1` is the active console and router.
The USG 3P and Cloud Key Gen2 Plus at the former `192.168.1.180` are retired
from active service. Do not reconnect them to obtain diagnostic data.
Use [Network setup](unifi-network-setup.md) for topology and the
[post-migration checklist](unifi-post-migration.md) for deployment status.

## Access matrix

| Target | Address | User | Verification |
| --- | --- | --- | --- |
| Cloud Gateway Max console | `192.168.1.1` | `root` | Native Management SSH off; resumed TCP/22 check refused; no new access enabled |
| AP Bedroom, U6+ | `192.168.1.128` | `ubnt` | Agent-key login passed August 31, 2026; recheck after migration |
| U7 Pro XG | `192.168.1.67` | `ubnt` | Agent-key login passed August 31, 2026; recheck after migration |
| Switch Server Closet | `192.168.1.158` | `ubnt` | Agent-key login passed August 31, 2026; recheck after migration |

The first Max SSH probe was blocked by the command sandbox. The resumed
approved network-capable probe reached the Max and received connection refused
on TCP/22, matching the native Management page's SSH-off state. Native MCP/API
reads now work. Enabling console SSH remains a separate reviewed access change;
no alternate credentials or retired hardware are needed for supported reads.

## Prefer the supported control plane

Use the Max's Network UI and version-specific **Integrations** API for saved
configuration, client records, events and audit activity. The existing
[read-only MCP launcher](../../network-infra/unifi-mcp/README.md) now provides
verified native reads against Max/site `default`. Use SSH to corroborate effective device state.

Console SSH and **Device SSH Authentication** are separate configurations.
Restoring a Network backup does not establish that a console's host SSH keys or
authorized keys moved to the Max. Do not transplant the Cloud Key's database
port or filesystem assumptions onto the new console.

## Max console SSH

In UniFi Site Manager, select **300 Newark Cloud Gateway Max**, then inspect
**Network > Settings > Management > General > SSH** (observed Network 10.6.106).
The checkbox was off on October 22. Record its actual current state before
changing it. Use the existing console credential if configured; a new password
must be entered by the owner directly and kept in the password manager.

The console uses `root`, independently of the adopted AP/switch username.
Confirm the single intended agent public key before installing it in
`/root/.ssh/authorized_keys`; do not blindly append every key in an agent.
Verify directory/file permissions `700`/`600`. Host key installation and
successful key authentication remain acceptance work, not completed setup.

After host trust and authorization are established:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 root@192.168.1.1 exit
```

The Max replaces a different appliance at the same address. Compare its
fingerprint through a trusted console path before replacing an exact stale
`known_hosts` entry. Never disable host-key checking globally. Console SSH
should remain reachable only over the intended LAN/VPN path.

## Adopted AP and switch access

The Network configuration historically used username `ubnt` and the public
key labelled **Ryan Timmons - 1Password id_rsa**. Inspect the Max's current
**Device SSH Authentication** settings and verify each device separately before
changing password access. No full public-key blob belongs in this runbook.

The workstation historically selected the 1Password agent:

```sshconfig
Host *
    IdentityAgent ~/Library/Group\ Containers/2BUA8C4S2C.com.1password/t/agent.sock
```

Use `ssh-add -l` to confirm the intended identity is available. Find the actual
device address in **UniFi Devices**, then verify the specific target:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 ubnt@192.168.1.128 exit
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 ubnt@192.168.1.67 exit
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 ubnt@192.168.1.158 exit
```

For transient discovery failures, preserve the failure before reprovisioning;
continue with [Bonjour/Apple TV troubleshooting](unifi-apple-tv-remote.md).

The October 22 follow-up found no verified entries for the three adopted-device
addresses in this Mac's `known_hosts`. A U7 connection stopped at host-key
verification before authentication. This is a host-trust prerequisite, not a
failed agent credential. Verify each fingerprint over an independently trusted
administrative path before adding an exact entry; never blindly accept a scan
or disable checking. Native Max packet capture remains available without
enabling console SSH.

Ryan approved the existing native **UniFi Devices > Max > Settings > Debug**
console for read-only firewall inspection and its displayed terms notice.
That session read effective rule counters without enabling SSH, installing a
key or changing credentials. After the zone upgrade, the native policy table
also exposes hit counts. This approval did not enable MCP debug/mutation tools.

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
