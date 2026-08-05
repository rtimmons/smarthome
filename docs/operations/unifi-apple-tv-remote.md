# UniFi and Apple TV Remote Troubleshooting

Use this runbook when the Apple TV Remote on an iPhone or iPad discovers an Apple TV inconsistently, remains on **Connecting**, or starts failing after an access-point change. Read [UniFi SSH Access](unifi-ssh-access.md) first for the two distinct SSH paths used below, and compare live state with [UniFi Network Setup and Tuning](unifi-network-setup.md) before changing the intended radio or SSID baseline.

The objective is to distinguish among three failure domains before changing configuration:

1. The iPhone or iPad is roaming, asleep, or has a poor Wi-Fi link.
2. Bonjour/mDNS discovery is not crossing an AP radio or bridge.
3. The Apple TV is discovered but its Companion service cannot be reached.

## Protocol Path

Apple's Remote uses Bonjour/mDNS discovery on UDP port `5353` and the Apple TV Companion service advertised by `_companion-link._tcp.local`. AirPlay advertises `_airplay._tcp.local`. A healthy path looks like:

```text
iPhone -> source AP/radio -> Layer-2 LAN -> destination AP/radio -> Apple TV
       <-       mDNS response and Companion TCP connection          <-
```

The source and destination AP may be the same device. Clients on the same Layer-2 network/VLAN do not need an mDNS gateway proxy. UniFi APs normally forward multicast unless multicast filtering, multicast/broadcast control, or client isolation prevents it. See Ubiquiti's [mDNS documentation](https://help.ui.com/hc/en-us/articles/12648701398807-UniFi-Gateway-Multicast-DNS-mDNS-Proxy) and [Wi-Fi settings reference](https://help.ui.com/hc/en-us/articles/32065480092951-UniFi-WiFi-SSID-and-AP-Settings-Overview).

## Preserve the Failure State

Before rebooting, reprovisioning, updating firmware, or saving any UniFi setting:

1. Record the exact local time of a failed Remote attempt.
2. Record the iPhone, Apple TV, and serving AP names, IP addresses, MAC addresses, radio bands, channels, and RSSI values.
3. Start the packet capture described below and reproduce the failure.

Even re-saving an unchanged global setting can reprovision APs and destroy the transient state under investigation. Treat **Apply**, **Save**, firmware-channel changes, and radio changes as service-affecting operations. After UI work, inspect the controller's administrator activity log so unexpected writes are not mistaken for organic disconnects.

## Establish the Current Topology

Do not rely on room names alone. An AP named for a room may not broadcast the SSID used by that room's Apple TV.

In UniFi Network, or through a read-only controller query, establish:

- SSID, VLAN/network, AP, radio band, channel, and channel width for both clients.
- Whether client isolation, multicast filtering, multicast/broadcast control, multicast-to-unicast, or minimum-RSSI rules are enabled.
- Whether the Apple TV has roamed to another AP.
- Whether the phone is repeatedly moving between 5 GHz, 6 GHz, or neighboring APs.

The Cloud Key is the source for controller configuration, retained events, statistics, and audit activity:

```bash
ssh root@192.168.1.180
```

UniFi Network currently stores its local data in MongoDB on port `27117`, principally in the `ace` and `ace_stat` databases. Direct database access is an internal, version-dependent diagnostic interface: make only read operations, inspect the live schema instead of assuming field names, and never update controller data through MongoDB.

## Inspect Live Wi-Fi Stations

Connect directly to the serving AP using its current address:

```bash
ssh ubnt@<ap-ip>
```

List wireless interfaces and associated stations:

```bash
iw dev
```

Once the SSID interface and client MAC are known, inspect each station:

```bash
hostapd_cli -i <ssid-interface> sta <client-mac>
```

Pay particular attention to:

- `signal` and whether it changes materially between bands.
- `inactive_msec`, especially when testing wake-from-sleep discovery.
- `tx_packets`, `tx_retries`, `tx_failed`, and receive drops.
- Authentication flags and AKM. Different Apple TV generations may legitimately use WPA2 or WPA3 on a transition-mode SSID.
- Repeated associations or roams at weak RSSI. A connection marked successful can still be a poor path for an interactive Remote session.

Inspect the in-use channel rather than assuming low RSSI means interference:

```bash
iw dev <ssid-interface> survey dump
hostapd_cli -i <ssid-interface> status
```

## Capture Discovery End to End

Capture on the Apple TV's serving AP before attempting the Remote connection. If the phone is on a different AP, capture there too before concluding that an absent packet originated at the phone. Substitute the current addresses:

