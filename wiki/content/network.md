# Network and local names

The [HTTPS wiki](https://wiki.home.rytim.com/) uses Ryan’s Authelia MFA. The HTTP entrances below remain available for LAN compatibility and recovery. These retained paths mean browser SSO is not universal network enforcement.

The Cloud Gateway Max at `192.168.1.1` provides routing and UniFi management.
The USG and Cloud Key are retired and disconnected; their configurations and
encrypted backups remain available for rollback.

## Find this guide

Open **http://wiki.home.arpa/**. If DNS fails, use [the NAS address](http://192.168.1.66/).
The [original port-8090 entrance](http://192.168.1.66:8090/) also works. The wiki
is plain HTTP on the trusted home network; linked applications keep their own
sign-ins. There is no public wiki listener.

## DNS design

Newark clients use the gateway for DNS. It automatically forwards `home.arpa` to either
Home Assistant or NAS AdGuard; both remain running and required. AdGuard owns
`wiki.home.arpa`, `hass.home.arpa`, and imported Bonjour hostnames, and answers unknown local names locally. The duplicate native
wiki record stays paused. Native ad blocking remains enabled, with category
filtering and Safe Search off.

Open Home Assistant at [hass.home.arpa:8123](http://hass.home.arpa:8123/).
The name resolves to its LAN address, `192.168.1.163`.

October 22 checks passed during either resolver outage and after recovery.
With both unavailable, private names failed closed without appearing in the
WAN DNS capture. Public DNS and ad blocking continued working. See the
[generated DNS policy](wiki-reference:network) and [DNS recovery](../../docs/operations/home-dns.md).

## Named web services

Open [Grid Dashboard](http://grid-dashboard.home.arpa/) on the Newark trusted
LAN. Its explicit DNS alias points to Home Assistant, where the Home HTTP Proxy
forwards requests to `hass.home.arpa:3000`. The browser keeps the friendly name.
The [direct dashboard address](http://hass.home.arpa:3000/) and Home Assistant
sidebar remain available. This HTTP proxy accepts only Newark LAN clients;
it does not add Internet access or automatic service discovery.

See [proxy operation and recovery](../../docs/operations/home-dns.md#http-service-pilot).

## Household sign-in rollout

The `SMARTHOME` AD directory runs on Home Assistant at `192.168.1.10` and uses
`ad.home.arpa`. Both household resolvers forward that subtree to the directory.
The gateway also forwards `home.rytim.com` to both resolvers for private browser
addresses. These names use Let's Encrypt certificates; client devices do not
need a new root certificate. `.home.arpa` remains the local discovery namespace.

Authelia runs on Home Assistant at
[the sign-in portal](https://auth.home.rytim.com), with verified public HTTPS.
QNAP has joined the directory; household share grants passed encrypted SMB read,
write and denial checks. Gmail SMTP delivered the enrollment email, and Ryan
confirmed OTP enrollment. Forgejo linking and application SSO checks remain.
The directory moved from the NAS to HA with its existing identity;
QNAP's machine trust and both household logins passed. Forgejo and Arr follow after
each service's access checks pass. Existing service sign-ins stay authoritative
until their migration is verified. Follow the dated
[identity rollout and recovery record](../../docs/operations/household-identity.md)
for current status and the separate human enrollment steps.

The [service hostname inventory](../../docs/operations/service-hostnames.md)
lists explicit routes for [Jellyfin](http://jellyfin.home.arpa/),
[Moonfin](http://moonfin.home.arpa/), [Plex](http://plex.home.arpa/),
[Seerr](http://seerr.home.arpa/), [Radarr](http://radarr.home.arpa/),
[Sonarr](http://sonarr.home.arpa/), [Prowlarr](http://prowlarr.home.arpa/),
[SABnzbd](http://sabnzbd.home.arpa/), [catalog](http://catalog.home.arpa/),
[printer](http://printer.home.arpa/) and [TinyURL](http://tinyurl.home.arpa/).
Existing sign-ins and direct ports remain available. The Arr names reach the
active cloud stack; Moonfin uses the same Jellyfin server. `ha.home.arpa` is
still deferred.

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

## Discover device names

The NAS discovers Bonjour hostnames automatically about once a minute and
maintains matching `.home.arpa` names on both resolvers, even while the Mac is
off. New names normally appear within one or two minutes. Existing manual
aliases win over discovered names; learned names missing for seven days expire.
Only unambiguous Newark trusted-LAN IPv4 addresses are imported.

Cabin / Lehigh discovery is not yet enabled. A Newark-side check reached the
Lehigh gateway and received the expected wiki DNS answer on October 24, but
resolution and application access from cabin clients still need verification.
See [Lehigh coverage and remaining checks](../../docs/operations/home-dns.md#cabin-lehigh-coverage-pending-acceptance).

`just dns-auto-status` reports the last scan. `just dns-check` validates the
live inventory. `just dns-auto-deploy` installs/updates the scanner and
`just dns-auto-stop` pauses discovery without stopping DNS. Updates use the
resolver APIs without restarts. See
[automatic NAS discovery](../../docs/operations/home-dns.md#automatic-nas-discovery)
for ownership, recovery and credentials.
