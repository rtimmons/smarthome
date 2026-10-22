# Cloud Gateway Max follow-up

Ryan authorized the post-migration improvements on October 22, 2026. The Max is
the active router/controller; the USG and Cloud Key are retired from active
service. Preserve their disconnected configurations as rollback material.
The [migration record](unifi-network-setup.md#cloud-gateway-max-migration)
contains the accepted cutover checks. This page tracks the remaining work;
source preparation is distinct from live deployment.

## Current progress

| Work | Prepared | Live acceptance still required |
| --- | --- | --- |
| Baseline and backup | Max/Lehigh System exports and cloud VPN archives encrypted and decryption-verified; leases, reservations, restricted print, live discovery and owner-confirmed application controls accepted | Retain recovery copies |
| Native DNS/ad blocking | Forwarding-only hybrid passes exact UDP/TCP contract and local-rewrite evidence; fresh Mac lease uses gateway DNS; second trusted host's A/local-negative checks pass; native wiki A paused | Forwarder-outage acceptance; retain both AdGuards |
| Lehigh Site Magic | LAN-only mesh created; UniFi reports both gateways Connected; both manual IPsec definitions paused for rollback | Owner accepted UniFi status without a Lehigh host; retain rollback definitions/backups |
| Cloud VPN SHA-256 | Paired deployment, actual SAs, reconnect, PFS14 rekey, encrypted backup and owner-confirmed LAN application sign-ins accepted | Preserve coordinated rollback |
| WAN recovery | Private inputs, provider firewall, fresh cloud SSH, UFW and negotiated SA preflight pass | Repeat after a WAN change |
| UniFi MCP | Native 0.6.1 tools and live Max/site reads accepted; read-only controls preserved | Rotate existing key before November 22 expiry |
| Firewall and IDS/IPS | Zones converted after counter/peer acceptance; eight custom policies active and three unreachable allow copies paused; Default/Notify retained | Preserve rollback copies and review future policy hits before further cleanup |
| Access/docs | Native API works; Max SSH is off and TCP/22 refuses connections | Console SSH requires a separate reviewed access change |

The initial implementation session could not open terminal network connections
(`Operation not permitted`), and Firefox repeatedly closed in settings.
Ryan requested Safari; its authenticated session successfully opened the native
settings. Network is `10.6.106`, UniFi OS `5.1.33`. The Max's fresh full export
(all applications and settings, 156,272 bytes) was encrypted off-device with
the existing recovery identity and authenticated decryption matched its hash.
Private archive and verification receipts are ignored. Automatic backups are
enabled; console SSH is off. No new SSH access was enabled.
Lehigh's fresh full System export (185,360 bytes) was separately encrypted and
authenticated-decryption checked before any proposed mesh cutover.
A second Max export after the DNS/Notify-only changes (157,184 bytes) was also
encrypted and decryption-verified. Preserve both pre-change and post-change
archives. Plain native downloads remain in the owner's Downloads directory;
they were not modified or removed by the executor.

### Resumed Mac acceptance — October 22

This session runs on Darwin on the owner's Mac. Native MCP exposes 26 tools
with no controller mutation/debug entries. It read the local Max, site
`default`, 38 active clients, four intended WLANs, network/WAN definitions,
DNS-filter settings and all seven expected infrastructure reservations.
The API also lists a restored inactive `Internet 2` definition; the supported
overview shows only FiOS/WAN1 active. Do not remove it solely from that listing.

Ordinary sandbox TCP/443 still returns `PermissionError`, errno 1. The same
TCP/TLS probe succeeds with `require_escalated`, and the subsequent DNS,
dedicated SSH and wiki operations use that approved path. No credential setup,
GUI-terminal bypass, MCP mutation or unrestricted executor configuration was needed.

The Mac joined `sintheta-printer` and received a fresh lease from `192.168.6.1`.
`homeassistant.local` resolved; HA TCP/8099 opened. Probes bound to that client
address confirmed HA TCP/8123, NAS TCP/80, gateway TCP/443 and TCP/53, public
TCP/443 and cloud-private TCP/15055 blocked. The Mac then
returned to `sintheta` with gateway/DNS `192.168.1.1`; its newly added printer
Wi-Fi preference was removed. A later repeat sent exactly one idempotent
`NETWORK CHECK` label at 17:03 Eastern; the service returned HTTP 200, `sent`
and print count one, and Ryan confirmed the physical label printed correctly.
The Mac had no wired adapter. Home Assistant's existing wired connection
provided a separate acceptance path: NetworkManager recorded a new `enp4s0`
lease at 14:37:27 Eastern after Max cutover. The current connected Ethernet
interface is automatic DHCP at `192.168.1.163/24`, with gateway and DNS
`192.168.1.1`. This was an observed renewal; no host or network restart was
performed for the check.

Ryan then connected an awake phone to `sintheta-printer`. Its first numeric
HTTP check failed while cellular data was enabled; with cellular data off,
Ryan confirmed the permitted HA TCP/8099 health endpoint loaded. While both
clients were on the same AP, the Mac could still reach that endpoint but
could not resolve the phone's direct neighbor address, ping it or open the
two tested TCP ports. This accepts peer isolation for the tested pair, with
the phone's working Wi-Fi endpoint as the active-client control. Closed phone
TCP ports alone were not treated as proof. The Mac was restored automatically
and its temporary printer Wi-Fi preference removed after each test. Restore
the phone's cellular setting after testing.

Bonjour browsing found five Companion, nine AirPlay and thirteen Sonos
instances. A subsequent ordinary UDP socket sent fresh multicast PTR questions
with distinct transaction IDs and retained matching wire replies from UDP/5353:
five Companion, nine AirPlay and thirteen Sonos instances. All 27 advertised
TCP endpoints opened. These fresh replies establish live client discovery,
independently of the system Bonjour cache. They do not show AP bridge ingress
and egress or establish interactive Remote/playback acceptance. Private evidence
is under ignored `build/unifi-followup-20261022/` and
`build/unifi-remaining-20261022/`.

The Max's native **UniFi Devices > Max > Packet Capture** also completed a
60-second capture scoped to `sintheta-printer`. Its downloaded tar archive
contained one PCAP with 1,496 packets. Offline inspection found both directions
of the allowed HA TCP/8099 exchange, the matching fresh `homeassistant.local`
mDNS question/answer, blocked-path requests with no replies, and five phone
neighbor requests with no replies. The read-only health URL returned HTTP 200.
The Mac again restored trusted Wi-Fi automatically. This is routed-interface
packet evidence, not an AP bridge trace or per-rule hit-counter baseline.
Capture archives, packet bytes and raw summaries remain private and ignored.

## Acceptance and backup

Check each path separately and retain dated, private evidence:

- A fresh wired and wireless DHCP lease, intended gateway/DNS and existing
  infrastructure reservations. Renew one test client at a time.
- Home Assistant, NAS/wiki and the label printer endpoint, without changing
  reservations or initiating an unsolicited print.
- A client actually associated with `sintheta-printer`: DHCP, hostname discovery
  and HA TCP/8099 must work; Internet, unrelated LAN/gateway ports and peer-client
  access must remain blocked. A trusted-LAN probe does not establish this.
- Live Sonos, AirPlay and Apple TV Companion advertisements and reachability.
  Preserve playback, groups and current radio settings during the checks.
- Native **System Config** export from the Max, stored encrypted off-device
  and authenticated-decryption checked. Do not treat a Cloud Key export as a
  current Max backup or repeat the failed full-console restore.

## Native DNS pilot

On October 22, Safari saved these policies through **Policy Engine > Policy
Table > DNS Records**:

| Domain | Type | Value |
| --- | --- | --- |
| `wiki.home.arpa` | Host (A), automatic TTL — **now paused** | `192.168.1.66` |
| `home.arpa` | Forward Domain | `192.168.1.163` |

Safari then opened `http://wiki.home.arpa/` and displayed the field guide.
The forwarding form accepts one DNS-server address, so this hybrid pilot
depends on HA AdGuard for local-zone negative answers; it is not a native-only
or dual-forwarder acceptance. Both AdGuards and their repository policy remain
intact. No DHCP fields changed.

The existing **CyberSecure > Content Filter > Default** policy already has
Ad Block on, filtering Off, all three Safe Search options off, and an Always
schedule. It was inspected and preserved, not newly enabled.

Keep both AdGuards running during the pilot. Use the existing local-zone policy
as the acceptance contract: exact wiki A, empty AAAA, unknown local names and
unknown subdomains rejected locally, plus public resolution over UDP and TCP.

Run `just dns-check --resolver 192.168.1.1`, then verify a newly leased client's
actual DNS path. A negative response alone does not prove it stayed local;
check gateway forwarding configuration and synthetic query/packet evidence.
The zone apex's current policy is NXDOMAIN. Review a native SOA alternative
explicitly rather than weakening tests to accept an unexplained response.

Verify the existing UniFi ad blocking from a test client. Keep content categories
Off and Safe Search disabled, preserving the existing policy. Native filtering
redirects DNS; configure local records/domain forwarding before enabling it.
Verify ordinary browsing, local names and a known ad-domain block. If native
zone behavior cannot meet the contract, keep AdGuard ownership and use supported
domain forwarding where appropriate. See [DNS operations](home-dns.md).

The resumed gateway check initially failed: the apex SOA query returned empty
`NOERROR` instead of the policy's `NXDOMAIN`. Pausing only the duplicate native
wiki A policy in the supported UI corrected this mismatch. With forwarding
retained, the unchanged full check passed over UDP and TCP. A new synthetic
unknown query through the gateway appeared in HA AdGuard as `RewriteRule` with
no upstream. Both AdGuards passed directly; `doubleclick.net` returned `0.0.0.0`
through the gateway over UDP/TCP. The returned fresh trusted Wi-Fi lease used
gateway DNS, and normal wiki-by-name HTTP returned 200.
A separate check over the dedicated Home Assistant SSH path queried the gateway
from that second trusted host: the wiki A answer was `192.168.1.66`, and both
the zone-apex SOA query and a fresh unknown local name returned `NXDOMAIN`.
This second-host check used its ordinary DNS client; the full UDP/TCP contract
remains the separately accepted repository check above.

Keep the native A policy paused for rollback. AdGuard owns local records;
the trusted-client gateway resolver forwards `home.arpa` to HA. This
single-forwarder hybrid has no accepted automatic local-zone failover. Both
AdGuards stay running; no DHCP settings changed and no test was weakened.
The reviewed policy and generated wiki reference describe this arrangement.
Recovery includes both AdGuard configurations and the Max's forwarding and
paused-policy System export.

After the accepted DNS and SHA-256 changes, a new full Max System export
(158,336 bytes) was encrypted off-device and authenticated-decryption verified.
All earlier Max, Lehigh and cloud VPN archives remain intact. The native
plaintext download was preserved in the owner's Downloads directory.

After acceptance, update `network-infra/dns/policy.json`, its generated wiki
reference and backup scope to describe the accepted owner, then stop only the
resolver services no longer in any client lease or upstream path. Preserve
configuration/backups. Rollback restores the captured Max policy and DHCP
settings with both AdGuards still available.

## Lehigh Site Magic mesh

The first native preview was closed without applying it. Later on October 22,
Ryan explicitly authorized proceeding without a Lehigh test host and accepting
UniFi's success status. The supported **SD-WAN > Mesh** workflow then created
`Newark-Lehigh` under the existing owning account. UniFi's Status filter reports
**Connected (2)** and both gateways show green, with exactly one Default LAN
advertised by each site. This is the owner-approved acceptance criterion;
bidirectional LAN-host application tests were not performed.

Use Site Manager **Settings > SD-WAN > Mesh** with the same owning UI account
for both gateways. Share only Newark `192.168.1.0/24` and Lehigh
`192.168.8.0/24`. Keep `192.168.6.0/24` and cloud `10.77.0.0/30` out of this
mesh. Site Magic is for the two UniFi gateways; the third-party cloud VPN
remains separate. The gateway handles WAN-address changes automatically.

Before creation, both native `300Newarkto2117Lehigh` manual IPsec definitions
were reviewed and **paused**, preserving their credentials and settings rather
than deleting them. Their route-based selectors were the opposite site's
Default /24; they used IKEv1/AES-128/SHA1, DH14/PFS. The Max configuration was
also captured privately; the encrypted full exports cover both consoles.
Pausing both peers first prevented active competing routes during the cutover.
The separate cloud IPsec definition was preserved.

After connection, Lehigh's gateway TCP/443 was reachable from the trusted Mac.
Gateway DNS and the separate cloud application path passed. A fresh associated
printer-client check passed all eight allow/deny expectations, including denied
Lehigh gateway access, while HA TCP/8099 health and a fresh HA mDNS wire reply
worked. The Mac returned to its trusted Wi-Fi afterward; no label was printed
again and no phone-peer retest is claimed.

Fresh full System exports from both consoles after the mesh cutover were
encrypted and authenticated-decryption verified: Max 167,632 bytes and Lehigh
185,824 bytes. All pre-change exports and their private receipts remain intact.

For rollback, open **SD-WAN > Newark-Lehigh > Configure**, uncheck both Default
LAN advertisements and apply, then verify their routes have withdrawn before
resuming the preserved manual definitions on both consoles. This zero-network
form was previewed with Apply enabled, then cancelled; withdrawal itself was
not exercised. Do not leave mesh routes active while resuming the old peer.
If the product instead requires irreversible mesh removal, obtain its required
confirmation at that time. Verify the manual tunnel Established and Lehigh
gateway access after rollback. Retain pre-change exports and native downloads.

## Cloud VPN and WAN recovery

The accepted checked-in default `sha256` selects IKEv2
AES-256/HMAC-SHA256/PRF-SHA256 and ESP
AES-256/HMAC-SHA256, with MODP2048/PFS and the existing exact selectors. Deploy
the Max's matching native settings and the cloud profile together. Persist
`cloud_vpn_crypto_profile: sha256` in the ignored inventory after acceptance;
do not deploy the stronger cloud proposal alone against an unchanged peer.

The resumed current-WAN preflight passed for private inputs, Terraform,
Hetzner ingress, fresh dedicated cloud SSH, UFW and installed peer/selectors.
After a fresh encrypted/decryption-verified rollback backup, Safari changed
only the Max's IKE/ESP hashes to SHA256 and the scoped cloud-LAN playbook
applied its matching profile. No media service restarted. Explicit tunnel
reconnection and CHILD-SA rekey verified the settled installed SA with AES-256,
HMAC-SHA256, PRF-SHA256, MODP2048/PFS14, exact LAN-only selectors and no SHA-1.
Immediate post-rekey output was transitional; settled verification passed.
The ignored inventory now explicitly retains `cloud_vpn_crypto_profile: sha256`.
The `--require-sha256` preflight and application health passed. A fresh encrypted
cloud VPN/proxy archive passed authenticated decryption.

Keep `legacy_sha1` only for coordinated rollback: restore both Max hashes to
SHA1 and deploy that explicit cloud profile together, then recheck negotiation
and paths. Preserve the pre-change encrypted archive; never change only one peer.

For a WAN change, use this workflow:

1. Read WAN1's actual IPv4 in the Max. Run
   `just usenet-vpn-peer-check <verified-WAN-IPv4> --local-only`, then the full
   command. It checks private inventory and Terraform inputs, the recorded
   Hetzner firewall, fresh dedicated cloud SSH, UFW, installed selectors and
   negotiated SAs. It performs no changes and never prints raw replies.
2. If new-WAN SSH is blocked, use the existing Hetzner console to restore only
   that WAN `/32` for TCP/22 before resuming. A DNS hostname does not update
   Hetzner or UFW restrictions. Preserve every other authorized admin source.
3. Capture the encrypted VPN backup and private prior firewall/configuration.
   Reconcile `cloud_vpn_peer_ip`, `cloud_ssh_allowed_cidrs`, Terraform
   `vpn_peer_ipv4`/`admin_ssh_cidrs` and the Max's native peer identities. Preview
   Terraform; apply only the expected cloud-firewall rule changes, then deploy
   the existing scoped cloud-LAN playbook. Remove obsolete managed `/32`
   restrictions only after a fresh connection from the new source succeeds.
4. Re-run the preflight, adding `--require-sha256` after crypto modernization.
   Separately test LAN application authentication gates, blocked backend ports,
   reconnect and explicit CHILD-SA rekey. Take and verify the new encrypted VPN
   backup. The preflight never claims to verify the Max UI or LAN data path.

Do not install the historical USG `config.gateway.json` on the Max. Retain its
tracked copy solely as historical rollback evidence until the old-hardware
rollback window closes. Never print `ip xfrm state` or raw credential files.

## Firewall and IDS/IPS

On October 22 the native page offered a detection-engine update. **Update now >
Proceed** returned “Intrusion Prevention update started”; the update-required
banner was subsequently absent. The free profile displayed 26,656 signatures.
The pilot was saved as **On**, selected network **Default** only, detection mode
**Notify**. Printer was removed from the pilot's selected-network field before
saving; no firewall rule or network isolation was changed. **Notify and Block**
was not selected. No subscription or client certificate was installed.

Before the pilot, the Max's own ISP test measured 942 Mbps down / 951 Mbps up;
the post-save test measured 929 / 923 Mbps. Dashboard reachability samples were
10/8/4 ms before and 14/4/4 ms afterward (Microsoft/Google/Cloudflare).
One pair of gateway-origin measurements cannot establish a performance change
or routed-client throughput. Reopening settings confirmed Default/Notify
persisted. Safari still opened the wiki by name and reached the private Seerr
login page at `10.77.0.1:15055/login`; this was not an authenticated application
test. Both VPNs remained Established in the native overview.
Complete client/application checks and review actual alerts before considering
blocking mode. Rollback of this pilot is **CyberSecure > Threat Management >
Intrusion Prevention > Off > Apply Changes**; leave the existing ad policy and
local DNS records intact.

The resumed UI showed 33,225 signatures, Default only and Notify retained,
with zero security detections in its current month view. Sequential macOS
`networkQuality` over Wi-Fi measured about 622 Mbps down / 80 Mbps up, with
1177/144 RPM download/upload responsiveness. This routed-client sample has no
comparable pre-IDS client baseline and ran near deployment work; it cannot
attribute a performance change to IDS. Keep Notify mode.

Before conversion, the five custom printer rules retained their order: LAN In TCP/8099 allow at
20000 then all-other drop at 20001; LAN Local mDNS/DHCP allows at 20000/20001
then gateway drop at 20002. The legacy UI did not expose packet counters;
Max SSH remains off. The same-AP second-printer-peer check passed for the
Mac/awake-phone pair described above.
Two UPnP mappings were observed (HA UDP and NAS/Plex TCP); neither was removed.

Ryan subsequently approved read-only use of the existing native Debug console
and its displayed terms notice. With console SSH still off, exact counters
from `UBIOS_LAN_IN_USER` and `UBIOS_LAN_LOCAL_USER` established this baseline:

| Printer rule | Packets | Bytes |
| --- | ---: | ---: |
| HA TCP/8099 allow | 47 | 3,797 |
| Other routed traffic drop | 1,565 | 222,747 |
| Gateway mDNS allow | 38,547 | 15,075,693 |
| Gateway DHCP allow | 0 | 0 |
| Other gateway traffic drop | 6,091 | 365,976 |

These are cumulative counters, not isolated probe deltas. The zero DHCP count
does not prove the rule is redundant: initial DHCP can use earlier system
handling. Keep every translated rule until its lack of effect is established.
The private counter receipt records the observation method and timestamp.

Before the zone upgrade, a fresh **Network-only** export (99,632 bytes) was
downloaded, encrypted with the existing recovery identity and authenticated-
decryption verified. Preserve it and the accepted full System exports. Rollback
of an unsuccessful zone conversion is **Management > General > Restore from
Backup**, selecting that pre-zone Network export on this same Max/version;
retain the original native download for that path. Recheck DNS, both VPNs and
every printer allow/deny path after restoration. Do not use the retired Cloud
Key export or a CLI ruleset rewrite as the rollback.
After the later Site Magic cutover, withdraw the mesh LAN advertisements first
before restoring a pre-zone backup that enables the superseded manual peer.
Coordinate both consoles to avoid restoring competing routes.

Safari then completed the supported zone upgrade. Default and the printer VLAN
both mapped to **Internal**, retaining network-specific printer constraints;
this did not create a new Printer zone. The cloud policy-based IPsec connection
retains its generated policy handling; Lehigh appears in VPN. The restored
inactive Internet 2 definition remains listed in External without an active
secondary WAN. No VLAN, SSID, peer or radio settings changed.

The conversion produced eleven custom policies. Associated-client testing then
recorded hits on the Internal HA allow (11), mDNS allow (553), Internal drop
(28), External drop (17), VPN drop (4) and Gateway drop (376). Three generated
HA allow copies targeted Hotspot, External and VPN despite their fixed
`192.168.1.163` destination being connected to Internal. Their predicates cannot
match that current destination route, and all three showed no hits. Only those
copies were **paused** through the native UI, leaving eight active custom
policies and three recoverable copies. UniFi labels removal irreversible, so
no policy was deleted. The DHCP allow and every drop policy remain active.
To reverse this cleanup, show Paused policies and resume only those three HA
allow copies. Further cleanup needs new route and counter/effect evidence.

After conversion, the complete gateway DNS contract passed over UDP/TCP;
native MCP reads and the cloud `--require-sha256` preflight passed. Lehigh's
gateway TCP/443 remained reachable, Seerr returned HTTP 307, both private
proxies returned HTTP 401 and the tested direct backend stayed blocked.
From the associated printer client, HA health returned HTTP 200 and a fresh
mDNS wire answer; unrelated LAN, gateway, Internet and cloud paths remained
blocked. The phone had left the printer SSID, so post-conversion negative phone
probes were not counted as another peer test. The accepted same-AP peer test
predates conversion; AP isolation settings were unchanged.
The IoT SSID still shares Default and is not a separate security zone.

After the reversible cleanup, the printer health and fresh mDNS checks passed
again with all seven routed allow/deny expectations intact. Fresh Companion,
AirPlay and Sonos wire replies again yielded 27 reachable advertised TCP
endpoints. Network IDs, addressing, VLAN and DHCP/DNS fields matched the
pre-conversion snapshot; trusted gateway DNS, Internet and wiki access worked,
and the other direct backend TCP/9696 stayed blocked. The final full System
export (166,688 bytes) includes the zone framework and paused copies; it was
encrypted and authenticated-decryption verified. Preserve it alongside the
pre-zone Network-only export and every earlier archive.

Ryan then confirmed Apple TV Remote, AirPlay and Sonos controls working and
cloud-application sign-ins working from the home LAN. These are owner-verified
interactive checks, distinct from the agent's packet/transport evidence and
not a new codec, playback-duration or every-client test matrix.

Record a throughput/latency baseline, then pilot available native IDS/IPS and
check application operation and alerts. No paid subscription was selected.
Keep category filtering, IPv6, UPnP, STP and radio tuning as separately measured
decisions; a zone migration does not authorize unrelated behavior changes.

## Remaining acceptance

Site Magic is accepted against Ryan's explicitly revised criterion: UniFi
reports both gateways Connected with the intended LAN-only advertisements.
No Lehigh test host is available, so no bidirectional host test is claimed.
Both superseded manual definitions remain paused for rollback.
Zone migration and the bounded reversible duplicate cleanup are complete;
restricted printing, a same-AP printer peer and fresh wire-level discovery
are accepted.
Fresh wired/wireless DHCP and owner-verified application controls/sign-ins are
accepted. HA-forwarder outage behavior and automatic local-zone failover remain
unverified; preserve both AdGuards and the accepted hybrid. AP bridge captures are
the diagnostic next step if a future discovery failure needs localization;
the current client wire-level discovery and endpoint checks pass.

The native local API-key form has no read-only scope selector. The owner-approved
**Codex UniFi MCP - 300 Newark** key expires **November 22, 2026**; its initial
unused value was revoked and replaced before storage. Ryan now supplies
`UBIQUITI_API_KEY` through ChatGPT's MCP environment settings. The launcher uses
only that variable, maps it to upstream's `UNIFI_API_KEY`, and no longer invokes
1Password or Keychain. The owner's existing environment setting must be
preserved when editing server registration.

The exact GitHub `0.6.1` source commit
`12b4c6e964f920806e2604ab8554e98a4b92536f` is installed/cached. A direct MCP
session with the settings-provided key initialized and exposed 26 tools.
The earlier session's first live read failed under executor restrictions.
The resumed native MCP reads and approved external-to-sandbox TCP/TLS checks
now pass. No credential or package change was needed. Do not repeat key creation,
1Password setup or installation. Five synthetic launcher tests cover environment
mapping, invalid/missing values, protocol input, tracing privacy and forced
read-only settings. See the [MCP runbook](../../network-infra/unifi-mcp/README.md).

## Validation — October 22

All 549 infrastructure unit tests, deployment syntax/YAML/ShellCheck checks,
26 wiki tests, six DNS tests and five launcher tests passed. The required full
infrastructure recipe exits nonzero only at the two previously documented
[historical RSA-key findings](../../usenet-infra/docs/security-findings.md).
The separate current-source/index secret scan passes; no history was rewritten
or exception added. The unchanged live DNS contract passes against all three
resolvers. After the VPN rekey, LAN requests returned wiki HTTP 200, SAB/Prowlarr
HTTP 401 and Seerr HTTP 307; backend TCP/8080 and TCP/9696 remained blocked.
Those probes establish reachability and authentication gates. Ryan subsequently
confirmed interactive LAN sign-ins separately, as recorded above.

## Sources

- [UniFi DNS and local hostnames](https://help.ui.com/hc/en-us/articles/15179064940439-UniFi-DNS-Records-and-Local-Hostnames)
- [UniFi content filtering](https://help.ui.com/hc/en-us/articles/12568927589143-Content-and-Domain-Filtering-in-UniFi)
- [UniFi SD-WAN mesh](https://help.ui.com/hc/en-us/articles/16750417515159-UniFi-Gateway-Setting-Up-SD-WAN-with-UniFi-Site-Manager-and-Fabrics)
- [Zone firewall migration](https://help.ui.com/hc/en-us/articles/28223082254743-Migrating-to-Zone-Based-Firewalls-in-UniFi)
- [MCP launcher](../../network-infra/unifi-mcp/README.md)
