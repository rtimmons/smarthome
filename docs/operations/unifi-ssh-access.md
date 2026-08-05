# UniFi SSH Access

Use this runbook to configure or troubleshoot SSH access to the **Cloud Key Gen2 Plus** console and the UniFi devices it manages. These are two independent SSH configurations.

For Bonjour, AirPlay, or Apple TV Remote failures after AP changes, continue with [UniFi and Apple TV Remote Troubleshooting](unifi-apple-tv-remote.md) after verifying access here.

## Current Configuration

### Cloud Key OS

- Console: **Cloud Key Gen2 Plus**
- Current LAN IP: `192.168.1.180`
- SSH: enabled under **Control Plane > Console**
- SSH username: `root`
- Authentication: the 1Password-agent `id_rsa` public key is installed in `/root/.ssh/authorized_keys`
- Verified permissions: `/root/.ssh` is `700`; `authorized_keys` is `600`

Key-only login was verified with:

```bash
ssh -o BatchMode=yes root@192.168.1.180 exit
```

### Adopted Network Devices

- Device SSH authentication: enabled in the Network application
- SSH username: `ubnt`
- Registered key label: **Ryan Timmons - 1Password id_rsa**

The Network application's **Device SSH Authentication** setting applies to adopted APs, switches, and other managed Network devices. It does not enable SSH or install the key on the Cloud Key operating system.

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

The public key registered in UniFi and installed on the Cloud Key is the agent identity named `id_rsa`. Do not commit the full public-key blob; read the active value from the agent when it needs to be compared or replaced.

## Cloud Key Host SSH

Ubiquiti documents console SSH and adopted-device SSH as independent settings. UniFi Console SSH uses `root`; see [Connecting to UniFi with Debug Tools & SSH](https://help.ui.com/hc/en-us/articles/204909374-Connecting-to-UniFi-with-Debug-Tools-SSH).

### Enable the SSH service

In [UniFi Site Manager](https://unifi.ui.com/):

1. Open **Cloud Key Gen2 Plus**, not the 2117 Lehigh console.
2. Go to **Settings > Control Plane > Console**.
3. Enable **SSH**, accept the warning, and set a strong console SSH password.
4. Store the password in the approved password manager; never commit it to this repository.

Enabling this control opens port 22 on the Cloud Key's reachable network interfaces. It does not create a WAN firewall rule or port forward.

### Install the public key

The console UI enables SSH and sets its password but does not expose a host public-key field. From a trusted workstation, use the password once to install the public keys currently exposed by the 1Password agent:

```bash
ssh-add -L | ssh root@192.168.1.180 '
  umask 077
  mkdir -p /root/.ssh
  touch /root/.ssh/authorized_keys
  while IFS= read -r key; do
    grep -qxF "$key" /root/.ssh/authorized_keys ||
      printf "%s\n" "$key" >> /root/.ssh/authorized_keys
  done
  chmod 700 /root/.ssh
  chmod 600 /root/.ssh/authorized_keys
'
```

This command is idempotent for keys already present. It never transmits private-key material.

Because the host key is installed directly in the Cloud Key OS rather than through a UniFi console setting, verify it again after UniFi OS upgrades or recovery operations.

### Connect and verify

```bash
ssh root@192.168.1.180
```

For a non-interactive authentication and permissions check:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 root@192.168.1.180 \
  'id -un; stat -c "%a %U:%G %n" /root/.ssh /root/.ssh/authorized_keys'
```

Expected output begins with `root`, followed by permissions `700` and `600`.

## Adopted-Device SSH

In [UniFi Site Manager](https://unifi.ui.com/):

1. Open **Cloud Key Gen2 Plus** and the **Network** application.
2. Go to **Settings** and search for `SSH`.
3. Open **Device SSH Authentication**, then expand **Device SSH Settings**.
4. Confirm the username is `ubnt` and **Ryan Timmons - 1Password id_rsa** is listed under **SSH Keys**.

Find the current device IP in **Network > UniFi Devices**, then connect with:

```bash
ssh ubnt@<device-ip>
```

## Network Reachability

The client must already have network reachability to the Cloud Key or adopted device through the local LAN or an approved VPN/site-to-site route. Key installation does not expose SSH to the public internet. Do not publish port 22 directly; prefer VPN access.

## Troubleshooting

### The agent has no identities

1. Open and unlock 1Password.
2. Confirm the SSH key is enabled for the 1Password SSH agent.
3. Run `ssh-add -l` again.

### Permission is denied

1. Use `root` for the Cloud Key OS and `ubnt` for adopted Network devices.
2. Use `ssh -v <user>@<device-ip>` to inspect which identity the client offers.
3. For the Cloud Key, verify `/root/.ssh/authorized_keys` and its permissions using the console password or another authorized key.
4. For adopted devices, confirm the key label is still listed under **Device SSH Settings**.
5. Compare the installed public key with `ssh-add -L`.

### The connection times out or is refused

- **Refused**: confirm host SSH is enabled under **Control Plane > Console** for the Cloud Key.
- **Timeout**: confirm the current IP, LAN/VPN routing, and any policy between the client and the management network.
