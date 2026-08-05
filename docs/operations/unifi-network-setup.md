# UniFi Network Setup and Tuning

Use this document as the current UniFi Network baseline and as the change log for future Wi-Fi tuning. Read [UniFi SSH Access](unifi-ssh-access.md) before running the verification commands below. For Apple TV Remote, AirPlay, or Bonjour failures, use the evidence-preserving workflow in [UniFi and Apple TV Remote Troubleshooting](unifi-apple-tv-remote.md).

The settings in this file were observed and verified on **2026-08-05**. UniFi device addresses, firmware, controller schema, RF conditions, and client placement can change; confirm live state before making another change.

## Design Goals

- Keep the two wired APs because the condo utility wall weakens coverage into the bedroom wing and primary bathroom.
- Prefer reliability and useful coverage over maximum benchmark throughput.
- Keep 2.4 GHz cells narrow and non-overlapping.
- Preserve 5 and 6 GHz capacity for phones, computers, media devices, and other capable clients.
- Give compatibility-sensitive IoT devices a simple 2.4 GHz/WPA2 SSID without changing their Layer-2 network.
- Make one RF or roaming change at a time and verify the effective AP configuration after provisioning.

## Current Topology

| Role | Device | Address | Wired uplink | Notes |
| --- | --- | --- | --- | --- |
| Controller | Cloud Key Gen2 Plus | `192.168.1.180` | LAN | UniFi Network `10.5.67` during the 2026-08-05 audit |
| Gateway | USG 3P | Dynamic/controller-reported | Switch | Default LAN gateway |
| Core switch | US 24 PoE 250W (`Switch Server Closet`) | Dynamic/controller-reported | — | Powers both active APs |
| Main AP | U7 Pro XG | `192.168.1.67` | Switch port 16, GbE | Main living-area capacity AP; Wi-Fi 7 and 6 GHz |
| Bedroom-wing AP | U6+ (`AP Bedroom`) | `192.168.1.128` | Switch port 10, GbE | Retained for coverage through the utility wall |

Versions observed during the audit were Network `10.5.67`, U7 Pro XG firmware `8.6.11`, and U6+ firmware `6.7.54`. Treat versions as comparison data, not upgrade targets; check current release notes and preserve failure evidence before changing firmware.

### Retired AC-HD cleanup

The AC-HD was removed from controller management, but the 2026-08-05 audit still found an **AC HD** device powered and advertising itself as ready for adoption. Its former address, `192.168.1.198`, also responded, and prior topology associated it with switch port 24.

Do not adopt it. Physically disconnect it or disable PoE only after confirming that port 24 still terminates at the retired AP. This is intentionally left as a manual confirmation step because switch-port labels and cabling can change.

## Intended Radio Plan

| AP | Band | Channel | Width | Power mode | Reasoning |
| --- | --- | --- | --- | --- | --- |
| AP Bedroom | 2.4 GHz | 1 | 20 MHz | Low | Small coverage cell for the bedroom wing and primary bathroom |
| U7 Pro XG | 2.4 GHz | 11 | 20 MHz | Auto | Avoids co-channel overlap with the Bedroom AP while providing main-area coverage |
| AP Bedroom | 5 GHz | 36 | 40 MHz | Medium | Stable bedroom-wing coverage without overlapping the U7's channel block |
| U7 Pro XG | 5 GHz | 161 | 80 MHz | Auto | Higher-capacity main-area cell on a separate channel block |
| U7 Pro XG | 6 GHz | Auto; channel 69 observed | 160 MHz | Auto | Preserve high-throughput service; change only when a captured failure supports an A/B test |

Both APs have wired uplinks, so **Mesh Parent** and **Mesh Connect** are disabled on both. This removes unnecessary wireless-mesh behavior, with the accepted tradeoff that an AP will not fall back to a wireless uplink if its Ethernet path fails.

Do not use 40 MHz channels on 2.4 GHz. Recheck channel utilization before changing the current channel plan; a visually empty channel at one moment is not sufficient evidence.

## Wi-Fi Networks

### `sintheta`

Primary client network:

