# Network and local names

UniFi connects the trusted household network, Home Assistant, the NAS, and the devices. The separate restricted printer network intentionally has narrower access. The IoT Wi-Fi name uses the trusted network and is not a separate routed security boundary.

## Find this guide

The stable name is `http://wiki.home.arpa/`. As of October 9, both resolvers answer it, but the DHCP cutover still awaits UniFi sign-in; use the numeric address until your client uses those resolvers. If DNS is unavailable, use [the NAS address](http://192.168.1.66/). The old [Usenet address](http://192.168.1.66:8090/) remains a compatibility entrance.

The wiki is plain HTTP on the trusted network, without a separate login. Application links still require their own authentication. There is no public wiki listener or certificate installation.

## DNS design

Two resolvers on existing hosts provide the same local records: Home Assistant AdGuard at `192.168.1.163` and NAS AdGuard at `192.168.1.66`. Both map `wiki.home.arpa` to `192.168.1.66`. Neither depends on the other for internet DNS, and unknown names below `home.arpa` stay local.

Both addresses must be advertised together by trusted-LAN DHCP after the rollout checks pass. A public resolver is not a suitable fallback because it cannot answer the private name. The deployment record distinguishes configured intent from completed DHCP cutover.

## Troubleshooting and recovery

If the numeric wiki address works but the name fails, inspect the client’s actual DNS servers, lease age, and any browser encrypted-DNS override. Ask each resolver directly before restarting anything. A cached answer alone does not establish failover.

If internet DNS fails, check each resolver and its upstream route separately. Keep the previous DHCP settings and resolver configurations available for rollback. Numeric NAS and Home Assistant addresses remain the recovery path.

Use [DNS operations](../../docs/operations/home-dns.md) for deployment and recovery and [the UniFi baseline](../../docs/operations/unifi-network-setup.md) for topology. Use the [Bonjour runbook](../../docs/operations/unifi-apple-tv-remote.md) for discovery failures; `.local` mDNS and `home.arpa` unicast DNS are different mechanisms.

Existing VPN routing is retained. Named access over a VPN additionally requires that client’s DNS routing to reach the household resolvers; do not infer that from LAN verification.
