# Home web proxy

A small Caddy add-on with explicit mappings:

| Browser URL | Upstream |
| --- | --- |
| `http://grid-dashboard.home.arpa/` | `http://hass.home.arpa:3000/` |
| `https://git.home.rytim.com/` | `http://192.168.1.66:3003/` |
| `http://jellyfin.home.arpa/` | `http://192.168.1.66:8096/` |
| `http://moonfin.home.arpa/` | `http://192.168.1.66:8096/Moonfin/Web/` |
| `http://plex.home.arpa/` | `http://192.168.1.66:32400/web/` |
| `http://seerr.home.arpa/` | `http://10.77.0.1:15055/` |
| `https://radarr.home.rytim.com/` | `http://10.77.0.1:19696/radarr/` |
| `https://sonarr.home.rytim.com/` | `http://10.77.0.1:19696/sonarr/` |
| `https://prowlarr.home.rytim.com/` | `http://10.77.0.1:19696/` |
| `https://sabnzbd.home.rytim.com/` | `http://10.77.0.1:18080/` |
| `http://catalog.home.arpa/` | `http://192.168.1.66:1337/` |
| `http://printer.home.arpa/` | `http://hass.home.arpa:8099/` |
| `http://tinyurl.home.arpa/` | `http://hass.home.arpa:4100/` |

It binds only Home Assistant's LAN address, `192.168.1.163`, on ports 80 and
443, and accepts clients from `192.168.1.0/24`. Unknown hosts return 404; other
sources return 403. It does not trust forwarded-IP headers for access control.
HTTPS uses the renewed public Let's Encrypt certificate from the read-only SSL
mount. Caddy's admin socket is private to the container and configuration
persistence is disabled. No Docker or Home Assistant API access is granted.

Authelia checks every Arr browser request before the gateway credential is
injected. The upstream cloud gateway requires this credential and HA's actual
source IP, then strips credentials and identity headers before the app. Private
SSL state, including this credential, is retained by the encrypted identity
backup. The `.home.arpa` Git and Arr aliases redirect to canonical HTTPS names.

Host networking is intentional: binding the exact LAN interface avoids exposing
this listener on Home Assistant's other interfaces. There is no Docker port
mapping or Supervisor bridge-address TCP probe. Supervisor starts the add-on
at boot and watches its process. Verify HTTP separately after deployment.

Run from the repository root:

```sh
just --justfile home-proxy/Justfile --working-directory home-proxy deploy
```

The image build validates Caddy's configuration before starting it. Test the
friendly URL, static assets, original port-3000 URL, unknown hosts and source
restrictions. Do not exercise lighting/music controls merely as smoke tests.

See [DNS and proxy operations](../docs/operations/home-dns.md#http-service-pilot)
for the paired-DNS update and rollback procedure. The existing NAS wiki is
independent. Stopping `local_home_proxy` disables all its friendly web routes;
use the original host-and-port URLs or HA ingress during recovery. Rebuild this stateless add-on from
source during recovery; retain DNS runtime policy and resolver backups.

## Service routing and checks

Direct recovery ports retain their existing authentication. Forgejo uses OIDC;
Arr browser routes require the Authelia `arr-users` group and two factors. The Arr routes
preserve their base paths and reject sibling applications. Seerr requires its
existing numeric Host upstream; its gateway still rejects API-key headers.
Moonfin redirects only its root to the plugin web client; native clients use
the Jellyfin root. `ha.home.arpa` remains deferred and has no route or DNS record.

No access logs are enabled. HTTP request-error dumps are excluded to avoid
recording tokens in media URLs; startup/configuration diagnostics remain enabled.
Jellyfin trusts only `192.168.1.163` as the additional known proxy; remote access
and automatic port mapping remain disabled. Retain that exact network setting
when restoring Jellyfin (it is application state, outside this stateless image).

Run `just --justfile home-proxy/Justfile --working-directory home-proxy verify`
before DNS publication, then repeat with `--dns` afterward. It checks HTTP entry
points, login gates, isolation and existing routes without reading media catalogs or invoking controls. A separate
non-LAN-source check must return 403 even with a forged `X-Forwarded-For` header.
See the [service route inventory](../docs/operations/service-hostnames.md) for
acceptance details and limitations.

The isolated authentication regression suite uses synthetic services and secrets:

```sh
HOME_PROXY_RUNTIME_TEST=1 uv run --project wiki --python "$(cat .python-version)" --frozen python -m unittest discover -s home-proxy -p test_gateway.py -v
```

It verifies anonymous and denied requests, identity-service failure, API paths,
header spoofing, credential injection after authorization and sibling isolation.
