# Smarthome wiki handoff

## Current state — October 22, 2026

The household wiki is deployed at **http://wiki.home.arpa/** on the QNAP.
Numeric recovery is **http://192.168.1.66/**; the original port-8090 entrance
and legacy fragment redirects are retained. The Max migration, gateway DNS
forwarding, automatic AdGuard failover and SSH access are accepted in the
[network follow-up](docs/operations/unifi-post-migration.md).

Both AdGuards remain required. Clients use gateway DNS; direct-AdGuard DHCP
is an unselected alternative, not pending rollout work. See
[DNS operations](docs/operations/home-dns.md) for failure drills and recovery.

## Ownership and publishing

- Household explanations live in `wiki/content`; imported operational runbooks
  remain canonical. `wiki/components.json` owns coverage and review fingerprints.
- Generated references describe repository configuration. Dated acceptance and
  deployment receipts do not imply continuous service health.
- Keep the site static, with local assets/search, non-root execution, read-only
  mounts, exact LAN bindings and checksummed releases. Never add credentials,
  private inventory, media identities, live APIs, Docker access or public exposure.
- Review affected components with `just wiki-review`, run `just wiki-check`, then
  publish once with `just wiki-deploy`. Preserve existing receipts. Unrelated
  working-tree changes need their own review and must not enter publication.

[Wiki operations](docs/operations/wiki.md) owns the build, deployment, rollback
and backup procedure. `just wiki-rollback` restores the retained prior release;
failed candidates roll back automatically. A publication failure after successful
service deployment requires a wiki retry, not reversal of healthy services.

Configuration backups include wiki runtime/release pointers and private DNS
configuration, excluding generated HTML and DNS query history. Rebuild and
publish after replacement-host recovery; pointers alone cannot restore the site.
Keep original encrypted snapshots and private acceptance evidence unchanged.
