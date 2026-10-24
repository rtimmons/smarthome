# UniFi Network Setup and Tuning

Current gateway and migration acceptance are dated **October 22, 2026**.
Radio/client tuning below retains the August baseline unless explicitly dated
otherwise. Use [SSH access](unifi-ssh-access.md) for verified connections,
[accepted changes and rollback](unifi-post-migration.md) for migration work and
[Bonjour troubleshooting](unifi-apple-tv-remote.md) before changing discovery.

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
| Gateway and controller | Cloud Gateway Max NS (`300 Newark Cloud Gateway Max`) | LAN gateway `192.168.1.1` | ONT to WAN; existing switch uplink to a Max LAN port | Network `10.6.106` on both source and destination before restore; Max UniFi OS `5.1.33` observed during setup |
| Retired active hardware / rollback | USG 3P and Cloud Key Gen2 Plus | Former Cloud Key reservation `192.168.1.180` | Disconnected during cutover | Ryan confirmed retirement from active service; preserve configurations and backups for rollback |
| Core switch | US 24 PoE 250W (`Switch Server Closet`) | `192.168.1.158` | Port 23 to gateway | Firmware `7.5.15.17146` observed October 22; powers both APs |
| Main AP | U7 Pro XG | `192.168.1.67` | Switch port 16, GbE | Main living-area capacity AP; Wi-Fi 7 and 6 GHz |
| Bedroom-wing AP | U6+ (`AP Bedroom`) | `192.168.1.128` | Switch port 10, wired; 100 Mb/s observed October 22 | Retained for coverage through the utility wall |

U7 `8.7.11` and U6+ `6.7.54` were observed October 22. Treat versions as
comparison data, not upgrade targets; capture an off-device backup before
firmware or Network changes. The AC-HD is no longer adopted; its last verified
switch port was down. Do not re-adopt retired hardware.

<a id="planned-cloud-gateway-max-migration"></a>

## Cloud Gateway Max migration

The Max NS (`UCG-Max-NS`) replaced routing and Network management on October 22.
A full console backup failed with an undiagnosed error; a fresh Network-only
`.unf` from Network `10.6.106` restored successfully. Ryan moved the ONT to Max
WAN, connected the existing switch to Max LAN and disconnected the USG/Cloud
Key. No Protect/storage migration was selected.

Leases, reservations, DNS failover, restricted printing, discovery, VPNs and
SSH are accepted in the [follow-up record](unifi-post-migration.md). Site Magic
supersedes the paused manual Lehigh peers; cloud IPsec now uses SHA-256.
Keep the old hardware disconnected and preserve all recovery copies. A hardware
rollback must coordinate routing and device management, not simply reconnect
the USG. Never restore a backup that reactivates the manual Lehigh peer while
Site Magic still advertises the same routes.

## Routed Networks and Services

| Name | Purpose | Addressing | Internet | Discovery and isolation | Audit note |
| --- | --- | --- | --- | --- | --- |
| `Default` | Trusted LAN | Untagged, `192.168.1.0/24`; DHCP `.20`-`.254` | Allowed | mDNS on; IGMP snooping off; UPnP allowed | Most infrastructure, media, and IoT clients still share this Layer-2 segment |
| `sintheta-printer` | Restricted print clients | VLAN 3, `192.168.6.0/24`; DHCP `.6`-`.254` | Disabled | Network and Wi-Fi client isolation on; mDNS on; IGMP snooping off | Firewall permits only Home Assistant TCP/8099 plus gateway DHCP and mDNS |