- Native/Default network on `192.168.1.0/24`
- Broadcast by both APs on 2.4, 5, and 6 GHz
- WPA2/WPA3 transition mode with PMF optional
- Band Steering and BSS Transition enabled
- Fast Roaming (`802.11r`) disabled
- Minimum data rate: 12 Mbps
- DTIM: 3 on all bands
- Client isolation, multicast filtering, and multicast/broadcast blocking disabled

Fast Roaming remains off while compatibility-sensitive clients are still migrating away from this SSID. After the IoT migration is substantially complete, enabling `802.11r` on `sintheta` is a reasonable controlled experiment for Apple mobile devices. Record the change time and retain a rollback path.

### `sintheta-iot`

Compatibility SSID created on 2026-08-05:

- Uses the same Native/Default network and the existing Wi-Fi credential; never write that credential into this repository
- Broadcast by both APs on 2.4 GHz only
- WPA2 with PMF disabled
- Fast Roaming and BSS Transition disabled
- Default 1 Mbps minimum/basic rate and DTIM 1
- Client isolation, multicast filtering, multicast-to-unicast, and multicast/broadcast blocking disabled
- No VLAN, firewall, routing, DHCP, or mDNS changes

This SSID is **not a security boundary**. Clients remain on the same `192.168.1.0/24` Layer-2 network and retain the same routes and peer visibility as clients on `sintheta`. Its purpose is radio and authentication compatibility. A future security-isolation project must explicitly introduce a VLAN, firewall policy, DHCP scope, and any required mDNS forwarding.

### `sintheta-6-test`

- Native/Default network
- Broadcast only by the U7 Pro XG on 5 and 6 GHz
- WPA3
- Retained as a test network; do not treat its behavior as representative of all clients on the primary SSID

## Client Placement

Move fixed, low-bandwidth, compatibility-sensitive Wi-Fi devices to `sintheta-iot`:

- Brother QL-810W, observed as `BRWACF23C3213C4`
- `fancontroller-r3-1-8b11b8` and `fancontroller-r3-1-8b12ee`
- `ledgridwall`
- GE appliance `GEMODULEC4DD`
- Nuheat thermostats, including the previously observed `Nuheat A (fishy grl)` record
- Nest thermostats (`Nest 1` through `Nest 4` and the older `Nest I think` record)
- Sense energy monitor `Sense-N304000573`
- Other fixed 2.4 GHz appliances after identifying them, including the observed `MT7681` client

Keep performance-sensitive or roaming clients on `sintheta`:

- Phones, tablets, computers, and watches
- Apple TVs, Chromecast, Roku TV, and Nintendo Switch
- Sonos speakers and amps
- Home Assistant and other wired infrastructure

Do not move a wired device merely because it is an IoT product. For another printer, move it only if it is wireless and benefits from the compatibility settings; same-subnet AirPrint discovery works across these two SSIDs.

## Safe Change Workflow

