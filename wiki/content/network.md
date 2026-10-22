# Network and local names

UniFi connects the trusted household network, Home Assistant, the NAS, and the devices. The separate restricted printer network intentionally has narrower access. The IoT Wi-Fi name uses the trusted network and is not a separate routed security boundary.

## Find this guide

The stable name is `http://wiki.home.arpa/`. On October 16, both AdGuard resolvers answered it, but the checked Mac still used the USG for DNS and received “name not found.” Client cutover remains pending; use the numeric address until your client's DNS path is verified. If DNS is unavailable, use [the NAS address](http://192.168.1.66/). The old [Usenet address](http://192.168.1.66:8090/) remains a compatibility entrance.

The wiki is plain HTTP on the trusted network, without a separate login. Application links still require their own authentication. There is no public wiki listener or certificate installation.

## Gateway upgrade installed

The **Cloud Gateway Max NS (US Version), UCG-Max-NS**, took over routing and UniFi Network management on **October 22, 2026**. A fresh Network-only backup restored the existing configuration after the full console backup failed. Ryan confirmed the retained switch and both access points online in the Max's controller.

Checks from the Mac passed for gateway reachability, public DNS, Internet HTTPS, Home Assistant, and the wiki's numeric address. Both site-to-site VPNs were repaired after the WAN address changed and now show Established. Lehigh's gateway and the private Usenet application endpoints are reachable. Fresh DHCP leases, reservations, printer isolation and printing, and media-device discovery still need explicit acceptance. Save a post-cutover Max System Config backup. Retain the disconnected USG and Cloud Key with their configurations intact, and check the Cloud Key's other applications/sites before retiring it.

DNS and ad blocking remain a separate decision after baseline acceptance. Choose between native UniFi DNS/ad blocking and the existing AdGuard pair. The [migration record and hardware inventory](../../docs/operations/unifi-network-setup.md#cloud-gateway-max-migration) record the cutover, checks, and rollback requirements.

A duplicate-address warning after cutover identified Prusa Alpha and “Nest I think” at `192.168.1.118`. Both now have separate reservations: the printer keeps `.118`, and the Nest uses `192.168.1.19`. The Nest reconnected successfully, and both devices passed reachability checks. A historical conflict event is not proof of a current conflict; compare the current client addresses before changing them again.

## DNS design

The [generated DNS policy](wiki-reference:network) lists the configured resolvers, local records, upstreams and filter settings directly from the repository. The resolvers use independent upstream access, and unknown names below the local zone stay local.

If the AdGuard design is retained, both addresses must be advertised together by trusted-LAN DHCP after the rollout checks pass. A public resolver is not a suitable fallback because it cannot answer private names. Keep the resolvers intact while the final DNS design remains pending.

## Troubleshooting and recovery

If the numeric wiki address works but the name fails, inspect the client’s actual DNS servers, lease age, and any browser encrypted-DNS override. Ask each resolver directly before restarting anything. A cached answer alone does not establish failover.

If internet DNS fails, check each resolver and its upstream route separately. Keep the previous DHCP settings and resolver configurations available for rollback. Numeric NAS and Home Assistant addresses remain the recovery path.

Use [DNS operations](../../docs/operations/home-dns.md) for deployment and recovery and [the UniFi baseline](../../docs/operations/unifi-network-setup.md) for topology. Use the [Bonjour runbook](../../docs/operations/unifi-apple-tv-remote.md) for discovery failures; `.local` mDNS and `home.arpa` unicast DNS are different mechanisms.

The October 22 VPN repair corrected Lehigh's stale remote address and restored the disabled Usenet tunnel, including its encryption setting and the cloud's peer identities and source restrictions. The [Usenet VPN runbook](../../usenet-infra/docs/lan-ui.md) records the verified scope and recovery procedure. Named access over a VPN additionally requires that client's DNS routing to reach the household resolvers; do not infer that from LAN verification.