```bash
tcpdump -ni any -e -vv \
  'udp port 5353 and (host <iphone-ip> or host <apple-tv-ip>)'
```

Using `any` produces duplicate-looking packets because it shows bridge ingress and egress. Those duplicates are useful: they establish whether the AP received and forwarded each packet. Stop the capture after the failed or successful attempt and note the kernel-drop count printed by `tcpdump`.

On macOS, independently browse the relevant Bonjour service:

```bash
dns-sd -B _companion-link._tcp local.
dns-sd -B _airplay._tcp local.
```

Interpret the capture in order:

- No query on the phone's serving AP: investigate the phone, its Wi-Fi transition, or the Remote app.
- Query leaves the phone's AP but never reaches the Apple TV's AP: investigate the intervening Layer-2 path.
- Query enters the AP but does not leave toward the Apple TV: investigate AP filtering, bridge state, or firmware.
- Apple TV receives the query but does not reply: investigate Apple TV sleep, tvOS, or service state.
- Reply enters the AP but is not forwarded: investigate AP multicast forwarding.
- Discovery completes in both directions: move to direct Companion reachability and phone roaming; multicast is not the failed layer.

Cached `dns-sd` output is not sufficient proof. The packet capture must show a live request and response, preferably while the Apple TV station is idle.

## Test Companion Reachability

Read the Companion port from the live `_companion-link._tcp` advertisement rather than permanently assuming a port. Test it from another LAN host, such as Home Assistant:

```bash
ssh root@homeassistant.local "nc -zvw 3 <apple-tv-ip> <companion-port>"
```

For corroboration, inspect Home Assistant's Apple TV integration without printing pairing credentials:

```bash
ssh root@homeassistant.local "ha core logs --lines 2000" | \
  rg -i 'apple.?tv|pyatv|<apple-tv-ip>'
```

If live mDNS succeeds, the Companion port opens, and Home Assistant has no corresponding errors, the AP-to-Apple-TV path is unlikely to be the cause of an intermittent Remote failure.

## 2026-08-05 Living Room Investigation

This case provides a baseline for future comparisons, not a permanent topology guarantee:

- **Living Room** is an older Apple TV HD on 5 GHz through the U7 Pro XG. Its roughly one-day telemetry averaged about `-63 dBm`, near-`100%` satisfaction, and effectively no dropped frames.
- A capture taken after five minutes of Apple TV radio inactivity showed the U7 forwarding a Companion/AirPlay query to it and forwarding its response back to the LAN with zero kernel capture drops.
- The advertised Companion and AirPlay TCP ports were reachable from Home Assistant.
- The iPhone 17 Pro Max repeatedly selected the U7's 160 MHz 6 GHz radio at approximately `-78` to `-89 dBm`, then moved back to 5 GHz or the Bedroom AP. Its 5 GHz connection was materially stronger and stable.
- The U7 was running firmware `8.6.11`. Its 6 GHz Extended Range/AFC mode was already off, so disabling Extended Range was not an applicable workaround.
- The AP named **AP Living Room** did not broadcast the `sintheta` SSID, so locking this Apple TV to that AP was not a valid option.
- Re-saving the existing global firmware channel caused an AP reprovision during the investigation. Disconnect and roam events at approximately `12:58 EDT` were therefore excluded from root-cause evidence. Remote reliability improved after this reprovision, so a transient AP state remained possible but unproven.

The strongest remaining hypothesis was the phone's weak 6 GHz selection or a transient U7 state, not persistent multicast failure on the Apple TV's link. Ubiquiti's official [8.6.11 release discussion](https://community.ui.com/releases/0d476b79-b684-4370-96af-ccb21ce35cbd) also contains a report of 6 GHz trouble from another iPhone 17 Pro Max user; treat community reports as supporting evidence rather than confirmation.

## If the Problem Returns

Do not immediately reprovision the AP. Capture one failed Remote attempt first, then:

1. Compare the phone's current 6 GHz and 5 GHz station records.
2. Confirm whether the mDNS query and response cross both AP radios.
3. Test the advertised Companion port.
4. Correlate the exact failure time with controller connectivity events and administrator activity.
5. Only after preserving evidence, run a reversible A/B test: temporarily disable 6 GHz on the U7 or reduce its width from 160 MHz to 80 MHz.

If the A/B test is needed, record the before/after time and revert it after enough Remote attempts to distinguish a real improvement from the temporary benefit of reprovisioning.
