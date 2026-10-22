# Household DNS operations

## Design and rollout status

The existing dual-resolver design uses Home Assistant AdGuard (`192.168.1.163`) and
an independent NAS AdGuard (`192.168.1.66`). Both serve the repository's local
policy; neither forwards to the other. The wiki record is `wiki.home.arpa` →
`192.168.1.66`. Unknown names in `home.arpa` must be answered locally.

The October 9 preflight found AdGuard running on Home Assistant, NAS TCP/UDP 53
available specifically on its LAN address, and trusted-LAN DHCP using automatic
gateway DNS. A stored Home Assistant DNS address was disabled. These observations
are not a completed cutover. See the implementation/acceptance record in
[wiki-plan.md](../../wiki-plan.md) for subsequent verification.

### October 16 DNS status and October 22 gateway cutover

Read-only checks on **2026-10-16** passed the repository's full UDP/TCP DNS checks
against both AdGuard addresses: wiki A, empty wiki AAAA, unknown local names,
zone apex, and public A resolution. This Mac's active resolver was still
`192.168.1.1`, with search domain `localdomain`; its normal `wiki.home.arpa`
lookup returned `NXDOMAIN`. This confirms the client-path gap on this Mac, not
the DHCP configuration or behavior of every LAN client. No settings changed.
The repository policy currently assigns only `wiki.home.arpa`; arbitrary device
names have not yet been added.

