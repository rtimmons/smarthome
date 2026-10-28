# Network and local names

The [HTTPS wiki](https://wiki.home.rytim.com/) uses Ryan’s Authelia MFA. The HTTP entrances below remain available for LAN compatibility and recovery. These retained paths mean browser SSO is not universal network enforcement.

The Cloud Gateway Max at `192.168.1.1` provides routing and UniFi management.
The USG and Cloud Key are retired and disconnected; their configurations and
encrypted backups remain available for rollback.

## Find this guide

Open [the authenticated HTTPS wiki](https://wiki.home.rytim.com/).
For LAN compatibility or SSO recovery, use `http://wiki.home.arpa/`.
If DNS fails, use [the NAS address](http://192.168.1.66/).
The [original port-8090 entrance](http://192.168.1.66:8090/) also works. The wiki
HTTP compatibility entrance is unauthenticated on the trusted home network;
the HTTPS entrance above requires Authelia MFA. Linked services have their own
authentication boundaries. There is no public wiki listener.

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

Open [Grid Dashboard](https://grid-dashboard.home.rytim.com/) with Authelia MFA on the Newark trusted
LAN. Its explicit DNS alias points to Home Assistant, where the Home HTTP Proxy
forwards requests to `hass.home.arpa:3000`. The browser keeps the friendly name.
The HTTPS entrance is separate from the retained HTTP kiosk route.
The [direct dashboard address](http://hass.home.arpa:3000/) and Home Assistant
sidebar remain available. This HTTP proxy accepts only Newark LAN clients;
it does not add Internet access or automatic service discovery.

See [proxy operation and recovery](../../docs/operations/home-dns.md#http-service-pilot).

For a saved TinyURL slug, use `http://go/<slug>` on the Newark trusted LAN.
The gateway resolves `go` (also `go.localdomain`), and the proxy redirects to
the same path at `tinyurl.home.arpa`. Use the explicit `http://` prefix;
public or encrypted DNS overrides may bypass the household shortcut. See
[short-name setup and recovery](../../docs/operations/service-hostnames.md#tinyurl-short-name).

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
confirmed OTP enrollment. Forgejo's native OIDC account link and fresh sign-in
passed. Arr/SAB browser entrances now use the Authelia MFA proxy; Prowlarr uses
External authentication and native API keys remain unchanged. Catalog has an
outer MFA gate plus native OAuth. The user confirmed all four Arr/SAB browser
entrances and Catalog OAuth sign-in with visible operator actions on October 25,
2026. No search, download or transfer was started. Jellyfin uses verified AD-backed LDAPS
with the existing account; its playback APIs have no browser MFA redirect.
The directory moved from the NAS to HA with its existing identity;
QNAP's machine trust and both household logins passed. Follow the dated
[identity rollout and recovery record](../../docs/operations/household-identity.md)
for current status and the separate human enrollment steps.

The [service hostname inventory](../../docs/operations/service-hostnames.md)
lists explicit routes for [Jellyfin](https://jellyfin.home.rytim.com/),
[Moonfin](https://jellyfin.home.rytim.com/Moonfin/Web/), [Plex](http://plex.home.arpa/),
[Seerr](http://seerr.home.arpa/), [Radarr](https://radarr.home.rytim.com/),
[Sonarr](https://sonarr.home.rytim.com/), [Prowlarr](https://prowlarr.home.rytim.com/),
[SABnzbd](https://sabnzbd.home.rytim.com/), [catalog](https://catalog.home.rytim.com/),
[printer](https://printer.home.rytim.com/) and [TinyURL](https://tinyurl.home.rytim.com/).
Retained HTTP, direct-port and recovery routes have separate access controls;
these HTTPS entrances do not make SSO universal network enforcement. The Arr names reach the
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

Ryan's laptop has two reserved addresses: `ryan-laptop-wifi.home.arpa` resolves
to `192.168.1.72`, and `ryan-laptop-ethernet.home.arpa` to `192.168.1.109` through
the CalDigit adapter. These manual names remain pinned when an interface is
disconnected. Its shared Bonjour hostname can advertise both addresses and is
therefore skipped by discovery. See [laptop interface aliases](../../docs/operations/home-dns.md#laptop-interface-aliases).

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
