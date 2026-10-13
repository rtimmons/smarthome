# Household DNS operations

## Design and rollout status

The desired resolvers are existing Home Assistant AdGuard (`192.168.1.163`) and
an independent NAS AdGuard (`192.168.1.66`). Both serve the repository's local
policy; neither forwards to the other. The wiki record is `wiki.home.arpa` →
`192.168.1.66`. Unknown names in `home.arpa` must be answered locally.

The October 9 preflight found AdGuard running on Home Assistant, NAS TCP/UDP 53
available specifically on its LAN address, and trusted-LAN DHCP using automatic
gateway DNS. A stored Home Assistant DNS address was disabled. These observations
are not a completed cutover. See the implementation/acceptance record in
[wiki-plan.md](../../wiki-plan.md) for subsequent verification.

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

The DHCP cutover is still pending authenticated UniFi access. Default-network
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