1. Record the controller version, AP firmware, connected switch ports, current channels, widths, power modes, and SSID settings.
2. Preserve evidence for an active failure before saving or reprovisioning anything. A UniFi save can temporarily improve a transient issue and obscure the cause.
3. Make one coherent change in the supported UniFi UI.
4. Wait for every affected device to finish provisioning.
5. Verify the saved controller state and the effective AP configuration.
6. Record the change, observation window, and rollback condition in [Iteration Log](#iteration-log).

Never update UniFi configuration through its MongoDB database. The database is an internal, version-dependent diagnostic interface and is read-only for this workflow.

### Relevant UI locations

- SSID settings: **Network > Settings > WiFi**
- Per-AP radios and meshing: **Network > UniFi Devices > select AP > Settings gear > Radios**
- Controller SSH: **Control Plane > Console > SSH**
- Adopted-device SSH: search Network settings for **Device SSH Authentication**
- Pending retired hardware: **Network > UniFi Devices**, filtered to **Pending Adoption**

## Verification Commands

### Controller WLAN state

This query intentionally excludes passphrases:

```bash
ssh root@192.168.1.180 "mongo --quiet --port 27117 ace --eval '
db.wlanconf.find(
  {name:{\$in:[\"sintheta\",\"sintheta-iot\",\"sintheta-6-test\"]}},
  {
    _id:0, name:1, enabled:1, networkconf_id:1, wlan_bands:1,
    security:1, wpa_mode:1, pmf_mode:1, iapp_enabled:1,
    roaming_assistant_na_enabled:1, minrate_ng_enabled:1,
    minrate_ng_data_rate_kbps:1, dtim_mode:1, dtim_ng:1,
    ap_group_mode:1
  }
).forEach(printjson)
'"
```

### Controller AP state

```bash
ssh root@192.168.1.180 "mongo --quiet --port 27117 ace --eval '
db.device.find({type:\"uap\"}).forEach(function(d) {
  printjson({
    name:d.name,
    model:d.model,
    ip:d.ip,
    mesh_sta_vap_enabled:d.mesh_sta_vap_enabled,
    radio_table:(d.radio_table || []).map(function(r) {
      return {
        radio:r.radio,
        channel:r.channel,
        ht:r.ht,
        tx_power_mode:r.tx_power_mode
      }
    })
  })
})
'"
```

The 2.4 GHz result should show channel 1 for `AP Bedroom` and channel 11 for `U7 Pro XG`. The controller field `mesh_sta_vap_enabled:false` confirms that wireless mesh connection is disabled; also confirm in the UI that both **Mesh Parent** and **Mesh Connect** are off.

### Effective AP configuration

Run this against each current AP address. The allowlist avoids printing Wi-Fi credentials:

```bash
ssh ubnt@<ap-ip> \
  "grep -E '^(wireless\.[0-9]+\.(ssid|devname|dtim_period|l2_isolation|mcast\.enhance|mcastrate|uapsd)|aaa\.[0-9]+\.(bss_transition|ft\.status|wpa3\.ft\.status)|bandsteering\.(status|mode)|radio\.[0-9]+\.(channel|ht|txpower|txpower_mode))=' /tmp/system.cfg"
```

Expected `sintheta-iot` properties on both APs include:

- Exactly one 2.4 GHz virtual interface; no 5 or 6 GHz instance
- `dtim_period=1`
- `ft.status=disabled`
- `bss_transition=disabled`
- `l2_isolation=disabled`
- `mcast.enhance=0`

`/tmp/system.cfg` is generated state and can change across firmware versions. Read it for verification; do not edit it.

## Performance Signals to Watch

The one-time audit immediately around provisioning showed elevated 2.4 GHz contention:

- AP Bedroom on channel 1: approximately 86% busy utilization and 45% TX retries
- U7 Pro XG while still on channel 6: approximately 51% busy utilization and 15% TX retries

These are snapshots, not benchmarks. The channel-11 change and IoT migration should be evaluated over a longer comparable period. Watch:

- Channel busy utilization and TX retry rate per AP and band
- Client RSSI, reconnects, and roaming between the two APs
- Primary-bath coverage and device reliability on the low-power Bedroom AP
- Whether 2.4 GHz clients accumulate disproportionately on one AP
- Apple TV Remote/AirPlay behavior before and after any roaming change

Do not raise AP transmit power solely to hide poor client RSSI; asymmetric links can make the AP audible to a client that cannot transmit back reliably.

## Iteration Log

### 2026-08-05: two-AP radio plan and IoT compatibility SSID

- Confirmed the U7 Pro XG and AP Bedroom use wired GbE uplinks.
- Retained the Bedroom AP because the utility wall causes spotty primary-bath coverage without it.
- Set the U7 2.4 GHz radio to channel 11/20 MHz; retained Bedroom channel 1/20 MHz.
- Retained the non-overlapping 5 GHz plan and the U7's 160 MHz 6 GHz radio.
- Disabled Mesh Parent and Mesh Connect on both wired APs.
- Created `sintheta-iot` on the Default network with the compatibility settings documented above.
- Deliberately left Fast Roaming off on `sintheta` until IoT migration reduces compatibility risk.
- Found the retired AC-HD still powered and pending adoption; physical/PoE cleanup remains open.

### Next controlled iterations

1. Move the documented IoT clients in small groups and observe stability.
2. Compare 2.4 GHz utilization and retries after the migration.
3. Confirm primary-bath coverage remains acceptable before reducing Bedroom AP power further or removing it.
4. When legacy clients are off `sintheta`, test Fast Roaming there with a recorded start time and rollback condition.
5. If Apple TV Remote problems recur, capture a failure before changing 6 GHz width or reprovisioning the U7.
