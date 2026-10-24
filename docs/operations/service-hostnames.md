# Web service inventory and proposed hostnames

Inventory: October 24, 2026, Newark LAN. **Proposal only:** the additional names
below have not been deployed by this inventory. Keep direct host-and-port access.
The existing HTTP proxy binds `192.168.1.163:80` and permits only
`192.168.1.0/24` clients. No new WAN access, wildcard DNS, automatic discovery,
application restarts, acquisition requests or playback actions are proposed here.

## Recommended explicit mappings

For new proxied names, add exact A records pointing to **192.168.1.163**, even
when the upstream is on the NAS or cloud VPN. `wiki.home.arpa` keeps its existing
NAS address and isolated static server. `hass.home.arpa` remains the host alias.

| Proposed browser hostname | Upstream reachable from home | Entry path / routing requirement | Inventory evidence |
| --- | --- | --- | --- |
| `jellyfin.home.arpa` | `http://192.168.1.66:8096` | Preserve all paths; stock web client | NAS container running/healthy; `/` returned 302 |
| `moonfin.home.arpa` | `http://192.168.1.66:8096` | Redirect only `/` to `/Moonfin/Web/` on the same hostname; proxy every other path unchanged | Moonfin Web returned 200; same Jellyfin container |
| `plex.home.arpa` | `http://192.168.1.66:32400` | Redirect only `/` to `/web/`; preserve other paths | Native NAS listener; `/web/` returned 302 to its web client |
| `seerr.home.arpa` | `http://10.77.0.1:15055` | Existing private Seerr proxy, with its login and API-key restrictions | Cloud container healthy; 307 to login |
| `radarr.home.arpa` | `http://10.77.0.1:19696` | Root redirect to `/radarr/`; preserve that prefix; reject paths outside it | Active cloud Radarr healthy; private gateway returned 401 |
| `sonarr.home.arpa` | `http://10.77.0.1:19696` | Root redirect to `/sonarr/`; preserve that prefix; reject paths outside it | Active cloud Sonarr healthy; private gateway returned 401 |
| `prowlarr.home.arpa` | `http://10.77.0.1:19696` | Preserve paths, but deny the sibling `/radarr` and `/sonarr` routes on this hostname | Cloud container healthy; private gateway returned 401 |
| `sabnzbd.home.arpa` | `http://10.77.0.1:18080` | Existing authenticated private proxy | Cloud container healthy; private gateway returned 401 |
| `catalog.home.arpa` | `http://192.168.1.66:1337` | NAS selective-copy dashboard; preserve paths and authentication | NAS container healthy; HTTP 200 |
| `printer.home.arpa` | `http://hass.home.arpa:8099` | Preserve `/bb` entry redirect and all service paths | HA add-on started; root returned 302 to `/bb` |
| `tinyurl.home.arpa` | `http://hass.home.arpa:4100` | Preserve UI and short-link paths | HA add-on started; HTTP 200 |
| `ha.home.arpa` | `http://hass.home.arpa:8123` | Core UI/API; configure the exact trusted proxy source before rollout | HA Core HTTP 200; proxy trust not changed |

The first group to implement should be Jellyfin/Moonfin, Plex, Seerr, the active
Arr services, SABnzbd, catalog, printer and TinyURL. Home Assistant itself needs
an explicit trusted-proxy configuration change and login/WebSocket verification.

The Arr gateway's 401 responses are the expected unauthenticated Basic Auth
challenge, not proof of a successful application login. Preserve that gate and
the applications' own authentication. The Home Assistant SSH environment also
reached the private cloud endpoints: Seerr returned 307 and SAB/Radarr/Sonarr
returned 401. Verify again from the actual proxy during rollout.

## Two distinctions that affect the names

**Active Arr services are on the cloud host, not the NAS.** Their application
ports are loopback-only: Radarr 7878, Sonarr 8989, Prowlarr 9696 and SABnzbd 8080.
Keep using the accepted VPN-facing authenticated proxies above; do not publish
the raw backend ports. There is also a running Radarr add-on on Home Assistant
at port 7878. Its login responds, but this inventory does not establish its
purpose or authorize retiring it. Reserve `radarr-ha.home.arpa` for that instance
if it still needs a separate bookmark. The unqualified `radarr` name should go
to the active cloud acquisition service.

**Moonfin Web is a Jellyfin plugin/client entry point.** It is not another
container or port. Both proposed names reach the same Jellyfin account system;
browsers may keep separate sessions for the two origins. For a single-origin
alternative, use `jellyfin.home.arpa/Moonfin/Web/` and make the `moonfin` name a
redirect to that canonical URL. Native Moonfin clients should use the Jellyfin
server root, not `/Moonfin/Web/`. No Seerr authentication mode migration is needed.

## Existing names and separate work

