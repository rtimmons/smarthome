# Household DNS operations

## Design and rollout status

Accepted **October 22, 2026**: trusted clients use gateway `192.168.1.1` for DNS.
The Max has two active native **Forward Domain** policies for `home.arpa`,
targeting HA AdGuard `192.168.1.163` and NAS AdGuard `192.168.1.66`. Both
resolvers remain running and required, with independent public upstreams.

AdGuard owns `wiki.home.arpa` → `192.168.1.66`,
`hass.home.arpa` → `192.168.1.163`, and local negative answers.
Unknown local names stay local. Bonjour host records can be discovered and
reconciled with the command below.
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

## Bonjour hostname import

Before automatic operation is enabled, the trusted-LAN Mac can run
`just dns-discover` to preview discovered hostnames, then
`just dns-discover --apply` for a one-shot import. Once the NAS owns updates,
manual apply is refused; preview compares with the current NAS inventory.
The command enumerates Bonjour service types, extracts SRV target hostnames,
and resolves their IPv4 addresses. Service display names and TXT metadata are
not saved. A host such as `fixture-device.local` becomes
`fixture-device.home.arpa`; application ports and Bonjour service discovery
remain unchanged. Only single-label, DNS-safe hostnames with exactly one
address in `192.168.1.0/24` are imported. Multiple interfaces advertising the
same address are deduplicated; hosts with multiple LAN addresses are skipped.
A previously learned ambiguous name is withdrawn rather than left misleading.

Manual records, including `wiki` and `hass`, always take precedence.
`policy.json` records ownership and last-seen timestamps under `mdns_records`.
Later successful apply runs update changed addresses and remove discovered
records unseen for seven days. An empty or failed discovery aborts; it never
clears the zone. A missing device is not proof it has left the network.
Discovery only covers advertisements visible to this Mac and can miss sleeping
or isolated devices. The initial Mac command is a bounded preview/import. Automatic operation now
uses the NAS service described below; its scans perform refresh and expiry.

Apply retains the previous policy privately, uses the existing paired resolver
deployment and rollback checks, then writes the accepted desired policy.
Unchanged rules avoid resolver deployment. Private previews and snapshots live
under `build/wiki-private/`; the preview contains host addresses, not service
metadata. Review source changes and publish the updated wiki after a record
change. `just dns-test` exercises parsing, conflicts, manual ownership,
address changes, grace expiry and DNS answer validation without LAN access.

October 24 acceptance: the initial import added 31 discovered hostnames alongside
both manual aliases. All 33 names passed exact A, empty AAAA, unknown-subdomain,
zone-negative and public-resolution checks over UDP/TCP through each AdGuard
and the gateway. One host advertising multiple LAN addresses was skipped.
The NAS resolver was running and healthy after deployment. This establishes
name resolution, not application compatibility or every VLAN's discovery coverage.

## Automatic NAS discovery

`just dns-auto-deploy` installs or updates the separate `home-dns-discovery`
Compose project on the NAS. It starts on boot through `restart: unless-stopped`
and scans the trusted LAN about once a minute, independently of the Mac.
New advertisements are normally imported within one or two minutes; a full
DNS validation or recovery can take longer. Only advertisements visible on the
NAS trusted-LAN interface are eligible. It is not a DHCP/all-VLAN inventory.

The scanner uses host networking for mDNS and loopback access to NAS AdGuard.
It is non-root, drops all capabilities, has a read-only root filesystem, no
Docker socket, and no HTTP server or new administration port. The image
recreates source-file bytes to strip inherited QNAP ACLs; ordinary chmod alone
was insufficient. Deployment tests application and dependency imports as the
configured non-root user before starting the scanner. Source lives in
`dns/runtime/automatic`, credentials in `dns/config/automatic`, and learned
policy, health and recovery journal in `dns/backups/automatic-state`, relative
to the NAS application root. These paths fall inside existing DNS backup scope.
The dedicated `Household DNS Discovery` Home Assistant token is private and
also retained under ignored `build/wiki-private/` on the Mac. Its permission
comes from the provisioning account; it is not a DNS-only Home Assistant token.
The NAS password is the existing loopback-only resolver administration credential.
No SSH access key is copied to the scanner.

Updates change only AdGuard custom rules through authenticated APIs, secondary
then primary, without restarting either resolver. Manual aliases stay pinned.
Every changed generation is validated through both resolvers and the gateway
over UDP/TCP, including A, empty AAAA, local negatives and public resolution.
A failed update attempts to restore the prior rules on both. A durable pending
journal recovers interruption between writes. Unexpected custom rules, extra
rewrites or disabled filtering pause updates instead of overwriting drift.
Empty/failed scans preserve existing records; seven-day expiry requires a
successful scan. Service display names, TXT data and credentials are not logged.

Use `just dns-auto-status` to read last-scan health and counts, and
`just dns-check` to check the live runtime inventory rather than the initial
repository snapshot. `just dns-auto-stop` stops only discovery and retains
both resolvers and their last accepted names. `just dns-auto-deploy` resumes it.
The repository policy remains the initial seed plus an automatic-ownership
marker; runtime host churn does not modify Git files. Static deploy, one-shot
apply and manual primary rollback refuse to compete with automatic ownership.
For deliberate manual policy changes or recovery, stop the scanner first,
retain its runtime policy/journal, reconcile the accepted generation with both
resolver rule lists, then resume. Do not replay the older seed over learned
state or clear a pending journal merely to suppress an error.

October 24 automatic acceptance: the NAS scanner started healthy with 34 records.
A new synthetic Bonjour hostname advertised after startup appeared on both
AdGuards and the gateway in 70 seconds without a manual import. After its
accepted runtime generation completed, the synthetic record was removed and
all remaining DNS records plus negative/public checks passed over UDP/TCP.
Discovery was resumed; neither resolver was restarted for these updates.

## Cabin / Lehigh coverage — pending acceptance

Site Magic advertises Newark `192.168.1.0/24` and Lehigh `192.168.8.0/24`.
On October 24, a Newark-side probe reached Lehigh's gateway `192.168.8.1`
and a DNS query directed to that address returned `wiki.home.arpa` as
`192.168.1.66`. This does not establish Lehigh's effective forwarding policy,
exclude DNS interception along the path, or prove cabin clients can resolve
names and reach the applications. No Lehigh configuration was changed.

The NAS scanner currently accepts only Newark `192.168.1.0/24` addresses and
listens on `192.168.1.66`. Lehigh hostname discovery is **not implemented**.
Before extending it, inspect the Lehigh controller and identify a persistent
discovery source on that LAN. Adding its subnet to an address allowlist alone
does not provide remote multicast observations. Preserve manual aliases and
handle duplicate hostnames across sites without overwriting either host.

Remaining acceptance: inspect Lehigh DNS forwarding to both AdGuards, test
UDP/TCP DNS and application access from a Lehigh client, then validate a new
Lehigh hostname and its removal through the automatic discovery workflow.
Keep the superseded manual VPN peers paused and printer-network restrictions
intact. Browser inspection was blocked by the locked Mac; the connected UniFi
MCP controller currently exposes Newark only.