The **Cloud Gateway Max NS (US Version), UCG-Max-NS**, arrived and took over
routing and Network management on **October 22**. Ryan confirmed the switch and
both APs online. The Mac's public DNS query through `192.168.1.1`, Internet HTTPS,
Home Assistant, and numeric wiki access passed. Local-name resolution and the
DNS/filtering design were not changed or accepted during that cutover.
The [migration record](unifi-network-setup.md#cloud-gateway-max-migration)
lists the remaining baseline checks. The later forwarding-only hybrid acceptance below keeps AdGuard record
ownership and both resolvers running. The direct-AdGuard DHCP procedure below
remains an alternative requiring its own rollout and rollback checks.

### Accepted gateway-forwarding hybrid — October 22

The resumed Mac session verified the native pilot through Safari and direct
DNS checks. The duplicate native `wiki.home.arpa` A record caused the gateway
to return empty `NOERROR` for the zone apex instead of the required `NXDOMAIN`.
Pausing that record corrected the response without weakening the tests. The
policy remains saved but **paused**, available for rollback.

The active native **Forward Domain** policy sends `home.arpa` to HA AdGuard
at `192.168.1.163`. AdGuard remains the owner of `wiki.home.arpa` →
`192.168.1.66` and local negative answers. Both AdGuards remain running and
passed their exact direct checks. The gateway passes the same full contract
over UDP/TCP: exact wiki A, empty AAAA, unknown names/subdomains, NXDOMAIN at
the apex and public resolution. A fresh synthetic unknown query sent through
the gateway appeared in HA AdGuard as a local `RewriteRule` with no upstream.
The returned fresh Mac wireless lease advertises gateway DNS, and ordinary
wiki-by-name HTTP returns 200. A later check from Home Assistant as a second
trusted host queried the gateway directly: the wiki A answer matched, and the
apex SOA and a fresh unknown local name returned `NXDOMAIN`. That used the
host's ordinary DNS client; the full UDP/TCP matrix remains the separate
repository check. These observations do not establish every VLAN or browser
encrypted-DNS override.

Default's native Ad Block remains enabled, with categories Off and Safe Search
disabled. `doubleclick.net` returns `0.0.0.0` through the gateway over UDP/TCP.
No DHCP settings or AdGuard filter/upstream rules changed. This initial hybrid
used the gateway as trusted-client resolver and **one** local-zone forwarder.
The subsequent dual-forwarder acceptance below replaces that single-forwarder
limitation. Both AdGuards remain required and running.

`network-infra/dns/policy.json` and the generated wiki reference now record
the client resolver, AdGuard record ownership, forwarding targets and paused
native A policy. The native settings remain UI-owned. Preserve both AdGuard
backups and the accepted Max System export, including the forwarding policy.
Keep the paused native A as historical pilot rollback material. Resuming it
reproduces the known apex mismatch; normal recovery keeps it paused and
preserves domain forwarding and both resolvers.

`just dns-check --resolver 192.168.1.1` checks the gateway without an AdGuard
administration session. Repeat `--resolver` for multiple candidates; the default
command still checks both AdGuards. DNS replies alone do not prove containment;
retain the separate synthetic-query evidence described above.

### Automatic local-zone failover — October 22

The Max now has **two active Forward Domain policies for `home.arpa`**, one
targeting HA `192.168.1.163` and one targeting NAS `192.168.1.66`. The supported
native UI accepted both policies for the same zone. The duplicate native wiki
A remains paused. Trusted DHCP still advertises only the gateway `192.168.1.1`;
native ad blocking and the printer restrictions are unchanged. This is native
gateway resolver selection, with no new monitoring daemon or public fallback.
The list order does not promise a preferred server or immediate failback.

The associated Mac exercised each resolver outage without stopping either
AdGuard. Each service's existing access lists were captured privately, then
only the gateway's `192.168.1.1` DNS requests were temporarily denied at one
resolver. The other resolver remained available, and both services reported
running throughout. Exact original access lists were restored in `finally`,
with an independent restoration watchdog. The NAS administration API used its
existing pinned SSH command path; SSH port forwarding remained prohibited.

With either resolver unavailable to the gateway, all fourteen client DNS checks
passed over UDP/TCP: exact wiki A, empty AAAA, fresh unknown local names and
subdomains, apex NXDOMAIN, public A and an ad-domain block. Cold positive checks
waited beyond the observed ten-second rewrite TTL. The Mac's ordinary system
resolver and HTTP client reached `http://wiki.home.arpa/` at `192.168.1.66`
with HTTP 200 in each outage. Native LAN capture confirmed requests from the
gateway to the denied resolver received no answer, while the surviving resolver
answered the fresh synthetic names and the wiki A/AAAA questions. Backend wire
queries used UDP; both client transports were tested separately.

With both backends denied to the gateway, fresh local names failed closed:
the UDP probe timed out after six seconds and TCP returned `REFUSED`. Neither
was accepted as a successful local DNS answer. Public resolution and ad blocking
still passed. The WAN capture contained zero `home.arpa` DNS packets while a
fresh public-zone control below `iana.org` produced three outbound questions
and three answers. The public control proves the capture could observe DNS
egress during this test. After exact access-list restoration, the full contract
and ordinary wiki-by-name HTTP 200 passed automatically, with no client resolver
or DHCP changes. Both AdGuards reported running after every phase and at closure.
The drill covered fifty accepted DNS questions plus application checks; raw
captures, prior attempts and restoration receipts remain private.
The final full Max System export (167,744 bytes) was encrypted off-device and
authenticated-decryption verified. Preserve it and all earlier exports; the
AdGuard protection, upstreams, local rules and original access lists were
verified unchanged after the drill.

Both resolver access lists and services must be healthy after a drill. For a
future repeat, preserve `/control/access/list`, temporarily add only the gateway
to `disallowed_clients` using `/control/access/set`, and restore the exact
captured lists with a deadline/watchdog. Refuse conflicting pre-existing
allowlists or concurrent changes rather than overwriting them. Keep protection,
filtering, upstreams and both daemons unchanged. Store raw captures and API
snapshots privately; publish only scoped synthetic-query evidence.

To roll back this change, inspect the target address and pause only the new
NAS-targeting `home.arpa` policy in the native UI. Retain the HA policy and
paused native A. This restores the former single-forwarder limitation. If both
backends are unavailable, use numeric recovery addresses and repair a backend;
never add a public fallback for the private zone. Both AdGuards remain necessary
for this accepted redundant design and must not be retired.

## Configuration ownership

`network-infra/dns/policy.json` owns the wiki record and desired local-zone rules.
The deployment workflow captures the primary's existing upstream and filter
policy privately before configuring the secondary. Keep credentials, full
AdGuard configuration, filter/account tokens, and rollback copies outside Git.
Never copy query history, client browsing data, or household secrets into the wiki.

The secondary DNS service has its own configuration and state directories under
the NAS application root. Its administration endpoint binds only to loopback and
is reached through the dedicated NAS SSH identity. The wiki cannot access it.
Existing QNAP listeners on loopback and container bridge addresses remain intact.

## Cutover and rollback

Before changing DHCP, test both resolvers over UDP and TCP, including the wiki A
record, an unknown `home.arpa` name, and ordinary public resolution. Verify each
resolver's upstream path is independent and local requests cannot escape it.
Pilot one client using both resolvers before changing network-wide DHCP.

Use the supported UniFi interface to set Default-network DNS to the two local
addresses. Do not write the controller database, configure a public fallback,
change the restricted printer network, or silently disable unrelated filtering.
Verify fresh leases actually use the intended resolvers, including with either
resolver unavailable. Preserve the prior DHCP fields and DNS configurations.

If verification fails, restore the captured DHCP settings through the same UI
and restore each resolver's saved configuration. Restore the old resolver before
removing any address clients still have in their leases. Wiki recovery uses
`http://192.168.1.66/` or the retained port-8090 entrance.

## Backup and recovery

The NAS settings backup must include the secondary DNS configuration, runtime
definition, and private rollback material, but exclude DNS query/statistics data.
Primary policy snapshots are included in the NAS archive. A complete primary restore also needs a native Home Assistant backup explicitly containing `a0d7b954_adguard`; the seven repository-add-on partial backup does not include it. Capture a fresh
backup after accepted changes and verify the archive's configuration entries.
An untested archive is not proof of a replacement-host restore.

## Boundaries

This is trusted-LAN unicast DNS. `.local` discovery is a separate protocol.
Clients with hard-coded public DNS or encrypted DNS can bypass DHCP and need
their own configuration. Existing VPN transport remains unchanged; private-name
resolution over a VPN requires a working DNS route and separate verification.

## Commands and accepted resolver checks (2026-10-09)

Run `just dns-check` to test both resolvers over UDP and TCP. It requires the
controller's `dig` utility and does not change anything. `just dns-deploy`
reconciles the reviewed policy, saves private snapshots, deploys the secondary,
then updates primary custom rules only after secondary validation. It refuses
unreviewed primary upstream/filter drift. It uses the existing HA authenticated
Supervisor ingress API; session tokens remain in memory.

The secondary runs AdGuard Home 0.107.79, matching the inspected primary engine.
Its derived image removes upstream file capabilities so it can run as the
non-root NAS deployment user with no Linux capabilities, listening on 1053 inside
the container. Host publication supplies LAN TCP/UDP 53. Administration is
password-protected and bound to NAS loopback port 3001. Generated credentials
and full snapshots are private; query logging/statistics are disabled on the NAS.

Accepted checks: wiki A record, empty wiki AAAA, unknown local names (including
below `wiki.home.arpa`), the zone apex, and ordinary internet A resolution all
passed over UDP and TCP against each resolver. Primary synthetic-query evidence
recorded local `RewriteRule` handling with no upstream. This also demonstrates
that the tested controller path was not transparently replaced by gateway DNS.
It does not establish that every client or VLAN follows the same path.

Direct-AdGuard DHCP cutover remains an unselected alternative after the accepted
gateway-forwarding hybrid. Do not run the following optional cutover merely
to complete the historical plan. Default-network
DHCP previously used automatic/gateway DNS (`dhcpd_dns_enabled: false`), with
`192.168.1.163` stored in the first disabled manual field. Before saving, capture
the current form and all manual fields privately. Set only this network's DNS
servers to `192.168.1.163` and `192.168.1.66`. Pilot, renew a laptop and phone lease,
and verify both normal use and either-server failover before accepting cutover.
To roll DHCP back, restore Automatic DNS and the captured fields, then renew
leases. The printer network must remain unchanged.

Primary rollback: `just dns-rollback-primary /absolute/path/to/dns-before-*.json`
restores the saved custom-rule list. Private snapshots are under
`build/wiki-private/` and `/share/Container/usenet/dns/backups/` on the NAS.
For the secondary, retain `secondary-<timestamp>.tgz`. After restoring DHCP and
allowing old leases to expire, stop only the `home-dns` resolver, extract the
chosen archive into the DNS root, and run its Compose definition with
`up -d --force-recreate --wait resolver`. Automatic deployment failure recovery
uses this same configuration/runtime restoration. Never stop either advertised
resolver simply to clean up snapshots.

Source syntax: [AdGuard DNS filtering rules](https://adguard-dns.io/kb/general/dns-filtering-syntax/).
Exact-name exceptions matter: allowing all subdomains of the wiki would leak
unknown local names upstream. The checked policy has no such exception.
