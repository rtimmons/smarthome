# UniFi Network Setup and Tuning

Use this document as the current UniFi Network baseline and as the change log for future Wi-Fi tuning. Read [UniFi SSH Access](unifi-ssh-access.md) before running the verification commands below. For Apple TV Remote, AirPlay, or Bonjour failures, use the evidence-preserving workflow in [UniFi and Apple TV Remote Troubleshooting](unifi-apple-tv-remote.md).

The whole-site configuration baseline in this file was observed read-only on **2026-08-31**. The radio investigation history from **2026-08-05** remains useful comparison data. UniFi device addresses, firmware, controller schema, RF conditions, client placement, and dynamic UPnP mappings can change; confirm live state before making another change.

## Design Goals

- Keep the two wired APs because the condo utility wall weakens coverage into the bedroom wing and primary bathroom.
- Prefer reliability and useful coverage over maximum benchmark throughput.
- Keep 2.4 GHz cells narrow and non-overlapping.
- Preserve 5 and 6 GHz capacity for phones, computers, media devices, and other capable clients.
- Give compatibility-sensitive IoT devices a simple 2.4 GHz/WPA2 SSID without changing their Layer-2 network.
- Keep the intentionally weak print-client credential behind VLAN, firewall, and client-isolation controls.
- Make one RF or roaming change at a time and verify the effective AP configuration after provisioning.

## Current Topology

| Role | Device | Address | Wired uplink | Notes |
| --- | --- | --- | --- | --- |
| Controller | Cloud Key Gen2 Plus | `192.168.1.180` | Switch port 21, GbE | UniFi OS `5.1.31`; Network `10.6.101` |
| Gateway | USG 3P (`Security Gateway`) | LAN gateway `192.168.1.1` | Switch port 23, GbE | Firmware `4.4.57.5578372`; controller `ip` field is the public WAN address, not its management address |
| Core switch | US 24 PoE 250W (`Switch Server Closet`) | `192.168.1.158` | Port 23 to gateway | Firmware `7.4.1.16850`; powers both active APs |
| Main AP | U7 Pro XG | `192.168.1.67` | Switch port 16, GbE | Main living-area capacity AP; Wi-Fi 7 and 6 GHz |
| Bedroom-wing AP | U6+ (`AP Bedroom`) | `192.168.1.128` | Switch port 10, GbE | Retained for coverage through the utility wall |

Device firmware observed on 2026-08-31 was U7 Pro XG `8.7.11.19419`, U6+ `6.7.54.15663`, switch `7.4.1.16850`, and USG `4.4.57.5578372`. The controller marked all four adopted devices supported, but Ubiquiti's [product-lifecycle documentation](https://help.ui.com/hc/en-us/articles/1500001268521-Ubiquiti-s-Vintage-and-Legacy-Products) classifies the USG family as **Legacy**, meaning it no longer receives updates and future software may not fully support it. Treat every version here as comparison data, not an upgrade target; read current release notes, preserve failure evidence, and take an off-device backup before changing firmware or the Network application.

### Retired AC-HD cleanup

The AC-HD was removed from controller management. The 2026-08-05 audit still found it powered and pending adoption at `192.168.1.198`, associated with switch port 24.

On 2026-08-31 the controller had exactly four device records, all adopted, and switch port 24 was down with no active PoE load. Controller cleanup is therefore complete. The remaining open question is only physical disposition: confirm whether the retired AP and its cable have been removed or merely left disconnected. Do not re-adopt it.

## Routed Networks and Services

| Name | Purpose | Addressing | Internet | Discovery and isolation | Audit note |
| --- | --- | --- | --- | --- | --- |
| `Default` | Trusted LAN | Untagged, `192.168.1.0/24`; DHCP `.20`-`.254` | Allowed | mDNS on; IGMP snooping off; UPnP allowed | Most infrastructure, media, and IoT clients still share this Layer-2 segment |
| `esp` | Unresolved legacy network | VLAN 2, `192.168.5.0/24`; DHCP `.6`-`.254` | Disabled | mDNS on; IGMP snooping off; network isolation not enabled | No SSID and no retained client records; determine its owner and purpose before reusing or deleting it |
| `sintheta-printer` | Restricted print clients | VLAN 3, `192.168.6.0/24`; DHCP `.6`-`.254` | Disabled | Network and Wi-Fi client isolation on; mDNS on; IGMP snooping off | Firewall permits only Home Assistant TCP/8099 plus gateway DHCP and mDNS |

