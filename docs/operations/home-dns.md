# Household DNS operations

## Design and rollout status

Accepted **October 22, 2026**: trusted clients use gateway `192.168.1.1` for DNS.
The Max has two active native **Forward Domain** policies for `home.arpa`,
targeting HA AdGuard `192.168.1.163` and NAS AdGuard `192.168.1.66`. Both
resolvers remain running and required, with independent public upstreams.

AdGuard owns `wiki.home.arpa` → `192.168.1.66`,
`hass.home.arpa` → `192.168.1.163`, and local negative answers.
Unknown local names stay local; arbitrary device records have not been added.
The native wiki A policy is saved but **paused**: enabling it caused empty
`NOERROR` at the zone apex instead of required `NXDOMAIN`. Keep it paused.
Default's existing native Ad Block remains on; categories and Safe Search are
off. The [generated policy](../../network-infra/dns/policy.json) records this
hybrid. Native forwarding/filter settings are UI-owned; DHCP is unchanged.

### Accepted gateway-forwarding hybrid — October 22

Gateway and both direct resolvers passed the exact UDP/TCP contract: wiki A
exactly `192.168.1.66`, empty wiki AAAA, unknown local names/subdomains and apex
`NXDOMAIN`, plus public A resolution. A synthetic unknown gateway query was
handled locally by AdGuard without an upstream. Gateway ad blocking returned
`0.0.0.0` for the tested ad domain over UDP/TCP.

A fresh Mac Wi-Fi lease used gateway DNS and ordinary wiki-by-name HTTP returned
200. HA provided a second trusted-host check for wiki A and local negatives.
These checks do not establish every VLAN or browser encrypted-DNS override.

### Automatic local-zone failover — October 22

The gateway selects between the two forwarders automatically; policy order
does not promise a preferred server or immediate failback. Each-backend outage,
both-down containment and recovery passed without stopping either AdGuard:

| Phase | Accepted evidence |
| --- | --- |
| Either backend unavailable | Fourteen client UDP/TCP checks passed, cold wiki answers and normal system resolution/HTTP 200 worked; LAN capture showed the survivor answering and no reply from the denied backend |
| Both unavailable | Fresh local UDP timed out and TCP returned `REFUSED`; public resolution and ad blocking still worked; WAN capture had no `home.arpa` DNS and observed a fresh `iana.org` public control |
| Restored | Exact original access lists/configuration and running services verified; full DNS contract and wiki HTTP 200 recovered without client/DHCP changes |

Cold positive checks waited beyond the observed ten-second rewrite TTL.
Backend capture queries used UDP; client UDP and TCP were tested separately.
The drill covered fifty accepted DNS questions plus application checks. Raw
captures, prior attempts and restoration receipts remain private under
`build/unifi-dns-failover-20261022/`; verified encrypted Max exports are retained.

For a future drill, capture each resolver's `/control/access/list` privately.
Temporarily add only the gateway to `disallowed_clients` with
`/control/access/set`; keep protection, upstreams, filters and both daemons
unchanged. Refuse conflicting allowlists or concurrent edits. Restore the exact
captured lists in `finally`, with an independent deadline/watchdog, and verify
services and configuration afterward. NAS administration uses its existing
pinned SSH command path; port forwarding remains prohibited.

## Configuration ownership

`network-infra/dns/policy.json` owns local records and desired AdGuard rules.
`just dns-deploy` captures private snapshots, deploys/validates the secondary,
then updates primary custom rules. It refuses unreviewed primary upstream/filter
drift and uses HA's authenticated Supervisor ingress with tokens in memory.
Keep credentials, full configuration and rollback copies outside Git; never
publish query history or client browsing data.

For a record change, retain the reviewed previous `policy.json` in ignored
`build/` before editing, then deploy with
`just usenet dns deploy --previous-policy /absolute/path/to/previous-policy.json`.
This permits replacement of that exact previous custom-rule list while retaining
the upstream/filter drift checks. Checks cover every configured name's A and
empty AAAA answers and reject unknown subdomains. Home Assistant is available at
`http://hass.home.arpa:8123/`; DNS does not change its listening port.

The NAS resolver has separate configuration/state directories under the NAS
application root. Its non-root image listens internally on 1053, publishing
LAN TCP/UDP 53. Password-protected administration binds to loopback port 3001
and uses the dedicated NAS SSH identity. NAS query logging/statistics are off;
existing QNAP loopback/bridge listeners and wiki isolation remain intact.

## Cutover and rollback

Normal recovery keeps gateway DHCP DNS and repairs a backend. If both fail,
use **http://192.168.1.66/** or port 8090. To reverse dual forwarding, pause
only the NAS-targeting native policy, retaining HA forwarding and the paused
native A; this restores the former single-backend dependency. Never use a
public fallback for `home.arpa` or retire either resolver in the accepted design.

Direct-AdGuard DHCP is an **unselected alternative**, not pending migration
work. If deliberately chosen later, first capture Default's current DHCP fields
and validate both independent resolvers/containment. Pilot a client, then use
the supported UniFi UI to advertise both `192.168.1.163` and `192.168.1.66`, with fresh client
leases and either-server failover checks. Preserve printer settings and native
DNS interception/filtering behavior. Roll back by restoring the captured
Automatic DNS/manual fields and renewing leases; never remove a resolver still
advertised in outstanding leases.

Primary rule rollback:

```sh
just dns-rollback-primary /absolute/path/to/dns-before-*.json
```

Snapshots remain in `build/wiki-private/` and
`/share/Container/usenet/dns/backups/`. For secondary recovery, retain
`secondary-<timestamp>.tgz`. After removing it from client/gateway service and
allowing affected leases to expire, stop only `home-dns`, restore the chosen
configuration/runtime archive, then run its Compose definition with
`up -d --force-recreate --wait resolver`. Deployment-failure recovery uses the
same restoration. Do not stop an advertised resolver to clean up snapshots.

## Backup and recovery

NAS settings backups include secondary configuration/runtime and private primary
policy snapshots, excluding query/statistics data. A complete HA primary restore
also needs a native HA backup explicitly containing `a0d7b954_adguard`; the
seven repository-add-on partial backup does not include it. Capture and verify
fresh configuration archives after accepted changes. Readback is not proof of
a replacement-host restore.

## Boundaries

This is trusted-LAN unicast DNS. `.local` is separate mDNS discovery. Hard-coded
public/encrypted DNS can bypass DHCP and needs client-specific checks. VPN
private-name resolution needs its own verified DNS route.

<a id="commands-and-accepted-resolver-checks-2026-10-09"></a>

## Commands

```sh
just dns-check
just dns-check --resolver 192.168.1.1
```

The default checks both AdGuards; explicit `--resolver` checks the selected
endpoint without an AdGuard administration session. Repeat the option for
multiple targets. Checks require `dig` and do not change configuration; packet
containment and real-client failover need the separate drill above.

Exact-name exceptions matter: allowing every subdomain of the wiki would leak
unknown local names upstream. See [AdGuard rule syntax](https://adguard-dns.io/kb/general/dns-filtering-syntax/).
