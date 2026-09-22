# Seerr discovery and requests

Open [Seerr](http://10.77.0.1:15055/) on the home network or existing VPN route
and **sign in with the existing Plex owner account**. There is no new password.
Other Plex accounts cannot automatically enroll; local-password login is off.
Browse trending/popular movies and TV, filter by genre, or search. Request a
movie or selected TV seasons; use Sonarr directly for individual episodes.
The default quality is Ultra-HD: prefer 2160p / 4K, with 1080p fallback when
no eligible 4K release is available. Both native profile ID 5 definitions allow
1080p beneath every 2160p source; retain that ordering when restoring profiles.
Availability comes from the four general Plex
libraries (IDs 2/3/4/5); private library ID 1 is excluded.

Seerr sends explicit requests to Radarr/Sonarr, which find releases through
Prowlarr, send them to SAB, import into the Storage Box and clean up completed
sources. Watchlist acquisition is off. Arr RSS polling remains off to preserve
the existing missing backlog; future episodes require explicit Sonarr searches.
Wait for a large request to finish before adding another. Failed jobs remain
for review, and the 100 GiB release limit still applies.

The existing single-copy server entries use the 4K quality profile; Seerr's
separate `is4k` server flag stays false because it enables a second parallel
copy workflow. Existing library items and pending requests are not bulk
upgraded or searched by a default-profile change. Automatic upgrades remain off.

Both NZBGeek and NZBFinder cart feeds remain disabled. Their credentials are
still used by Prowlarr for native searches. The three old paused requests,
44 journals and retired worker guards are preserved. Do not enable a cart or
restart its retired worker to test Seerr.

## Deployment and verification

The isolated `usenet-seerr` Compose project runs Seerr v3.4.1, pinned to digest
`sha256:f4768de5f616248d723e05891f3345a1402123775d03bf0890dbfedc0831bda1`.
The app listens only on loopback port 5055. Its private proxy listens on
10.77.0.1:15055 and rejects API-key authentication from remote clients.
The VPN firewall permits that UI only through the existing private tunnel;
Plex access is limited to the selected NAS host and port 32400 through IPsec.
No media storage is mounted into Seerr. The service runs as the existing
unprivileged identity with a read-only image and bounded temporary/cache space.

```sh
just usenet-configure-seerr
just usenet-seerr-status
just usenet-native-ownership-status
```

Bootstrap privately derives the existing owner token from Plex preferences;
`secrets/seerr/plex-bootstrap.json` is ignored, mode 0600, and never printed.
The temporary remote bootstrap copy is removed even on deployment failure.
Future VPN role deployments must retain `cloud_vpn_seerr_nas_ip` in the private
inventory. Deployment does not restart Plex, SAB, Arr or Filex.

Status verifies selected library IDs, login policy, native connections,
Ultra-HD profile, watchlist policy and nonempty discovery feeds. Connection tests
do not prove a real request/import; no media is selected implicitly for testing.
The existing native import acceptance is documented separately in the plan.

Cloud encrypted backups include `config/seerr` (settings and SQLite database),
`compose/seerr` and the installed helper. Logs/cache are excluded. Restore into
an isolated directory first; reconstruct `usenet-seerr.service` from source and
reconcile private VPN policy before enabling. Replacement-host startup remains
separate from archive restoration.

To roll back the portal, stop and disable only `usenet-seerr.service`, retaining
its configuration/database for recovery. Keep both carts disabled; native Arr
manual requests remain available. Never restore historical cart/RSS policy.

Official references: [release](https://github.com/seerr-team/seerr/releases/tag/v3.4.1),
[Docker setup](https://docs.seerr.dev/getting-started/docker/),
[service settings](https://docs.seerr.dev/using-seerr/settings/services/).