The global inter-network security posture is `ALLOW_ALL`. The five `sintheta-printer` rules are the only custom firewall rules, so `esp` is not a security boundary from the trusted LAN or site-to-site VPN merely because its Internet toggle is off. The `sintheta-iot` SSID uses `Default`; it is also not a routed security boundary.

### WAN, VPN, and exposure baseline

- `FiOS` is the primary DHCP WAN. `Internet 2` is a DHCP, failover-only secondary WAN.
- Smart Queues are disabled on both WANs. IPv6 protocol selection is disabled even though a legacy `ipv6_enabled` field remains true; treat IPv6 as not configured until verified from a client and gateway firewall.
- The enabled `300Newarkto2117Lehigh` site-to-site IPsec VPN reaches `192.168.8.0/24`, selects **all** local subnets, and uses IKEv1, AES-128, SHA-1, DH group 14, and PFS. Ubiquiti's current [manual IPsec guidance](https://help.ui.com/hc/en-us/articles/31176030265111-IPSec-Site-to-Site-VPN-for-UMR) recommends at least AES-256 with SHA-256 for stronger security, subject to peer support.
- No manual port forwards, static routes, or firewall address groups exist. UPnP and NAT-PMP are enabled in secure mode for `Default`; live dynamic mappings were visible during the audit, so “no manual port forwards” does not mean “no inbound exposure.” Ubiquiti's [UPnP guidance](https://help.ui.com/hc/en-us/articles/12648697125783-UniFi-Gateway-UPnP) recommends leaving it disabled unless required.
- No-IP dynamic DNS publishes `timmonslee.hopto.org` on the primary WAN.

### Controller-wide services

