# UniFi Network Setup and Tuning

Use this document as the current UniFi Network baseline and as the change log for future Wi-Fi tuning. Read [UniFi SSH Access](unifi-ssh-access.md) before running the verification commands below. For Apple TV Remote, AirPlay, or Bonjour failures, use the evidence-preserving workflow in [UniFi and Apple TV Remote Troubleshooting](unifi-apple-tv-remote.md).

The whole-site configuration baseline in this file was observed read-only on **2026-08-31**. The radio investigation history from **2026-08-05** remains useful comparison data. UniFi device addresses, firmware, controller schema, RF conditions, client placement, and dynamic UPnP mappings can change; confirm live state before making another change.

**2026-10-22 migration update:** The **Cloud Gateway Max NS (US Version), UCG-Max-NS**, now provides routing and UniFi Network management. Ryan confirmed the switch and both APs online in its controller. Gateway, public DNS, Internet HTTPS, Home Assistant, and numeric wiki checks passed from the Mac. See [migration status](#cloud-gateway-max-migration) for the restore path and remaining acceptance checks. Other dated configuration observations below remain historical until rechecked.

Ryan authorized the [post-migration improvements](unifi-post-migration.md) on
October 22. The forwarding-only DNS hybrid, associated printer-client allow/deny tests,
cloud SHA-256 reconnect/PFS rekey and native read-only MCP now pass their dated
checks. Site Magic and zone migration await the specific remaining client
evidence in that checklist.

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
| Core switch | US 24 PoE 250W (`Switch Server Closet`) | `192.168.1.158` | Port 23 to gateway | Firmware `7.4.1.16850`; powers both active APs |
| Main AP | U7 Pro XG | `192.168.1.67` | Switch port 16, GbE | Main living-area capacity AP; Wi-Fi 7 and 6 GHz |
| Bedroom-wing AP | U6+ (`AP Bedroom`) | `192.168.1.128` | Switch port 10, GbE | Retained for coverage through the utility wall |

Device firmware observed on 2026-08-31 was U7 Pro XG `8.7.11.19419`, U6+ `6.7.54.15663`, switch `7.4.1.16850`, and USG `4.4.57.5578372`. The controller marked all four adopted devices supported, but Ubiquiti's [product-lifecycle documentation](https://help.ui.com/hc/en-us/articles/1500001268521-Ubiquiti-s-Vintage-and-Legacy-Products) classifies the USG family as **Legacy**, meaning it no longer receives updates and future software may not fully support it. Treat every version here as comparison data, not an upgrade target; read current release notes, preserve failure evidence, and take an off-device backup before changing firmware or the Network application.

### Retired AC-HD cleanup

The AC-HD was removed from controller management. The 2026-08-05 audit still found it powered and pending adoption at `192.168.1.198`, associated with switch port 24.

On 2026-08-31 the controller had exactly four device records, all adopted, and switch port 24 was down with no active PoE load. Controller cleanup is therefore complete. The remaining open question is only physical disposition: confirm whether the retired AP and its cable have been removed or merely left disconnected. Do not re-adopt it.

<a id="planned-cloud-gateway-max-migration"></a>

## Cloud Gateway Max migration

### Cutover and verified operation — 2026-10-22

The full `.unifi` console backup failed to restore with a generic error; its
cause was not established. A fresh Network-only `.unf` backup was downloaded
from **Cloud Key > Network > Settings > Management > Download Backup**, with
**Backup for All Applications and Settings** unchecked and only **Network**
selected. Firefox reported the 71.6 KB download complete. Both Network
applications were version `10.6.106`.

Ryan restored the `.unf` on the Max. Cloud access then stalled while the Max's
WAN was connected to the existing switch. Restored LAN/upstream subnet overlap
was suspected, not confirmed by logs. With the ONT moved to the Max's WAN and
its LAN still disconnected, Ryan could see the existing devices and networks.
He then completed the instructed cutover: disconnect the Cloud Key and move the
switch uplink from the USG's LAN to a Max LAN port. Ryan reported household
operation working and all three retained UniFi devices online in the Max.

Read-only checks from the Mac confirmed default gateway `192.168.1.1`, two
successful gateway pings, public A resolution through that gateway, Internet
HTTPS 200, Home Assistant HTTP 200 at `192.168.1.163:8123`, and wiki HTTP 200 at
`192.168.1.66`. These establish basic connectivity, not complete acceptance.
Fresh wired/wireless DHCP leases and reservations, printer VLAN isolation,
printing, Sonos/AirPlay/Apple TV discovery and Cloud Key other applications remain
unverified. Later that day, a fresh full Max System export was encrypted
off-device and authenticated-decryption checked. Safari saved the native wiki A
record and `home.arpa` forwarding to HA AdGuard, then opened the wiki by name.
The existing ad-only Default policy was inspected and preserved. The resumed session paused the duplicate native A record so forwarding alone
passes the exact UDP/TCP contract and synthetic local-rewrite evidence. It also
verified a fresh Mac wireless lease, seven reservations, printer-client paths
and Bonjour advertised TCP reachability. Wired, second-peer, printing and live
packet evidence remain separate. See the
[follow-up record](unifi-post-migration.md) for exact settings and pending checks.

The WAN address changed during cutover. On October 22, the Lehigh endpoint of
`300Newarkto2117Lehigh` still targeted an old Newark WAN address. Updating that
remote address to the Max's verified WAN address restored reachability: the Mac
received three of three replies from Lehigh's `192.168.8.1` gateway. Both ends
retain the matching route-based VPN settings and existing credential. The
separate Usenet tunnel retained its old local address, was disabled, and had an
ESP AES-128 setting that mismatched the cloud's AES-256 requirement. It now uses
WAN1's current address, AES-256 for both IKE/ESP, and the existing IKEv2,
SHA1-HMAC, DH14/PFS and policy-based LAN-only selectors. Both tunnels show
**Established**. The resumed authorized follow-up then changed the cloud tunnel
to matching SHA-256 IKE/ESP on both peers and verified actual reconnection and
CHILD-SA rekey/PFS14. See the [Usenet VPN recovery record](../../usenet-infra/docs/lan-ui.md)
for the cloud firewall/identity repair and data-path checks.

### Ordered hardware inventory — 2026-10-16

| Item | Recorded status |
| --- | --- |
| Product | Cloud Gateway Max NS (US Version) |
| Model | `UCG-Max-NS` — Cloud Gateway with built-in UniFi Network controller; not the independent `UXG-Max` |
| Purchase | Ordered by Ryan on 2026-10-16; purchase price and order identifiers not recorded |
| Arrival | Received and powered on **2026-10-22**, confirmed by Ryan |
| Installation | Routing and Network controller cutover completed **2026-10-22**; basic checks passed as recorded above |
| Role | Replaces the USG 3P as router/gateway and this site's Cloud Key Network management |
| Storage | NS / no storage model; no NVR-storage purchase or Protect migration selected |
| Retained network hardware | US 24 PoE 250W switch, U7 Pro XG, and U6+ |
| Old hardware | USG and Cloud Key retired from active service; keep disconnected configurations available for rollback |

The completed gateway cutover does not choose between native UniFi DNS/ad
blocking and the existing dual-AdGuard design. Defer those changes until the
remaining baseline checks and the DNS decision are complete. The goals remain
reliable `name.home.arpa` resolution for LAN clients and ad blocking, preferably
through Ubiquiti-supported features.

### Original migration plan and remaining acceptance checks

The plan below was recorded before arrival. The dated cutover record above
identifies completed work; do not repeat a restore merely to follow this plan.

1. **Refresh the baseline and recovery material.** Confirm delivery/model and
   inventory the new unit. Re-read current Ubiquiti migration guidance and release
   compatibility. Export fresh off-device Cloud Key System Config and Network
   backups through supported interfaces; verify the restore path on the target
   software. Keep credentials and backups private. Check for other sites,
   Protect/other applications, and recovery access before deciding the Cloud Key's
   final role. Inventory any active legacy `config.gateway.json` customizations;
   do not assume a backup translates them to the new gateway.
2. **Prepare a bounded cutover.** Agree the maintenance window and rollback
   conditions. Capture WAN/DHCP, reservations, SSIDs, VLANs, firewall rules, VPN,
   DNS/filtering, dynamic DNS, and port dependencies as they actually exist then.
   Preserve `192.168.1.1` as the intended LAN gateway and the existing infrastructure
   reservations. Keep the replacement isolated from the production LAN during
   preparation so it cannot compete with the USG's gateway address or DHCP service.
3. **Migrate routing and Network management first.** Use the supported
   backup/restore workflow appropriate to the installed versions. Move the switch
   and AP management to the UCG-Max's controller and prevent the old Network
   application from competing for those devices. Preserve existing network
   behavior; defer new DNS, filtering, Wi-Fi tuning, segmentation, and VPN-policy
   changes until the migrated baseline works. Retain the old hardware and backups
   without factory-resetting them during the rollback window.
4. **Verify household operation.** Check a fresh wired and wireless DHCP lease,
   internet access, reservations, management/adoption, Home Assistant, NAS/wiki,
   printers, Sonos/AirPlay/Apple TV discovery, and the existing site-to-site VPN.
   Verify both the allowed print-API path and the denied Internet/other-LAN paths
   on `sintheta-printer`; it already has outstanding client acceptance tests.
   Save an accepted post-migration backup and update topology/access documentation.
5. **Choose and validate DNS/ad blocking separately.** Review native UniFi local
   records and ad blocking against retaining AdGuard on `192.168.1.163` and
   `192.168.1.66`. Establish one owner for `home.arpa` records, preserve
   `wiki.home.arpa` and local negative answers, add agreed device names, and test
   actual laptop/phone DNS paths, encrypted-DNS overrides, UDP/TCP, and applicable
   resolver failover. A DHCP search suffix alone does not create chosen device
   records. Handle gateway DNS interception explicitly if using AdGuard; do not
   silently disable filtering or advertise public DNS as a private-zone fallback.

Rollback must cover both gateway cabling/configuration and device management,
not just reconnecting the USG. Record the recovery procedure before
cutover, including how the switch/APs return to the old controller if needed.
Do not retire the Cloud Key, remove the AdGuard instances, or discard backups
merely because the new gateway initially comes online.

References: [Ubiquiti backups and migration](https://help.ui.com/hc/en-us/articles/360008976393-Backups-and-Migration-in-UniFi),
[ordered product](https://store.ui.com/us/en/products/ucg-max-ns), and
[household DNS status and rollback](home-dns.md).

## Routed Networks and Services

| Name | Purpose | Addressing | Internet | Discovery and isolation | Audit note |
| --- | --- | --- | --- | --- | --- |
| `Default` | Trusted LAN | Untagged, `192.168.1.0/24`; DHCP `.20`-`.254` | Allowed | mDNS on; IGMP snooping off; UPnP allowed | Most infrastructure, media, and IoT clients still share this Layer-2 segment |
| `sintheta-printer` | Restricted print clients | VLAN 3, `192.168.6.0/24`; DHCP `.6`-`.254` | Disabled | Network and Wi-Fi client isolation on; mDNS on; IGMP snooping off | Firewall permits only Home Assistant TCP/8099 plus gateway DHCP and mDNS |

The global inter-network security posture is `ALLOW_ALL`. The five `sintheta-printer` rules are the only custom firewall rules. The `sintheta-iot` SSID uses `Default`; it is not a routed security boundary.

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

The original five mappings had `use_fixedip:true` in controller state on 2026-08-31. The Brother and LED Grid Wall reservations were created that day at their already-active addresses; the other three were verified as existing reservations. Prusa Alpha and Nest I think received reservations on 2026-10-22 after both appeared at `.118`; the supported UI confirmed both saved mappings. Fan controllers are deliberately outside this infrastructure reservation set and were not changed.

Current [UniFi DNS documentation](https://help.ui.com/hc/en-us/articles/15179064940439-UniFi-DNS-Records-and-Local-Hostnames) supports a per-client **Local DNS Record** or a gateway DNS host record on capable gateways. The August audit found neither control in this legacy USG site's supported Network UI, and the original five client records above had no `local_dns_record` value. Dedicated AdGuard resolvers now serve `wiki.home.arpa`, but the October 16 client check still used gateway DNS and received `NXDOMAIN`; see [DNS operations](home-dns.md). Continue using reserved numeric addresses where ordinary DNS is required until client cutover is verified. The post-migration DNS review will revisit local records under `home.arpa`; do not overload `.local`, which is reserved for mDNS.

### WAN, VPN, and exposure baseline

- `FiOS` is the only configured Internet connection and uses WAN1 with DHCP. WAN2 is unconfigured, so there is no automatic Internet failover.
- Smart Queues are disabled on `FiOS`. IPv6 protocol selection is disabled even though a legacy `ipv6_enabled` field remains true; treat IPv6 as not configured until verified from a client and gateway firewall.
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

Controller state and both APs' generated configurations were verified in August.
On October 22 this Mac joined the SSID, received a fresh printer-network lease,
resolved `homeassistant.local`, reached HA TCP/8099 and confirmed the tested
Internet, other LAN/gateway and cloud-private ports blocked. It returned to
`sintheta` afterward. A second associated peer and an actual print job remain
untested; see the [acceptance record](unifi-post-migration.md).

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

The Brother printer was online at `192.168.1.192` on `sintheta` through the U7's 2.4 GHz radio when its fixed-IP reservation was created and verified on 2026-08-31. The printer add-on is configured for that address. Keep the reservation if moving the printer to `sintheta-iot`, and do not join the Brother printer itself to `sintheta-printer`: that SSID is for untrusted print-request clients and intentionally cannot accept Home Assistant's TCP/9100 connection to the printer.

## Switch Baseline

`Switch Server Closet` is the only adopted switch. The August 31 baseline used classic STP with priority `4096`; RSTP, global automatic edge detection, jumbo frames, flow control, DHCP snooping, and 802.1X port control were disabled. Port 23 is the gateway uplink, and ports 10 and 16 power the two APs. Port 21 formerly powered the Cloud Key, which was disconnected during the October 22 cutover. Recheck effective switch settings after migration. Use Ubiquiti's [STP hierarchy guidance](https://help.ui.com/hc/en-us/articles/24292724428311-Understand-and-Mitigate-Network-Loops-STP) when deciding root priority, RSTP, edge, and BPDU settings.

The live 100 Mb/s links on ports 12, 15, and 22 mapped to Sonos, Philips Hue, and Sonos records respectively. These devices commonly have fast-Ethernet interfaces, so link rate alone is not evidence of a cabling fault. Investigate only if the device's own specification promises gigabit or if errors, drops, or throughput symptoms appear. Port 24 is down and no pending device remains.

## Audit Recommendations and Decision Register

The recommendation is not permission to change live state. Answer the question in the last column, record the intended value and rollback, then use the [Safe Change Workflow](#safe-change-workflow).

| Priority | Setting or scope | Observed value | Recommended next step | Question that determines the target value |
| --- | --- | --- | --- | --- |
| High | `sintheta-printer` validation | Saved and provisioned; no client test | Join an expendable client and prove DHCP, `homeassistant.local`, TCP/8099, blocked Internet, blocked other LAN/gateway ports, and client isolation | Which device types will join, and do any require NTP or other traffic beyond the print API? |
| High | Gateway lifecycle | UCG-Max-NS routing and Network management active 2026-10-22; switch and both APs reported online; basic service checks passed | Complete [remaining acceptance checks](#cloud-gateway-max-migration), save a Max System Config backup, and retain old hardware | What other Cloud Key applications must remain available, and have DHCP, isolation, discovery, printing, and VPN checks passed? |
| High | UPnP/NAT-PMP | Enabled on `Default`; live dynamic mappings exist | Inventory mappings and owners, then disable UPnP if each need can be removed or replaced with VPN/manual narrowly scoped access | Are Plex remote access, gaming, peer-to-peer apps, or Home Assistant integrations relying on a mapping? |
| High | Site-to-site VPN crypto and scope | August 31 Lehigh baseline: IKEv1/AES-128/SHA-1 and all local subnets. October 22: both tunnels Established; Usenet verified IKEv2/AES-256/SHA1-HMAC with LAN-only selectors | Recheck Lehigh's effective proposals and selectors; coordinate remaining modernization toward IKEv2, AES-256 and SHA-256 with only required local networks | What does each peer support, and should Lehigh reach any future IoT VLAN? |
| Medium | IoT segmentation | `sintheta-iot` shares trusted `Default` | Inventory dependencies and migrate small device groups to a real restricted VLAN with explicit Home Assistant and discovery exceptions | Which Sonos, AirPlay, Chromecast, printer, cloud, and phone-to-device flows must cross the boundary? |
| Medium | mDNS proxy | All services across all eligible networks | Move toward custom networks/services only after a test proves raw `homeassistant.local` A-record resolution still works for print clients | Which cross-VLAN services are actually required, and can UniFi's custom service model preserve hostname-only lookup? |
| Medium | Backups | 14 daily controller-local Network backups; cloud backup off | Maintain an encrypted off-device System Config backup and test that the intended replacement hardware can restore it | Is UI cloud backup acceptable, or where will offline exports be stored and how often will restoration be tested? |
| Medium | Management access and logs | August 31 baseline: one recorded owner, device password auth enabled, NetFlow/syslog off; Max access policy not yet rechecked | Verify MFA/recovery, a break-glass path and dedicated Max SSH access before considering key-only device SSH; choose a log destination if forensic history matters | Who must recover the site if the owner account or Max fails, and what event retention/privacy budget is appropriate? |
| Medium | Hidden/test WLANs | Element Adoption and `sintheta-6-test` enabled | Disable each only when its owner confirms it is unused; verify AP generated state afterward | Are any AutoLink/Element devices still present, and what experiment/expiry date owns `sintheta-6-test`? |
| Medium | STP | Classic STP, sole switch priority 4096 | Document the intended root and consider RSTP during a maintenance window; set edge/BPDU behavior only after mapping downstream switches | Is `Switch Server Closet` the permanent root, and which ports lead to switches or bridges rather than endpoints? |
| High | DNS/filtering | October 16: both AdGuard resolvers passed direct checks; the Mac received `NXDOMAIN` for `wiki.home.arpa`. October 22: public DNS through the new gateway passed; local-name cutover remains unverified | Finish migrated baseline checks before selecting DNS ownership and testing client cutover | Use native UCG-Max DNS/ad blocking or retain dual AdGuard? Which client names should be assigned under `home.arpa`? |
| Low | Smart Queues and IPv6 | Smart Queues off; IPv6 protocol disabled | Leave off unless a measured latency or IPv6 requirement justifies an end-to-end design and gateway-capacity test | What are sustained WAN rates, bufferbloat under load, ISP IPv6 support, and VPN/firewall requirements? |

### API and MCP diagnostics

The selected integration is [enuno/unifi-mcp-server](https://github.com/enuno/unifi-mcp-server),
pinned to `0.6.1`, with the existing local stdio launcher, read-only `network`
profile and settings-provided credential (`UBIQUITI_API_KEY`). The resumed Mac
session exposes 26 native tools without controller mutations/debug and has
successfully read Max/site `default`, current clients, networks/Wi-Fi, WAN,
DNS filters and all seven infrastructure reservations. Ordinary sandbox TCP
remains denied, while the same TLS check succeeds through approved
`require_escalated` execution. No credential or launcher change was needed.
See the [launcher runbook](../../network-infra/unifi-mcp/README.md) and
[post-migration work](unifi-post-migration.md).

Use the Max's version-specific **Integrations** documentation where an API
covers the desired read. Keep direct AP/switch effective-state checks for
provisioning and transient failures. No active workflow requires reconnecting
the Cloud Key or writing controller MongoDB.

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
- Client reservations: **Network > Client Devices > select client > Settings > IP Settings > Fixed IP Address**
- Per-AP radios and meshing: **Network > UniFi Devices > select AP > Settings gear > Radios**
- Controller SSH: **Control Plane > Console > SSH**
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

For a native DNS pilot, run:

```sh
just dns-check --resolver 192.168.1.1
```

This checks exact response semantics over UDP/TCP. Local handling without
upstream leakage and a fresh client's actual resolver path require the
additional [DNS acceptance checks](unifi-post-migration.md#native-dns-pilot).

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

### 2026-08-31: retired orphan network and unused WAN2

- Confirmed in the supported UI that `esp` was a routed VLAN 2 network, not a Wi-Fi SSID, and had no DHCP leases or associated WLAN.
- Confirmed `Internet 2` was an inactive failover-only WAN2 definition with no IPv4 or IPv6 address and 0% uptime.
- Removed `Internet 2`, then removed `esp`, through **Network > Settings > Overview > Manage**.
- Verified the post-change UI lists only `FiOS` on WAN1 and only `Default` plus `sintheta-printer` as routed networks; all four intended client WLANs remain present.
- WAN2 is now unconfigured and provides no failover. Roll back only by deliberately recreating the required network or secondary Internet connection from recorded addressing/provider requirements or by restoring an appropriate controller backup.

### 2026-08-31: infrastructure fixed-IP reservations

- Verified the existing Home Assistant (`192.168.1.163`), QNAP (`192.168.1.66`), and Canon printer (`192.168.1.150`) reservations.
- Created fixed-IP reservations for the online Brother QL-810W at `192.168.1.192` and LED Grid Wall at `192.168.1.98`, preserving their active addresses.
- Re-read controller state and confirmed `use_fixedip:true` with the expected MAC/address mapping for all five infrastructure clients.
- Deliberately excluded all fan controllers from this reservation change.
- Confirmed the current legacy-USG UI does not offer per-client or policy local-DNS records. Numeric reserved addresses remain the supported stable endpoints; `.local` remains mDNS-only.

### 2026-10-22: duplicate address after gateway migration

- UniFi Network `10.6.106` reported Prusa Alpha and Nest I think sharing `192.168.1.118` at 13:40:41 local time. Neither had a fixed-IP reservation; the Max's DHCP table showed `.118` leased to the Nest and no current lease for the printer. This supports a migration-related lease overlap, without proving whether the printer retained an old lease or used a device-side static address.
- Confirmed `.19` had no matching client-history entry, DHCP allocation, documented assignment, or ARP response. Reserved it for the Nest in the supported UI, then reconnected only that client's Wi-Fi. The Nest returned online through AP Bedroom at `.19`; all three local ping probes succeeded and ARP matched `64:16:66:97:50:0a`.
- Reserved `.118` for Prusa Alpha after the Nest moved. Reopened its settings to verify the saved reservation. UniFi's gateway-to-printer ping test succeeded with 0.3 ms minimum, 0.7 ms average, and 1.3 ms maximum during the verification window. No printer, switch, AP, or gateway restart was needed.
- Before/after evidence belongs in ignored `build/unifi-ip-conflict-20261022/`. If a reservation causes a regression, remove only that reservation after recording the current owners and choosing a non-conflicting lease plan; do not blindly return the Nest to `.118`.

### Next controlled iterations

1. Complete the `sintheta-printer` end-to-end client validation in the decision register.
2. Inventory live UPnP mappings and decide whether each one is still required before disabling UPnP.
3. Complete the authorized Site Magic and cloud IPsec modernization in the [post-migration checklist](unifi-post-migration.md).
4. Resolve the purpose of Element Adoption and `sintheta-6-test` before retaining or removing them.
5. Move documented IoT clients in small groups only after defining a real segmentation policy and required flows.
6. Compare 2.4 GHz utilization and retries after migration.
7. Confirm primary-bath coverage remains acceptable before reducing Bedroom AP power further or removing it.
8. When legacy clients are off `sintheta`, test Fast Roaming there with a recorded start time and rollback condition.
9. If Apple TV Remote problems recur, capture a failure before changing 6 GHz width or reprovisioning the U7.
