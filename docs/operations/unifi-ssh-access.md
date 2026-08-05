# UniFi Device SSH Access

Use this runbook to configure or troubleshoot SSH access to UniFi devices managed by the **Cloud Key Gen2 Plus** console.

## Current Configuration

- UniFi console/site: **Cloud Key Gen2 Plus**
- Device SSH authentication: enabled
- SSH username: `ubnt`
- Registered key label: **Ryan Timmons - 1Password id_rsa**
- Private-key provider: 1Password SSH agent

The registered key applies to UniFi devices managed by this Network site. This is separate from exposing SSH through the WAN and may also be separate from console-level SSH access to the Cloud Key operating system.

## Local SSH Agent

The workstation SSH configuration uses the 1Password agent socket:

```sshconfig
Host *
    IdentityAgent ~/Library/Group\ Containers/2BUA8C4S2C.com.1password/t/agent.sock
```

Confirm that the expected identity is available without copying or exporting private-key material:

```bash
ssh-add -l
ssh-add -L
```

The public key currently registered in UniFi is the agent identity named `id_rsa`. Do not commit the full public-key blob; read the active value from the agent when it needs to be compared or replaced.

## UniFi Configuration Path

In [UniFi Site Manager](https://unifi.ui.com/):

1. Open **Cloud Key Gen2 Plus**, not the 2117 Lehigh console.
2. Open the **Network** application.
3. Go to **Settings** and search for `SSH`.
4. Open **Device SSH Authentication**.
5. Expand **Device SSH Settings**.
6. Confirm **Device SSH Authentication** is enabled and the username is `ubnt`.
7. Under **SSH Keys**, confirm **Ryan Timmons - 1Password id_rsa** is listed.

To replace the key, paste only the public key returned by `ssh-add -L`, add it with a descriptive label, and apply the changes. Never paste or upload a private key.

## Connecting

Find the current device IP in **Network > UniFi Devices**, then connect with:

```bash
ssh ubnt@<device-ip>
```

For a non-interactive authentication check:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 ubnt@<device-ip> exit
```

The client must already have network reachability to the device, such as local LAN access or an approved VPN/site-to-site route. Adding the key does not create a WAN firewall rule, port forward, or public SSH endpoint.

## Troubleshooting

### The agent has no identities

1. Open and unlock 1Password.
2. Confirm the SSH key is enabled for the 1Password SSH agent.
3. Run `ssh-add -l` again.

### Permission is denied

1. Confirm the target belongs to the **Cloud Key Gen2 Plus** site.
2. Confirm the key label is still listed under **Device SSH Settings**.
3. Compare the public key in UniFi with `ssh-add -L`.
4. Confirm the SSH username is `ubnt`.
5. Use `ssh -v ubnt@<device-ip>` to inspect which identity the client offers.

### The connection times out

A timeout is a reachability or firewall problem, not normally a key problem. Confirm the current device IP, LAN/VPN routing, and any policy between the client and the management network. Do not expose port 22 directly to the internet; prefer VPN access.
