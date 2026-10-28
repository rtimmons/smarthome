# Cloud Gateway Max follow-up

The October 22, 2026 migration and authorized follow-up are accepted with the
limits below. The Max at `192.168.1.1` runs Network `10.6.106` and UniFi OS
`5.1.33`. The USG and Cloud Key are disconnected; preserve their configurations
and every private backup. See [topology](unifi-network-setup.md).

## Current progress

| Work | Accepted state | Ongoing requirement |
| --- | --- | --- |
| DNS/ad blocking | Two native `home.arpa` forwarders; either-backend failover, both-down containment and recovery passed | Keep both AdGuards running and native wiki A paused |
| Site Magic | `Newark-Lehigh`, Connected (2), only the two Default LANs shared | Keep old manual IPsec definitions paused for rollback |
| Cloud VPN | Paired SHA-256 deployment, reconnect/PFS rekey and LAN sign-ins passed | Coordinate both peers and WAN firewall restrictions |
| Firewall | Zones active; eight custom policies active, three redundant HA allow copies paused | Preserve DHCP/mDNS and every drop policy |
| IDS | Default only, Notify; printer excluded | Blocking mode needs a separate evaluation |
| MCP/API | 26 native read-only tools and live Max/site reads passed | Preserve launcher controls; rotate key before November 22 |
| SSH | Max, both APs and switch pass existing-key login with verified host pins | Retest after OS updates or restoration |
| Recovery | Fresh Max/Lehigh System and cloud VPN exports encrypted and decryption-verified | Retain pre-change copies and native downloads |

## Acceptance and backup

October 22 acceptance covered:

- Fresh Mac Wi-Fi leases and an observed post-cutover HA Ethernet DHCP lease;
  gateway/DNS `192.168.1.1` and all seven infrastructure reservations matched.
- An associated `sintheta-printer` Mac reached HA TCP/8099 and fresh
  `homeassistant.local` mDNS. Unrelated LAN/gateway, Internet, cloud and Lehigh
  paths stayed blocked. Ryan confirmed the single `NETWORK CHECK` label printed.
- Same-AP Mac/phone peer isolation passed with the awake phone's permitted HA
  endpoint working. Turn cellular data off for an iPhone's local-only control,
  then restore it. The peer test preceded zone conversion; AP isolation was
  unchanged. Post-conversion routed checks passed separately.
- Fresh wire replies found five Companion, nine AirPlay and thirteen Sonos
  instances; all 27 advertised TCP endpoints opened. Ryan confirmed Apple TV
  Remote, AirPlay, Sonos controls and cloud-application LAN sign-ins working.
- Native packet captures corroborated printer allow/deny paths and mDNS.
  These checks do not claim every client, codec or playback-duration combination.

The latest full Max System export after SSH setup was **167,888 bytes**;
post-mesh Lehigh was **185,824 bytes**. Both were encrypted off-device and
authenticated-decryption verified. Preserve all earlier archives,
particularly the **99,632-byte pre-zone Network-only export**. Readback does not
prove a replacement-hardware restore or restoration of console authorized keys.

## Native DNS pilot

Trusted DHCP advertises gateway DNS `192.168.1.1`. Two native **Forward Domain**
policies send `home.arpa` to HA AdGuard `192.168.1.163` and NAS AdGuard
`192.168.1.66`. AdGuard owns the local records and negative answers. The native
`wiki.home.arpa` A policy is saved but paused because enabling it changed the
zone apex from required `NXDOMAIN` to empty `NOERROR`.

Exact UDP/TCP answers, ordinary wiki-by-name HTTP, ad blocking, each backend
outage, both-down containment and automatic recovery passed. WAN capture showed
no private-zone DNS during both-down testing, with a working public DNS control.
Both AdGuards stayed running and their exact access lists were restored.
Default's existing native Ad Block remains on; categories and Safe Search are off.

Use [DNS operations](home-dns.md) for the contract, repeatable drill and recovery.
Rollback of the second forwarder pauses only the NAS-targeting policy; retain
HA forwarding, the paused native A and both resolvers. Do not retire AdGuard or
add public fallback DNS for the private zone.

## Lehigh Site Magic mesh

Site Manager **Settings > SD-WAN > Mesh > Newark-Lehigh** reports Connected (2).
Advertisements are exactly Newark `192.168.1.0/24` and Lehigh `192.168.8.0/24`.
Printer `192.168.6.0/24`, cloud `10.77.0.0/30`, Teleport and WAN are excluded.
Both superseded `300Newarkto2117Lehigh` manual IPsec definitions are paused.

Ryan explicitly accepted UniFi's success status without a Lehigh test host.
Trusted-LAN access to Lehigh's gateway passed; printer access stayed blocked.
No bidirectional LAN-host application test is claimed.

For rollback, open **Configure**, uncheck both Default LAN advertisements and
apply. Verify routes have withdrawn before resuming the preserved manual
definitions on both consoles; never leave competing mesh/manual routes active.
The zero-network form was previewed, but withdrawal was not exercised. If the
product requires irreversible mesh removal, obtain confirmation at that time.
Verify the manual tunnel Established and Lehigh gateway access afterward.

## Cloud VPN and WAN recovery

