# Home HTTP proxy

A small Caddy add-on with explicit mappings:

| Browser URL | Upstream |
| --- | --- |
| `http://grid-dashboard.home.arpa/` | `http://hass.home.arpa:3000/` |
| `http://git.home.arpa/` | `http://192.168.1.66:3003/` |

It binds only Home Assistant's LAN address, `192.168.1.163:80`, and accepts
clients from `192.168.1.0/24`. Unknown hosts return 404; other sources return
403. It does not trust forwarded-IP headers for access control. TLS and Caddy's
administration API are disabled. There are no credentials, host mounts, Docker
access or Home Assistant API permissions.

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
independent. To disable this pilot, stop `local_home_proxy` and continue using
`http://hass.home.arpa:3000/` or HA ingress. Rebuild this stateless add-on from
source during recovery; retain DNS runtime policy and resolver backups.
