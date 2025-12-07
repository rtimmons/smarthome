# Brother QL-810W Troubleshooting Guide

## Agent Notes
- Follow the repo-wide expectations in `../../AGENTS.md#ground-rules` (sandbox/git-lock permission, use `just`/env wrappers, “prepare to commit” steps).

This guide addresses common connectivity issues with the Brother QL-810W, particularly on Ubiquiti UniFi networks.

## Quick Diagnostics

When the printer becomes unreachable, run these commands to identify the issue:

```bash
# Test basic network connectivity
ping -c 3 192.168.1.192

# Test the raw print service port
nc -z -v 192.168.1.192 9100

# Check if printer is in ARP cache
arp -a | grep -i brother
```

This will tell you:
- **No ping, no ARP**: Printer is offline or IP changed
- **Ping works, port 9100 fails**: WiFi connected but print service disabled/crashed
- **No response at expected IP**: IP address changed (check router/UniFi controller)

## Physical Wake-Up

The QL-810W has aggressive power saving that can make it appear offline:

1. **Open and close the top cover** - most reliable wake method
2. **Press the Feed button** - prints a blank label and wakes WiFi
3. **Print from Brother iPhone app** - sometimes wakes the printer when other methods fail

After waking, wait 10-15 seconds for WiFi to reconnect before testing again.

## Common Ubiquiti UniFi Issues

The QL-810W is notoriously problematic on UniFi networks. These settings frequently cause disconnections:

### 1. Client Device Isolation

**Problem**: Prevents devices from communicating even when on the same network.

**Solution**:
- UniFi Controller → Settings → WiFi → [Your Network]
- Disable "Client Device Isolation" (sometimes called "AP Isolation")
- Disable "Multicast and Broadcast Control"
- Apply changes and wait for printer to reconnect

### 2. Band Steering

**Problem**: The QL-810W handles 2.4GHz/5GHz switching poorly and often drops connection.

**Solution** (choose one):

- **Option A**: Create a dedicated 2.4GHz-only network for IoT devices
  - Settings → WiFi → Create New Network
  - Name: "IoT" or similar
  - Band: 2.4GHz only
  - Reconnect printer to this network

- **Option B**: Disable band steering on existing network
  - Settings → WiFi → [Your Network] → Advanced
  - Disable "Band Steering"

### 3. WiFi Optimization Settings

**Problem**: UniFi's aggressive optimization drops IoT devices with weaker signals.

**Solution**:
- Settings → WiFi → [Your Network] → Advanced
- Disable "High Performance Devices"
- Set "Minimum RSSI" to -80 or disable it entirely
- Disable "Auto-Optimize Network"
- Disable "Connectivity Monitor" (can cause false disconnects)

### 4. DHCP Lease Expiration

**Problem**: Printer loses connection when DHCP lease expires and fails to renew.

**Solution** (choose one):
- **Option A - Fixed IP Reservation** (recommended):
  - UniFi Controller → Settings → Networks → [Your Network] → DHCP
  - Find printer in client list, click, select "Use Fixed IP Address"
  - Assign 192.168.1.192 to the printer's MAC address

- **Option B - Static IP on Printer**:
  - Use Brother Printer Setting Tool
  - Network Settings → WLAN → TCP/IP
  - Set: IP: 192.168.1.192, Subnet: 255.255.255.0, Gateway: 192.168.1.1, DNS: 192.168.1.1

### 5. Multicast DNS (mDNS) Filtering

**Problem**: Prevents discovery protocols from working, especially across VLANs.

**Solution**:
- Settings → Networks → Advanced
- Enable "Enable multicast DNS"
- Enable "IGMP Snooping" (for multicast traffic)

### 6. Firewall Rules / Traffic Rules

**Problem**: Unintended firewall rules blocking printer traffic.

**Solution**:
- Settings → Firewall & Security → Traffic Rules
- Ensure no rules are blocking local LAN traffic on port 9100
- Check "Internet Threat Management" isn't flagging the printer

## Finding a Lost Printer

If the printer isn't responding at its expected IP address:

### Check UniFi Controller
1. UniFi Network Controller → Clients → All Clients
2. Search for "Brother" or "QL-810W"
3. Note current IP address and connection status
4. Check if it's connected to expected WiFi network

### Use Brother Discovery Tools
These use mDNS/Bonjour which may work when direct IP fails:
- **iPhone/iPad**: Brother iPrint&Label app
- **macOS/Windows**: Brother Printer Setting Tool
- Tools will show current IP even if printer isn't responding to ping

### Network Scan
If you have `nmap` installed:
```bash
# Scan entire subnet for port 9100
nmap -p 9100 192.168.1.0/24

# Or scan with service detection
nmap -sV -p 9100 192.168.1.0/24
```

