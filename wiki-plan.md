# Smarthome wiki expansion

## Approved design

Expand the Usenet guide into a household and maintenance wiki at
**http://wiki.home.arpa**, hosted on the existing QNAP. Keep numeric recovery at
http://192.168.1.66/ and the original http://192.168.1.66:8090/ Usenet entrance,
including fragment links. Use HTTP without a wiki login; existing application
shortcuts retain their authentication. No WAN publication or new VPN.

### Content and ownership

Use a root `wiki/` MkDocs project with Markdown, a customized built-in theme,
local assets and offline-capable search. Cover start-here tasks, dashboard and
LED wall, lighting and automation, Sonos, climate/cameras/integrations, printing,
TinyURL/MongoDB, media/storage, networking, and maintenance/recovery.

Keep operational runbooks canonical and import only selected sources. Convert the
Usenet HTML explanations and diagrams to Markdown, retaining anchors. Each guide
explains purpose, dependencies, configuration ownership, usage, troubleshooting,
and recovery, distinguishing desired configuration and dated live evidence.

A component catalog owns pages and watched configuration paths. Generate service
facts from add-on manifests and devices/scenes/room groupings from the TypeScript
model. Preserve removed devices, scene exclusions and disabled services. These
are **repository configuration**, never an assertion of live availability.

Publish only allowlisted documents/fields. Exclude credentials, private inventory,
logs, media identities and raw state. Show source revision, working-tree status,
build time and separate review dates; rebuilding does not renew verification.
The website remains static and cannot call operational APIs.

### Hosting and DNS

Retain the `usenet-wiki` Compose project and `/share/Container/usenet/wiki` root.
Publish NAS `192.168.1.66:80` to an unprivileged container port, retaining 8090.
Leave existing HTTPS untouched. Retain non-root execution, read-only mounts,
resource limits, checksummed releases, health checks and automatic rollback.

Use existing AdGuard Home at `192.168.1.163` and independent NAS AdGuard at
`192.168.1.66`, TCP and UDP 53 bound specifically to the NAS LAN address. Maintain
matching local records, filtering and independent upstream policy. Resolve
`wiki.home.arpa` to the NAS and answer unknown `home.arpa` names locally.
Separate DNS configuration/data from the wiki and keep credentials private.

Test both resolvers before using the supported UniFi interface to advertise both
through Default-network DHCP. Do not advertise public fallback DNS. Preserve the
restricted printer network. Pilot a client; unresolved gateway DNS interception
blocks DHCP cutover. Preserve existing VPN reachability; document split DNS and
verify it separately. Keep rollback copies of prior DHCP and resolver settings.

### Freshness and publication

Require explanatory-document review or an explicit no-impact acknowledgement
against each changed source fingerprint. Generate mechanical facts automatically.
Run coverage, review, static-build, link and boundary checks locally and in CI,
without household credentials. Contributor and agent completion includes this
review. Direct device-interface changes still require intentional source updates;
checks cannot prove prose is semantically correct.

Provide `wiki-check`, `wiki-build`, `wiki-preview`, `wiki-deploy`, and
`wiki-rollback` root recipes. Keep `usenet-wiki-deploy` as an alias. DNS deployment
remains separate. Supported HA/add-on, standalone HA configuration and Usenet
deployments validate/build first, deploy components, record sanitized receipts,
then publish once after enclosing success. Nested commands and dry runs never
publish repeatedly or create misleading evidence. Retain unrelated receipts.

A wiki failure after service success is reported separately and retains the
previous site. Retry with `just wiki-deploy`; do not roll back healthy services.
No background publisher or scheduled AI maintenance is included.

## Delivery and acceptance

1. Catalog, Markdown build, generated references, checks and preview.
2. Migrate Usenet and write component guides; reconcile dated documentation.
3. Versioned static deployment, LAN port 80 and legacy entrance.
4. Independent DNS resolvers, validation, pilot and supported DHCP cutover.
5. Deployment hooks, backups and recovery instructions.
6. Record evidence here and link maintenance from the documentation index.

Acceptance covers all managed components; generated exclusions; a changed-source
freshness failure; local links/assets/search and legacy anchors; desktop/mobile;
no private inputs or API calls; DNS UDP/TCP, unknown-zone and public resolution;
either-resolver failover; fresh laptop/phone leases; numeric access; deployment
success/failure/dry-run/nesting; invalid-candidate rollback and idempotence;
printer isolation and no WAN exposure; relevant repository tests. Report known
historical secret-scan findings separately. Back up DNS and wiki configuration
and document numeric-address recovery.

## Implementation evidence

Implemented on 2026-10-09:

- MkDocs guides for all seven add-ons and the wider ecosystem, imported canonical
  runbooks, generated device/scene/service reference, local assets/search, review
  fingerprints, CI and deployment transaction hooks.
- Live QNAP port-80 wiki; legacy `8090/#storage` redirects to the correct preserved
  anchor. Desktop and 390-pixel phone layout, mobile menu and local search passed.
- Two AdGuard resolvers pass UDP/TCP wiki A, empty AAAA, unknown local names and
  public-name tests. Primary synthetic-query evidence confirms local rewriting
  without an upstream. DNS rollback was exercised while fixing startup validation.
- Backup inventory includes wiki runtime/pointers and private DNS configuration,
  including current primary policy; generated site and query history are excluded.
- Wiki unit checks and the configuration generator's 86 tests pass. Infrastructure
  suite: 476 tests pass, 9 skipped; syntax/shell checks pass. Its full scan reports
  the two already-documented historical RSA keys; no suppression was added.
- Root `just test`: Talos 121 tests and dashboard 102 tests pass. It stops at the
  two existing printer visual baselines (`bluey_meter_mode` and its long-text
  variant); 223 other printer tests pass. Later container checks were not reached.

Pending acceptance:

- Authenticated UniFi access to pilot and apply Default-network DHCP DNS. No DHCP,
  printer-network, WAN-forward or VPN setting has been changed. The requested
  hostname works through either new resolver but is not yet advertised to the LAN.
- Fresh laptop/phone leases, client failover with either resolver unavailable,
  independent VPN/split-DNS access, and a physical phone check. Phone-sized browser
  testing is not a substitute for those network checks.
Completed recovery checks:

- Repeating the accepted wiki deployment reported zero changes. UniFi’s stored
  port-forward collection was empty at verification; no WAN-forward changes were made.
- A deliberately rejected live wiki candidate restored the exact previous
  `publication.json` checksum and healthy port-80 service automatically.
- A fresh encrypted NAS configuration archive was captured and decrypted only in
  memory for verification. Required wiki/DNS configuration entries were present;
  generated site content and DNS history were absent. The scheduled NAS backup
  helper was updated without restarting household services.
- Final receipt audit found and removed a help-only test receipt. Help/version
  invocations now bypass all build/publication work, with regression coverage.
- Existing source evidence is not a claim of household service redeployment; no
  unrelated component receipt is renewed.

## References

- [MkDocs configuration](https://www.mkdocs.org/user-guide/configuration/)
- [Residential home.arpa namespace, RFC 8375](https://www.rfc-editor.org/info/rfc8375/)
- [UniFi DNS guidance](https://help.ui.com/hc/en-us/articles/15179064940439-UniFi-DNS-Records-and-Local-Hostnames)
- [Wiki maintenance](docs/operations/wiki.md)
- [Household DNS operations](docs/operations/home-dns.md)