- mDNS proxy mode is `all` across all eligible networks, with no custom service allowlist. See Ubiquiti's [mDNS proxy modes and service scoping](https://help.ui.com/hc/en-us/articles/12648701398807-UniFi-Gateway-Multicast-DNS-mDNS-Proxy).
- Global and per-network IGMP snooping are disabled. Do not enable it as a generic discovery fix; first establish a multicast problem, querier placement, and affected devices.
- DPI and advertisement filtering are enabled for `Default`. Suspicious-activity IDS/IPS, endpoint scanning, and the honeypot are disabled. DNS-over-HTTPS is off.
- NetFlow and remote syslog export are disabled. Local per-client time-series data is retained.
- The controller's management `auto_upgrade` flag is enabled for 03:00 local time and the firmware channel is `release`. Verify exactly which application/device scopes the supported UI currently assigns to those values before relying on them as an update policy.
- Network-only automatic backups run daily at 00:00 UTC and retain 14 files. Cloud backup is disabled; this does not establish an off-device recovery copy. Ubiquiti recommends a comprehensive System Config backup for CloudKeys and documents both [cloud and offline recovery paths](https://help.ui.com/hc/en-us/articles/360008976393-Backups-and-Migration-in-UniFi).
- The site database contains one owner administrator with email and push alerts enabled. Confirm the Control Plane's complete administrator/MFA and account-recovery state in the supported UI; the site database is not authoritative for every UniFi Identity account.

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

### `sintheta-printer`

Restricted print-client SSID created on 2026-08-31:

- Dedicated `sintheta-printer` network on VLAN 3, `192.168.6.0/24`, with DHCP from `192.168.6.6` through `192.168.6.254`
- Broadcast by both APs on 2.4 GHz only
- WPA2 with PMF disabled; never write the Wi-Fi credential into this repository
- Fast Roaming and BSS Transition disabled; DTIM 1
- Client isolation enabled; multicast filtering, multicast-to-unicast, and multicast/broadcast blocking disabled so mDNS can operate
- Network isolation enabled and Internet access disabled
- Gateway mDNS proxy enabled so clients can resolve `homeassistant.local`
- The only routed application exception is TCP from `sintheta-printer` to the reserved Home Assistant address `192.168.1.163:8099`; a following LAN In rule drops all other traffic from the network
- LAN Local rules allow only UDP mDNS to `224.0.0.251:5353` and DHCP renewals to `192.168.6.1:67`, then drop other access to the gateway

The print API uses unencrypted HTTP and the deliberately weak Wi-Fi credential is only an association barrier. The VLAN, client isolation, no-Internet setting, and ordered firewall rules are the security boundary. If Home Assistant's reservation changes, update the TCP/8099 destination rule at the same time.

Controller state and both APs' generated configurations were verified. An actual client has not yet joined this SSID, so DHCP, cross-VLAN mDNS, positive TCP/8099 access, and negative Internet/LAN tests remain required before treating the path as operational.

### `sintheta-6-test`

- Native/Default network
- Broadcast only by the U7 Pro XG on 5 and 6 GHz
- WPA3
- Retained as a test network; do not treat its behavior as representative of all clients on the primary SSID

### Hidden Element adoption SSID

The controller also generates hidden `element-1d1546a132bac87b` on 2.4 and 5 GHz because **Element Adoption** is enabled. It is a controller-owned WPA2 adoption network, not a user SSID, and must not be edited like the four named client SSIDs. If no wireless UniFi camera, smart plug, or other Element/AutoLink device still depends on it, disable Element Adoption in the supported UI and confirm the generated SSID disappears. Removing unused adoption service reduces management attack surface and beacon overhead.

## Client Placement

Move fixed, low-bandwidth, compatibility-sensitive Wi-Fi devices to `sintheta-iot`:

- Brother QL-810W, observed as `BRWACF23C3213C4` / `ac:f2:3c:32:13:c4`
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

The Brother printer's last retained record was `192.168.1.192` on `sintheta` through the U7's 2.4 GHz radio. The printer add-on is configured for that address, but the controller has **no fixed-IP reservation** for its MAC. Create and verify the reservation before relying on `.192` or moving the printer to `sintheta-iot`. Do not join the Brother printer itself to `sintheta-printer`: that SSID is for untrusted print-request clients and intentionally cannot accept Home Assistant's TCP/9100 connection to the printer.

## Switch Baseline

`Switch Server Closet` is the only adopted switch. It uses classic STP with priority `4096`; RSTP, global automatic edge detection, jumbo frames, flow control, DHCP snooping, and 802.1X port control are disabled. Port 23 is the gateway uplink. Ports 10 and 16 power the two APs, and port 21 powers the Cloud Key. Use Ubiquiti's [STP hierarchy guidance](https://help.ui.com/hc/en-us/articles/24292724428311-Understand-and-Mitigate-Network-Loops-STP) when deciding root priority, RSTP, edge, and BPDU settings.

The live 100 Mb/s links on ports 12, 15, and 22 mapped to Sonos, Philips Hue, and Sonos records respectively. These devices commonly have fast-Ethernet interfaces, so link rate alone is not evidence of a cabling fault. Investigate only if the device's own specification promises gigabit or if errors, drops, or throughput symptoms appear. Port 24 is down and no pending device remains.

## Audit Recommendations and Decision Register

The recommendation is not permission to change live state. Answer the question in the last column, record the intended value and rollback, then use the [Safe Change Workflow](#safe-change-workflow).

| Priority | Setting or scope | Observed value | Recommended next step | Question that determines the target value |
| --- | --- | --- | --- | --- |
| High | `sintheta-printer` validation | Saved and provisioned; no client test | Join an expendable client and prove DHCP, `homeassistant.local`, TCP/8099, blocked Internet, blocked other LAN/gateway ports, and client isolation | Which device types will join, and do any require NTP or other traffic beyond the print API? |
| High | Brother address | Add-on expects `192.168.1.192`; no reservation exists | Reserve `.192` to `ac:f2:3c:32:13:c4`, verify a renewed lease, then move it to `sintheta-iot` only if desired | Must existing jobs keep `.192`, and is the printer staying on `Default` long-term? |
| High | Gateway lifecycle | USG 3P / firmware 4.4.57; Ubiquiti classifies USG as Legacy | Plan replacement before a controller update or hardware failure forces it | Preserve Cloud Key or consolidate into a Cloud Gateway? Required WAN count, site VPNs, rack form, throughput, IDS/IPS rate, and migration window? |
| High | UPnP/NAT-PMP | Enabled on `Default`; live dynamic mappings exist | Inventory mappings and owners, then disable UPnP if each need can be removed or replaced with VPN/manual narrowly scoped access | Are Plex remote access, gaming, peer-to-peer apps, or Home Assistant integrations relying on a mapping? |
| High | Site-to-site VPN crypto and scope | IKEv1/AES-128/SHA-1; all local subnets included | Coordinate both peers toward IKEv2, AES-256, and SHA-256, and explicitly select only required local networks | What gateway is at 2117 Lehigh, what does it support, and should it reach `esp` or any future IoT VLAN? |
| Medium | IoT segmentation | `sintheta-iot` shares trusted `Default` | Inventory dependencies and migrate small device groups to a real restricted VLAN with explicit Home Assistant and discovery exceptions | Which Sonos, AirPlay, Chromecast, printer, cloud, and phone-to-device flows must cross the boundary? |
| Medium | Dormant `esp` network | VLAN 2, no Internet, mDNS on, no isolation, no SSID or retained clients | Identify its owner; document and secure it, repurpose it deliberately, or remove it | Was it intended for ESPHome provisioning, and does any static device use it without appearing in controller history? |
| Medium | mDNS proxy | All services across all eligible networks | Move toward custom networks/services only after a test proves raw `homeassistant.local` A-record resolution still works for print clients | Which cross-VLAN services are actually required, and can UniFi's custom service model preserve hostname-only lookup? |
| Medium | Backups | 14 daily controller-local Network backups; cloud backup off | Maintain an encrypted off-device System Config backup and test that the intended replacement hardware can restore it | Is UI cloud backup acceptable, or where will offline exports be stored and how often will restoration be tested? |
| Medium | Management access and logs | One recorded owner; device password auth enabled; NetFlow/syslog off | Verify MFA/recovery and a break-glass path; repair USG key access before considering key-only device SSH; choose a log destination if forensic history matters | Who must recover the site if the owner account or Cloud Key fails, and what event retention/privacy budget is appropriate? |
| Medium | Hidden/test WLANs | Element Adoption and `sintheta-6-test` enabled | Disable each only when its owner confirms it is unused; verify AP generated state afterward | Are any AutoLink/Element devices still present, and what experiment/expiry date owns `sintheta-6-test`? |
| Medium | STP | Classic STP, sole switch priority 4096 | Document the intended root and consider RSTP during a maintenance window; set edge/BPDU behavior only after mapping downstream switches | Is `Switch Server Closet` the permanent root, and which ports lead to switches or bridges rather than endpoints? |
| Low | Dual WAN | `Internet 2` is failover-only; WAN event reporting off | Document the provider and run a witnessed failover/restore test at an acceptable time | What outage duration is acceptable, and should failover generate an external alert? |
| Low | DNS/filtering | DHCP DNS is automatic; a stored `.163` value is inactive-looking; ad filtering is enabled; DoH off | Verify DNS servers from a fresh client lease before changing DNS, filtering, or encrypted DNS | Is Home Assistant intended to be the resolver, and must filtering be enforceable rather than best-effort? |
| Low | Smart Queues and IPv6 | Smart Queues off; IPv6 protocol disabled | Leave off unless a measured latency or IPv6 requirement justifies an end-to-end design and gateway-capacity test | What are sustained WAN rates, bufferbloat under load, ISP IPv6 support, and VPN/firewall requirements? |

### Optional audit automation

No UniFi/Ubiquiti skill was present in OpenAI's curated skill catalog on 2026-08-31. The strongest public candidates found were:

- [`thathaneydude/unifi`](https://github.com/thathaneydude/unifi) — best fit for repeatable read-only assessment. Its `unifi-security-assessment` orchestrates network security, segmentation/Wi-Fi, asset inventory, and Protect domain skills, and its repository tests reject mutating operations in those skills. It currently targets a Network `10.3.58` Integration API specification, so validate it against this `10.6.101` controller and retain the controller-specific checks in this runbook.
- [`sirkirby/unifi-mcp`](https://github.com/sirkirby/unifi-mcp) — best fit for broader health, firewall-audit, and eventual control workflows. It ships a Codex-compatible plugin, snapshot/preview-before-confirm patterns, and a large MCP tool surface. It also introduces a live mutation path and authenticates with a local admin/service account, so create a dedicated least-privilege identity and approve source review, secret storage, rollback, and legacy-USG coverage before installation.
- [`garymike/unifi-security-advisor`](https://github.com/garymike/unifi-security-advisor) — a promising standalone, local, read-only advisor that asks intent questions and can audit through the official API or an offline backup. It is not a Codex skill and is pre-1.0; use it only after source review in an isolated environment.

Choose tooling based on the intended authority: a recurring report should use a read-only API key and produce an evidence/coverage record; live control should use a dedicated account, explicit preview/confirmation, automatic snapshots, and tested rollback. No third-party tool replaces AP/switch effective-state checks or the legacy-USG-specific fields documented here.

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
  {name:{\$in:[
    \"sintheta\", \"sintheta-iot\", \"sintheta-printer\",
    \"sintheta-6-test\", \"element-1d1546a132bac87b\"
  ]}},
  {
    _id:0, name:1, enabled:1, networkconf_id:1, wlan_bands:1,
    security:1, wpa_mode:1, pmf_mode:1, hide_ssid:1,
    element_adopt:1, iapp_enabled:1,
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

Expected `sintheta-iot` and `sintheta-printer` properties on both APs include:

- Exactly one 2.4 GHz virtual interface; no 5 or 6 GHz instance
- `dtim_period=1`
- `ft.status=disabled`
- `bss_transition=disabled`
- `l2_isolation=disabled` for `sintheta-iot`; `enabled` for `sintheta-printer`
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

### 2026-08-31: restricted printer-client SSID

- Created VLAN 3 and the `192.168.6.0/24` `sintheta-printer` network with DHCP, network isolation, Internet access disabled, and mDNS enabled.
- Created the 2.4 GHz-only `sintheta-printer` WPA2 SSID on both APs with PMF, Fast Roaming, and BSS Transition disabled and client isolation enabled.
- Added an ordered LAN In allow for TCP to `192.168.1.163:8099`, followed immediately by a drop for all other traffic from the printer network.
- Added ordered LAN Local allows for mDNS and DHCP, followed by a drop for other gateway access.
- Verified the saved controller state and both APs' effective configurations without reading or recording the Wi-Fi credential.
- End-to-end validation from an associated client remains open; saved/effective AP state is not proof of the DHCP and firewall path.
- Roll back by removing the SSID, its five named firewall rules, and then the unused VLAN/network, in that order.

### 2026-08-31: whole-site read-only audit

- Reconciled current controller, gateway, switch, AP, network, WLAN, firewall, VPN, discovery, update, backup, and management settings.
- Confirmed the former AC-HD is absent from the device database, all four current devices are adopted, and switch port 24 is down.
- Confirmed that the only custom firewall rules are the five printer-network rules and documented the global `ALLOW_ALL` consequence for other LANs.
- Recorded recommendations and the intent questions that must be answered before changing security, multicast, VPN, STP, WAN, DNS, or update settings.
- Performed no live changes during this audit.

### Next controlled iterations

1. Complete the `sintheta-printer` client validation and Brother fixed-IP reservation in the decision register.
2. Inventory live UPnP mappings and decide whether each one is still required before disabling UPnP.
3. Plan the legacy USG replacement and coordinated IPsec modernization.
4. Resolve the purpose of `esp`, Element Adoption, and `sintheta-6-test` before retaining or removing them.
5. Move documented IoT clients in small groups only after defining a real segmentation policy and required flows.
6. Compare 2.4 GHz utilization and retries after migration.
7. Confirm primary-bath coverage remains acceptable before reducing Bedroom AP power further or removing it.
8. When legacy clients are off `sintheta`, test Fast Roaming there with a recorded start time and rollback condition.
9. If Apple TV Remote problems recur, capture a failure before changing 6 GHz width or reprovisioning the U7.