### ARP Table Scan
```bash
# View all ARP entries
arp -a

# Brother MAC addresses typically start with 00:80:77, 00:1B:A9, or 30:05:5C
arp -a | grep -iE '00:80:77|00:1b:a9|30:05:5c'
```

## Printer-Side Configuration

Access the printer's web interface at `http://192.168.1.192/` (when reachable):

### Verify Raw Port 9100 is Enabled
1. Network → Network → Protocol
2. Ensure "Raw Port (9100)" is checked/enabled
3. LPR and AirPrint are optional but can be disabled if causing issues

### WiFi Connection Settings
1. Network → Network → Wireless
2. Verify correct SSID
3. Use WPA2-PSK (not WPA3 - compatibility issues exist)
4. Ensure WiFi signal strength is reasonable (not below -70 dBm)

### Firmware Updates
1. Network → Administrator → Firmware Update
2. Check for updates - Brother has released fixes for connectivity issues
3. Current stable version should be 1.43 or higher

### Power Save Settings
1. General → General Settings → Ecology
2. Consider disabling "Sleep Mode" or increasing timeout
3. Trade-off: slightly higher power usage but better availability

## Recommended Long-Term Configuration

For maximum stability on UniFi networks:

### Create Dedicated IoT Network
```
Network Name: IoT
WiFi Band: 2.4GHz only
Security: WPA2-PSK
Client Isolation: Disabled
Band Steering: Disabled
Minimum RSSI: Disabled or -80
DHCP Range: 192.168.2.100-254
```

### Printer Network Settings
```
IP Address: 192.168.2.192 (static or fixed DHCP)
Subnet Mask: 255.255.255.0
Gateway: 192.168.2.1
DNS: 192.168.2.1 or 8.8.8.8
Protocol: WPA2-PSK (not WPA3)
Raw Port 9100: Enabled
```

### Update Environment Variable
```bash
export BROTHER_PRINTER_URI=tcp://192.168.2.192:9100
```

## Alternative Connection Methods

If WiFi remains unstable:

### USB Connection
The `brother_ql` library supports USB:
```bash
export PRINTER_BACKEND=brother-network
export BROTHER_PRINTER_URI=usb://0x04f9:0x209b
```

Find your specific USB identifiers:
```bash
system_profiler SPUSBDataType | grep -A 10 Brother
# or on Linux:
lsusb | grep Brother
```

### Wired Ethernet (with Adapter)
Some users have success with USB-to-Ethernet adapters for the printer, though this is not officially supported by Brother.

## Monitoring Connection Stability

Create a simple monitoring script to track disconnects:

```bash
#!/bin/bash
# Save as monitor-printer.sh
while true; do
  if nc -z -w 2 192.168.1.192 9100 2>/dev/null; then
    echo "$(date): Printer is reachable"
  else
    echo "$(date): PRINTER OFFLINE" >&2
  fi
  sleep 60
done
```

Run in background:
```bash
chmod +x monitor-printer.sh
./monitor-printer.sh >> printer-monitor.log 2>&1 &
```

Review logs to identify disconnect patterns (time of day, duration, etc.).

## Common Error Messages

### `brother_ql` Error: "Could not connect to printer"
- Printer is offline or IP incorrect
- Port 9100 not enabled on printer
- Firewall blocking connection

### `brother_ql` Error: "Timeout waiting for printer response"
- Printer received data but isn't responding
- Often means printer is in error state (out of labels, cover open)
- Try power cycling the printer

### Brother App: "Printer connection lost"
- Normal if printer enters sleep mode
- Check UniFi WiFi optimization settings
- Verify DHCP lease isn't expiring

## When All Else Fails

1. **Factory reset the printer**:
   - Hold Feed button while powering on
   - Keep holding until all lights flash
   - Reconfigure WiFi from scratch

2. **Isolate the issue**:
   - Temporarily connect laptop to same WiFi as printer
   - If it works, issue is network routing/VLAN
   - If it doesn't work, issue is printer WiFi

3. **Contact Brother Support**:
   - They can check printer logs remotely
   - May offer firmware updates not publicly available
   - RMA if hardware WiFi issue

## See Also

- [ql810w-setup.md](./ql810w-setup.md) - Initial printer setup guide
- [Brother QL-810W Support](https://support.brother.com/g/b/spec.aspx?c=us&lang=en&prod=lpql810weus) - Official specifications
- [UniFi Best Practices](https://help.ui.com/hc/en-us/articles/221029967-UniFi-Troubleshooting-Wireless-Connectivity) - UniFi wireless troubleshooting
