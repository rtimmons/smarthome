# Network and local names

UniFi connects the trusted household network, Home Assistant, the NAS, and the devices. The separate restricted printer network intentionally has narrower access. The IoT Wi-Fi name uses the trusted network and is not a separate routed security boundary.

## Find this guide

The stable name is `http://wiki.home.arpa/`. On October 16, both AdGuard resolvers answered it, but the checked Mac still used the USG for DNS and received “name not found.” Client cutover remains pending; use the numeric address until your client's DNS path is verified. If DNS is unavailable, use [the NAS address](http://192.168.1.66/). The old [Usenet address](http://192.168.1.66:8090/) remains a compatibility entrance.

The wiki is plain HTTP on the trusted network, without a separate login. Application links still require their own authentication. There is no public wiki listener or certificate installation.

## Gateway upgrade ordered

Ryan ordered a **Cloud Gateway Max NS (US Version), UCG-Max-NS**, on **October 16, 2026**. Expected arrival is approximately **October 23–30**, based on his one-to-two-week estimate. It is not installed; the USG 3P and Cloud Key Gen2 Plus remain the current gateway and controller.

The new device is intended to take over both routing and this site's UniFi Network management. Keep the existing switch and two access points. Retain the old gateway and Cloud Key for rollback, and check the Cloud Key's other applications/sites before deciding whether to retire it.

Ryan will request migration help once it arrives. Network settings, including DNS and ad blocking, are deferred until then. First migrate and verify the existing network; then choose between native UniFi DNS/ad blocking and the existing AdGuard pair. The [migration plan and hardware inventory](../../docs/operations/unifi-network-setup.md#planned-cloud-gateway-max-migration) record preparation, checks, and rollback.

## DNS design

The [generated DNS policy](wiki-reference:network) lists the configured resolvers, local records, upstreams and filter settings directly from the repository. The resolvers use independent upstream access, and unknown names below the local zone stay local.

If the AdGuard design is retained, both addresses must be advertised together by trusted-LAN DHCP after the rollout checks pass. A public resolver is not a suitable fallback because it cannot answer private names. Keep the resolvers intact while the gateway migration and final DNS design remain pending.

## Troubleshooting and recovery

If the numeric wiki address works but the name fails, inspect the client’s actual DNS servers, lease age, and any browser encrypted-DNS override. Ask each resolver directly before restarting anything. A cached answer alone does not establish failover.

If internet DNS fails, check each resolver and its upstream route separately. Keep the previous DHCP settings and resolver configurations available for rollback. Numeric NAS and Home Assistant addresses remain the recovery path.

Use [DNS operations](../../docs/operations/home-dns.md) for deployment and recovery and [the UniFi baseline](../../docs/operations/unifi-network-setup.md) for topology. Use the [Bonjour runbook](../../docs/operations/unifi-apple-tv-remote.md) for discovery failures; `.local` mDNS and `home.arpa` unicast DNS are different mechanisms.

Existing VPN routing is retained. Named access over a VPN additionally requires that client’s DNS routing to reach the household resolvers; do not infer that from LAN verification.