| Name | Destination / current role |
| --- | --- |
| `grid-dashboard.home.arpa` | Existing proxy to `hass.home.arpa:3000`; HTTP 200 |
| `wiki.home.arpa` | Existing NAS static server on port 80; HTTP 200 |
| `hass.home.arpa` | HA host alias; direct services retain their ports |
| `git.home.arpa` | Separate Git-hosting rollout: explicit proxy route to NAS port 3003; backend login returned 200 |
| `git-ssh.home.arpa` | Separate Git-hosting rollout: NAS SSH service on port 2222, not an HTTP proxy route |

Git-host DNS acceptance and backup work belong to that separate rollout; this
inventory does not mark them complete or modify them.

## Defer or keep existing access

| Service | Observed state / port | Recommendation |
| --- | --- | --- |
| HA Radarr | Started; `192.168.1.163:7878`, login 302 | Optional `radarr-ha.home.arpa`; never confuse it with the cloud owner |
| Sonos API | Started; `hass.home.arpa:5006`; `/sonos/zones` returned 200 | Optional `sonos-api.home.arpa`; an API, not a separate household UI |
| Snapshot service | Started; `hass.home.arpa:4010`; `/healthz` returned 200 | Keep direct/internal access unless a named API endpoint is useful |
| QTS NAS administration | Native HTTP 8080 returned 200; HTTPS listener 443 | Defer `nas-admin.home.arpa` until HTTPS/backend certificate handling is reviewed |
| HA UniFi application | Started; HTTPS 8443, plus device/portal ports | Defer `unifi-ha.home.arpa`; the active gateway controller is a different service |
| HA AdGuard, Z-Wave JS, ESPHome, Tailscale, Terminal & SSH, Piper | Started with HA ingress; several ports unpublished/dynamic | Keep HA ingress; do not bypass its authentication with direct proxy routes |
| NAS AdGuard administration | Resolver healthy; admin bound to `127.0.0.1:3001` | Keep loopback administration and dedicated SSH access |
| Filex | Cloud service running; existing pinned SSH tunnel at `127.0.0.1:15213` | Keep the tunnel and certificate trust; no new LAN route |
| Whisparr | HA add-on stopped; configured port 6969 | No live alias or start action proposed |
| Node Sonos HTTP API | Stopped; retained port 5005 | No alias; active service is Sonos API on 5006 |
| Matter Server / SONOFF flasher | Stopped | No live aliases |
| MongoDB, MQTT, Whisper, multiprotocol, SFTP, SSH, SMB/NFS, iperf, DNS | Data/discovery/device protocols or background services | Outside HTTP hostname routing |

No running Lidarr, Readarr or Bazarr container/add-on was found on the inventoried
NAS, HA or cloud host. Do not create aliases to assumed default ports.

## Rollout details and acceptance

1. Add one explicit hostname route and test with `curl --resolve` before DNS.
   Use Caddy's host/port upstream plus explicit path matchers; a table entry with
   a URL prefix is not a literal `reverse_proxy` upstream containing that path.
2. Preserve the current Arr `/radarr` and `/sonarr` base URLs. Their friendly
   entry URLs will show those paths after the root redirect. Removing the paths
   is a separate application/base-URL and cloud-gateway migration; blindly
   prepending or stripping prefixes can break assets, API requests and redirects.
3. For Jellyfin/Moonfin, configure the exact proxy address as a known proxy and
   preserve WebSockets, streaming/range requests and original paths. Disable
   URL-bearing access/error logs on the media proxy: Jellyfin can put credentials
   in query strings. Do not copy media responses or playback URLs into Git.
4. For Home Assistant, enable forwarded-client handling and trust only the
   verified proxy source address. Do not trust an entire LAN just for this alias.
5. Verify login/logout, redirects that retain the friendly origin, static assets,
   WebSockets where used, and representative user-approved playback. TinyURL's
   generated public links and Jellyfin's Seerr menu link need separate review;
   existing saved client/server addresses are not automatically rewritten.
6. Publish exact DNS records through the existing manual-record transaction,
   preserving current discovered records and authentication boundaries. Verify
   A/AAAA/local negatives through both resolvers and the gateway, then normal
   browser access. Keep direct ports, HA ingress, and numeric recovery available.

Initial simultaneous NAS probes timed out for Jellyfin, Moonfin, catalog and
wiki during other NAS work. Sequential bounded rechecks succeeded (302/200/200/200),
and the corresponding containers reported healthy. This is point-in-time reachability,
not a load test, playback test or proof that every VLAN can access these services.

Evidence: selected HA add-on metadata, NAS/container listener metadata, cloud
container status/bindings, and unauthenticated HTTP status/redirect probes.
Response bodies were discarded; no content catalogs or queue items were read.
Private raw operational evidence remains under ignored `build/service-inventory/`.

References: [DNS and proxy operations](home-dns.md),
[private cloud interfaces](../../usenet-infra/docs/lan-ui.md),
[Jellyfin/Moonfin deployment](../../usenet-infra/docs/jellyfin-trial.md),
[Jellyfin reverse proxy requirements](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/),
[HA HTTP proxy requirements](https://www.home-assistant.io/integrations/http/),
[Radarr URL Base](https://wiki.servarr.com/radarr/settings).
