# Network and local names

The Cloud Gateway Max at `192.168.1.1` provides routing and UniFi management.
The USG and Cloud Key are retired and disconnected; their configurations and
encrypted backups remain available for rollback.

## Find this guide

Open **http://wiki.home.arpa/**. If DNS fails, use [the NAS address](http://192.168.1.66/).
The [original port-8090 entrance](http://192.168.1.66:8090/) also works. The wiki
is plain HTTP on the trusted home network; linked applications keep their own
sign-ins. There is no public wiki listener.

## DNS design

Clients use the gateway for DNS. It automatically forwards `home.arpa` to either
Home Assistant or NAS AdGuard; both remain running and required. AdGuard owns
`wiki.home.arpa` and answers unknown local names locally. The duplicate native
wiki record stays paused. Native ad blocking remains enabled, with category
filtering and Safe Search off.

October 22 checks passed during either resolver outage and after recovery.
With both unavailable, private names failed closed without appearing in the
WAN DNS capture. Public DNS and ad blocking continued working. See the
[generated DNS policy](wiki-reference:network) and [DNS recovery](../../docs/operations/home-dns.md).

## Restricted printing and recovery

`sintheta-printer` permits discovery and the Home Assistant print endpoint,
while blocking Internet, unrelated LAN/gateway access and peer clients. On an
iPhone, temporarily turn cellular data off if a local request fails, then
restore it after testing. `sintheta-iot` is a compatibility Wi-Fi name on the
trusted LAN, not a separate security boundary.

The October 22 acceptance included leases, reservations, a physical test print,
printer restrictions, Apple TV Remote, AirPlay, Sonos and cloud-app sign-ins.
Site Magic connects only the Newark and Lehigh Default LANs; the cloud VPN uses
SHA-256. Intrusion detection is Notify-only on Default, excluding printer.
Current radio and Sonos tuning is preserved.

For help, use [network setup](../../docs/operations/unifi-network-setup.md),
[SSH access](../../docs/operations/unifi-ssh-access.md),
[Bonjour troubleshooting](../../docs/operations/unifi-apple-tv-remote.md) or
[accepted changes and rollback](../../docs/operations/unifi-post-migration.md).
SSH is verified on the Max, both APs and switch; printer and external WAN access
remain blocked. The acceptance record lists test limits and recovery steps.