Both peers use IKEv2 AES-256/HMAC-SHA256/PRF-SHA256, ESP AES-256/HMAC-SHA256 and
MODP2048/PFS14. Exact selectors remain `192.168.1.0/24` ↔ `10.77.0.0/30`.
Actual SAs, reconnect, CHILD-SA rekey, authentication gates, denied backend
ports and owner-confirmed LAN sign-ins passed. The default and private inventory
select `cloud_vpn_crypto_profile: sha256`. See [cloud VPN operation](../../usenet-infra/docs/lan-ui.md).

After a WAN change:

1. Read WAN1's actual IPv4 in the Max. Run
   `just usenet vpn-peer-check <verified-WAN-IPv4> --local-only`, then the full
   command with `--require-sha256`. It checks private inputs, Terraform, Hetzner,
   fresh dedicated cloud SSH, UFW, installed selectors and negotiated SAs.
2. If SSH is blocked, use the existing Hetzner console to restore only the new
   WAN `/32` for TCP/22. Preserve other authorized admin sources. DDNS does not
   update Hetzner or UFW source restrictions.
3. Capture an encrypted VPN backup and prior firewall/configuration. Reconcile
   `cloud_vpn_peer_ip`, `cloud_ssh_allowed_cidrs`, Terraform
   `vpn_peer_ipv4`/`admin_ssh_cidrs` and Max peer identities. Preview Terraform;
   apply only expected firewall changes, then the existing scoped cloud-LAN
   playbook. Remove obsolete managed `/32` rules only after fresh SSH succeeds.
4. Repeat preflight, LAN authentication/denied-backend checks, reconnect and
   explicit CHILD-SA rekey; capture and verify a fresh encrypted VPN backup.

This is a repeatable procedure, not automatic WAN repair. Preflight alone does
not verify the Max UI or LAN data path. For coordinated crypto rollback, restore
both Max hashes to SHA1 and deploy the explicit cloud `legacy_sha1` profile
together, then verify negotiation and paths. Never change only one peer or
install the historical USG `config.gateway.json` on the Max. Do not print
`ip xfrm state` or credential files.

## Firewall and IDS/IPS

Default and printer remain in **Internal**, with network-specific printer
restrictions. Lehigh is in VPN; cloud IPsec retains its generated handling.
The IoT SSID shares Default. A restored inactive Internet 2 record does not
provide WAN failover.

Before conversion, read-only effective rule counters and the associated-peer
test established the baseline. After conversion, policy hits and associated
client checks passed. Three unreachable HA allow copies targeting Hotspot,
External and VPN were paused because their fixed destination is connected to
Internal and they had no hits. Eight custom policies remain active; DHCP,
mDNS and every drop were preserved. Resume only those three copies to reverse
this cleanup. Further removal needs fresh route/counter evidence.

Zone rollback uses **Management > General > Restore from Backup**, selecting
the preserved pre-zone Network-only export on this Max/version. **Withdraw mesh
LAN advertisements first** if the backup enables the superseded manual peer;
coordinate both consoles. Recheck DNS, VPNs and every printer path after restore.
Do not substitute a Cloud Key backup or CLI ruleset rewrite.

IDS remains **Default / Notify**, excluding printer. Gateway speed samples were
942/951 Mbps before and 929/923 afterward; the later Mac Wi-Fi sample was about
622/80 Mbps, without a comparable pre-IDS client baseline. These do not establish
an IDS performance effect. The observed monthly security view had zero detections.
Rollback is **CyberSecure > Threat Management > Intrusion Prevention > Off >
Apply Changes**, preserving DNS/ad blocking. Blocking IPS remains unevaluated.

## SSH access completion — October 22

Ryan enabled Max SSH and installed the existing owner key, restricted to
`192.168.1.0/24`. Fresh strict-host-checking logins passed to the Max, both APs
and switch. Printer-network SSH to all four devices and Max external IPv4 WAN
SSH were blocked, with working positive controls. DNS and wiki access still
passed. [SSH operations](unifi-ssh-access.md) owns fingerprints, commands,
permissions, rollback and update/restore checks. MCP writes now require explicit approval under `network-infra/unifi-mcp/POLICY.md`.

<a id="remaining-acceptance"></a>

## Maintenance and evidence limits

Required migration checks are accepted under the criteria above. Keep both
AdGuards, paused rollback policies and encrypted backups. Retest access after
updates/restores; rotate the existing MCP key before **November 22, 2026**.
Site Magic host testing was waived; blocking IPS, a matched client throughput
benchmark and replacement-hardware recovery were not performed. For future
discovery failures, use the [Bonjour capture workflow](unifi-apple-tv-remote.md)
before changing radio or Sonos settings.

The prepared infrastructure changes passed 549 unit tests, syntax/YAML/ShellCheck,
26 wiki tests, six DNS tests and five launcher tests. The separate current-source/
index scan passes; the full history scan retains the two documented
[historical RSA findings](../../usenet-infra/docs/security-findings.md).
No history rewrite or scan exception was added.

Private evidence remains under ignored `build/unifi-followup-20261022/`,
`build/unifi-remaining-20261022/`, `build/unifi-dns-failover-20261022/` and
`build/unifi-ssh-20261022/`. Native downloads and encrypted archives are retained;
session chronology is also recoverable from Git history.
