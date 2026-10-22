# Network and local names

UniFi connects the trusted household network, Home Assistant, the NAS, and the devices. The separate restricted printer network intentionally has narrower access. The IoT Wi-Fi name uses the trusted network and is not a separate routed security boundary.

## Find this guide

The stable name is `http://wiki.home.arpa/`. On October 22, the Max’s forwarding-only hybrid passed the exact DNS checks and a fresh Mac Wi-Fi lease used gateway DNS. The duplicate native wiki record is saved but paused; AdGuard owns the local answers. If DNS is unavailable, use [the NAS address](http://192.168.1.66/). The old [Usenet address](http://192.168.1.66:8090/) remains a compatibility entrance.

The wiki is plain HTTP on the trusted network, without a separate login. Application links still require their own authentication. There is no public wiki listener or certificate installation.

## Gateway upgrade installed

The **Cloud Gateway Max NS (US Version), UCG-Max-NS**, took over routing and UniFi Network management on **October 22, 2026**. A fresh Network-only backup restored the existing configuration after the full console backup failed. Ryan confirmed the retained switch and both access points online in the Max's controller.

Checks from the Mac passed for gateway reachability, public DNS, Internet HTTPS, Home Assistant, and the wiki's numeric address. Both site-to-site VPNs were repaired after the WAN address changed and showed Established. Lehigh's gateway and the private Usenet application endpoints were reachable. The resumed checks verified fresh Mac wireless leases, a new Home Assistant Ethernet lease after cutover, all seven infrastructure reservations, printer-network restrictions and an isolated phone peer on the same AP. Ryan confirmed the single test label printed correctly. Fresh Bonjour wire replies and all 27 advertised Companion, AirPlay and Sonos TCP endpoints passed. Ryan also confirmed Apple TV Remote, AirPlay and Sonos controls, plus cloud-app sign-ins from home. A fresh full Max System export is encrypted off-device and decryption-verified. Ryan confirmed the USG and Cloud Key retired from active service; retain their disconnected configurations for rollback.

Ryan authorized a native DNS/ad-blocking pilot, Site Magic for Lehigh, cloud VPN
modernization and tooling cleanup. The forwarding-only DNS hybrid, cloud SHA-256 reconnect/PFS rekey and
native read-only MCP are accepted. The zone firewall is now active: it retains
the printer's network-specific restrictions, with eight active custom policies
and three redundant HA allow copies paused for easy recovery. Default and the
printer VLAN both remain in Internal. The `Newark-Lehigh` Site Magic mesh now
reports both gateways Connected and shares only Newark `192.168.1.0/24` and
Lehigh `192.168.8.0/24`. Printer and cloud VPN networks are excluded. Both old
manual IPsec definitions are paused for rollback. Ryan accepted UniFi's status
without a Lehigh test host; bidirectional host application tests were not run.
The [post-migration checklist](../../docs/operations/unifi-post-migration.md)
records status and acceptance; the [migration record](../../docs/operations/unifi-network-setup.md#cloud-gateway-max-migration)
records the completed cutover.

The free intrusion-detection pilot is now on for Default in **Notify** mode;
it reports detections without blocking traffic. The gateway's own speed tests
were 942/951 Mbps before and 929/923 afterward (download/upload). Those samples
do not establish client throughput or a sustained performance change. Printer
network isolation and existing VPN routes were preserved. The later routed Mac Wi-Fi sample measured about 622/80 Mbps; without a
comparable pre-IDS client baseline it cannot attribute a change to IDS. The
current security log view showed no detections. Keep Notify mode.

A duplicate-address warning after cutover identified Prusa Alpha and “Nest I think” at `192.168.1.118`. Both now have separate reservations: the printer keeps `.118`, and the Nest uses `192.168.1.19`. The Nest reconnected successfully, and both devices passed reachability checks. A historical conflict event is not proof of a current conflict; compare the current client addresses before changing them again.

## DNS design

The [generated DNS policy](wiki-reference:network) lists the configured resolvers, local records, upstreams and filter settings directly from the repository. The resolvers use independent upstream access, and unknown names below the local zone stay local.

The native gateway has two `home.arpa` forwarding policies, targeting HA and NAS
AdGuard. Its duplicate wiki A
record is paused because it caused the apex-response mismatch. Default's pre-existing native ad blocking remains enabled, with
content categories and Safe Search off. Exact UDP/TCP answers, a synthetic local rewrite without an upstream,
fresh Mac wireless resolution and an ad-domain block passed. Keep both AdGuards
running: the native dual-forwarder design passed each backend outage from the
Mac, including ordinary wiki-by-name HTTP access, while both services remained
running. The gateway automatically selected the surviving resolver. If direct AdGuard client DNS is selected, both
addresses must be advertised together by trusted-LAN DHCP after rollout checks
pass. A public fallback cannot answer private names.

## Troubleshooting and recovery

The restricted printer Wi-Fi intentionally has no Internet access. An iPhone
may switch a local request to cellular data even while it shows that Wi-Fi
connected. If the permitted print endpoint fails to load, temporarily turn
cellular data off, retry the explicit local HTTP address, then restore cellular
data. This passed on October 22; it does not require widening the firewall.

If the numeric wiki address works but the name fails, inspect the client’s actual DNS servers, lease age, and any browser encrypted-DNS override. Ask each resolver directly before restarting anything. A cached answer alone does not establish failover.

If internet DNS fails, check each resolver and its upstream route separately. Keep the previous DHCP settings and resolver configurations available for rollback. Numeric NAS and Home Assistant addresses remain the recovery path.

Use [DNS operations](../../docs/operations/home-dns.md) for deployment and recovery and [the UniFi baseline](../../docs/operations/unifi-network-setup.md) for topology. Use the [Bonjour runbook](../../docs/operations/unifi-apple-tv-remote.md) for discovery failures; `.local` mDNS and `home.arpa` unicast DNS are different mechanisms.

The October 22 VPN repair corrected Lehigh's stale remote address and restored the disabled Usenet tunnel, including its encryption setting and the cloud's peer identities and source restrictions. The later paired change verified SHA-256, reconnect and PFS rekey on the cloud tunnel. The [Usenet VPN runbook](../../usenet-infra/docs/lan-ui.md) records the verified scope and recovery procedure. Named access over a VPN additionally requires that client's DNS routing to reach the household resolvers; do not infer that from LAN verification.