The zone firewall is active. Default and printer both remain in Internal, with
network-specific printer restrictions; eight custom policies are active and
three unreachable HA allow copies are paused. See [firewall rollback](unifi-post-migration.md#firewall-and-idsips).
`sintheta-iot` shares Default and is not a routed security boundary.

## Infrastructure Address Inventory

The following service endpoints use UniFi fixed-IP reservations on `Default`. Treat the numeric address as the stable network contract for embedded clients and repository configuration; do not depend on a `.local` name when the caller cannot reliably use mDNS.

| Device or service | UniFi identity | Reserved address | Repository or operational dependency |
| --- | --- | --- | --- |
| Home Assistant | `00:c0:08:97:1a:8d` | `192.168.1.163` | `sintheta-printer` TCP/8099 firewall destination and direct embedded-client API calls |
| QNAP NAS | `24:5e:be:5f:d6:ae` | `192.168.1.66` | Stable storage and administration endpoint |
| Canon printer | `34:9f:7b:a4:69:e0` | `192.168.1.150` | Stable printer/scanner endpoint |
| Brother QL-810W | `BRWACF23C3213C4` / `ac:f2:3c:32:13:c4` | `192.168.1.192` | `printer` add-on raw TCP/9100 target |
| LED Grid Wall | `ledgridwall` / `88:a2:9e:36:1b:dc` | `192.168.1.98` | `grid-dashboard` LEDGrid API target on TCP/5000 |
| Prusa Alpha | `10:9c:70:0a:ec:70` | `192.168.1.118` | Preserve the printer's address after the gateway migration collision |
| Nest I think | `64:16:66:97:50:0a` | `192.168.1.19` | Separate the thermostat from the printer's address; below the dynamic `.20`–`.254` pool |

All seven reservations matched during October 22 acceptance. Prusa Alpha and
the Nest previously collided at `.118`; moving the Nest to unused `.19` and
reserving both addresses resolved the conflict. Remove a reservation only after
checking current address ownership; do not blindly return the Nest to `.118`.

Use reserved numeric addresses for embedded clients. Ordinary DNS provides
`wiki.home.arpa`, `hass.home.arpa`, and automatically discovered Newark Bonjour
hostnames under `.home.arpa`; `.local` remains mDNS. Lehigh discovery and
cabin-side access verification are pending. See [DNS ownership](home-dns.md).

### WAN, VPN, and exposure baseline

- FiOS/WAN1 uses DHCP. The restored inactive Internet 2 record does not provide
  a second WAN or failover. Smart Queues and IPv6 remain outside this migration.
- Site Magic shares only Newark `192.168.1.0/24` and Lehigh `192.168.8.0/24`.
  Both old manual Lehigh definitions are paused. Cloud IPsec separately uses
  IKEv2/AES-256/SHA-256/DH14-PFS and LAN-only selectors.
- No manual port forwards were added. Existing secure-mode UPnP/NAT-PMP on
  Default was preserved; two dynamic mappings were observed. Inventory owners
  before disabling it. No-IP DDNS does not repair cloud firewall restrictions.
- Default IDS is Notify-only, excluding printer. Native ad blocking remains on;
  content categories and Safe Search remain off. Both AdGuards are required.

### Controller-wide services

mDNS remains enabled for Default and printer. The retained August baseline uses
all eligible services, IGMP snooping off and no external NetFlow/syslog export;
recheck effective settings before changing them. Do not enable IGMP snooping
without proving a multicast problem and locating the querier.

Max automatic backups are enabled; maintain verified encrypted off-device
exports. Use the supported UI for administrator/MFA/recovery and update-policy
reviews; old Cloud Key database flags do not establish the Max's current policy.

## Intended Radio Plan

| AP | Band | Channel | Width | Power mode | Reasoning |
| --- | --- | --- | --- | --- | --- |
| AP Bedroom | 2.4 GHz | 1 | 20 MHz | Low | Small coverage cell for the bedroom wing and primary bathroom |
| U7 Pro XG | 2.4 GHz | 11 | 20 MHz | Auto | Avoids co-channel overlap with the Bedroom AP while providing main-area coverage |
| AP Bedroom | 5 GHz | 36 | 40 MHz | Medium | Stable bedroom-wing coverage without overlapping the U7's channel block |
| U7 Pro XG | 5 GHz | 161 | 80 MHz | Auto | Higher-capacity main-area cell on a separate channel block |
| U7 Pro XG | 6 GHz | Auto; channel 149 observed October 22 | 160 MHz | Auto | Preserve high-throughput service; change only when a captured failure supports an A/B test |

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
- The only routed application exception is TCP from `sintheta-printer` to the reserved Home Assistant address `192.168.1.163:8099`; following zone policies drop all other routed traffic from the network
- Gateway policies allow only UDP mDNS to `224.0.0.251:5353` and DHCP renewals to `192.168.6.1:67`, then drop other access to the gateway

The print API uses unencrypted HTTP and the deliberately weak Wi-Fi credential is only an association barrier. The VLAN, client isolation, no-Internet setting, and ordered firewall rules are the security boundary. If Home Assistant's reservation changes, update the TCP/8099 destination rule at the same time.

October 22 associated-client checks accepted DHCP, HA discovery/TCP/8099,
blocked routed paths, a same-AP phone peer and a physical label print. See the
[acceptance record](unifi-post-migration.md#acceptance-and-backup).

### `sintheta-6-test`

- Native/Default network
- Broadcast only by the U7 Pro XG on 5 and 6 GHz
- WPA3
- Retained as a test network; do not treat its behavior as representative of all clients on the primary SSID

### Hidden Element adoption SSID

The controller also generates hidden `element-1d1546a132bac87b` on 2.4 and 5 GHz because **Element Adoption** is enabled. It is a controller-owned WPA2 adoption network, not a user SSID, and must not be edited like the four named client SSIDs. If no wireless UniFi camera, smart plug, or other Element/AutoLink device still depends on it, disable Element Adoption in the supported UI and confirm the generated SSID disappears. Removing unused adoption service reduces management attack surface and beacon overhead.

## Client Placement

Use `sintheta-iot` for identified, fixed 2.4 GHz clients such as the Brother
label printer, fan controllers, LED wall, thermostats and appliances. Move small
groups only after recording reservations and required flows. Keep phones,
computers, media devices and Sonos on `sintheta`; wired clients need no SSID move.

The Brother stays at `192.168.1.192`. Do not join the printer itself to
`sintheta-printer`: that SSID is for restricted print-request clients and cannot
accept Home Assistant's TCP/9100 connection to the printer.

## Switch Baseline

`Switch Server Closet` is the only adopted switch. The August 31 baseline used classic STP with priority `4096`; RSTP, global automatic edge detection, jumbo frames, flow control, DHCP snooping, and 802.1X port control were disabled. Port 23 is the gateway uplink, and ports 10 and 16 power the two APs. Port 21 formerly powered the Cloud Key, which was disconnected during the October 22 cutover. Recheck effective switch settings after migration. Use Ubiquiti's [STP hierarchy guidance](https://help.ui.com/hc/en-us/articles/24292724428311-Understand-and-Mitigate-Network-Loops-STP) when deciding root priority, RSTP, edge, and BPDU settings.

The August 31 100 Mb/s links on ports 12, 15, and 22 mapped to Sonos, Philips Hue, and Sonos records respectively. These devices commonly have fast-Ethernet interfaces, so link rate alone is not evidence of a cabling fault. Investigate only if the device's own specification promises gigabit or if errors, drops, or throughput symptoms appear. Port 24 was down and no pending device remained at that audit.

## Further changes

Migration acceptance is complete under the [recorded limits](unifi-post-migration.md#maintenance-and-evidence-limits).
Separate decisions remain for UPnP owners, Element Adoption/test-SSID purpose,
real IoT segmentation, MFA/recovery, log retention and STP/IPv6 policy. Preserve
radio/Sonos tuning and discovery behavior until measured evidence supports a
specific change. Do not migrate IoT clients as a substitute for a routed policy.

### API and MCP diagnostics

Prefer the supported Max UI and version-specific Integrations API. The existing
[read-only MCP launcher](../../network-infra/unifi-mcp/README.md) exposes 26 tools
and has passed live reads. Keep its settings-provided credential and controls;
SSH supplies effective-state checks. Never reconnect the Cloud Key or write
controller MongoDB to perform current diagnostics.

## Safe Change Workflow

1. Record the controller version, AP firmware, connected switch ports, current channels, widths, power modes, and SSID settings.
2. Preserve evidence for an active failure before saving or reprovisioning anything. A UniFi save can temporarily improve a transient issue and obscure the cause.
3. Make one coherent change in the supported UniFi UI.
4. Wait for every affected device to finish provisioning.
5. Verify the saved controller state and the effective AP configuration.
6. Record the change, observation window, and rollback condition in [change history](#retained-change-history).

Never update UniFi configuration through its MongoDB database. The database is an internal, version-dependent diagnostic interface and is read-only for this workflow.

### Relevant UI locations

- SSID settings: **Network > Settings > WiFi**
- Client reservations: **Network > Client Devices > select client > Settings > IP Settings > Fixed IP Address**
- Per-AP radios and meshing: **Network > UniFi Devices > select AP > Settings gear > Radios**
- Max console SSH (Network 10.6.106): **Settings > Management > General > SSH**; see [verified access and rollback](unifi-ssh-access.md)
- Adopted-device SSH: search Network settings for **Device SSH Authentication**
- Pending retired hardware: **Network > UniFi Devices**, filtered to **Pending Adoption**

## Verification Commands

### Controller configuration and reservations

Use the active Max's supported Network UI or its version-specific Integrations
API. The earlier direct MongoDB queries against the retired Cloud Key have been
removed from this operational path.

- **WiFi:** compare the intended WLAN names, network assignments, enabled bands,
  security/PMF, roaming and isolation settings with the dated baseline above.
- **Networks / Internet:** verify `Default`, `sintheta-printer` and WAN1 against
  the accepted topology. Do not recreate retired VLAN `esp` or WAN2.
- **Client Devices:** compare all seven [infrastructure mappings](#infrastructure-address-inventory),
  including the October 22 printer/Nest repair. A saved reservation does not
  establish the client's current lease or local-name resolution.
- **UniFi Devices:** confirm the switch and both APs online, wired uplinks,
  channels 1/11 on 2.4 GHz, and Mesh Parent/Connect disabled.

To verify gateway DNS, run:

```sh
just dns-check --resolver 192.168.1.1
```

This checks exact response semantics over UDP/TCP. Local handling without
upstream leakage and a fresh client's actual resolver path require the
additional [DNS acceptance checks](unifi-post-migration.md#native-dns-pilot).

### Effective AP configuration

Run this against each current AP address. The allowlist avoids printing Wi-Fi credentials:

```bash
ap_ip=192.168.1.67 # Repeat with 192.168.1.128 for AP Bedroom.
ssh -i .ssh/unifi-owner.pub -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile=.ssh/unifi_known_hosts \
  -o GlobalKnownHostsFile=/dev/null -o ForwardAgent=no \
  -o ConnectTimeout=5 "ubnt@$ap_ip" \
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

## Retained change history

- **August 5:** Established the two wired AP/radio plan and compatibility IoT
  SSID; mesh parent/connect remain disabled.
- **August 31:** Added the restricted printer VLAN/SSID and infrastructure
  reservations; removed orphan VLAN `esp` and unused WAN2. A restored inactive
  WAN2 definition is now visible but has no active service.
- **October 22:** Max cutover, address-conflict repair and the accepted
  [post-migration improvements](unifi-post-migration.md). Detailed prior plans,
  measurements and session history remain in Git and ignored private evidence.
