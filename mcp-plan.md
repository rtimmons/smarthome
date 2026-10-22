# UniFi MCP handoff — October 22, 2026

The local Cloud Gateway Max at `192.168.1.1:443`, site `default`, is active.
The USG and Cloud Key are disconnected. Required migration checks are accepted;
see [current state and rollback](docs/operations/unifi-post-migration.md),
[SSH access](docs/operations/unifi-ssh-access.md) and
[DNS operations](docs/operations/home-dns.md).

## Access controls

- Preserve `network-infra/unifi-mcp/run.sh`, upstream `0.6.1` pinned to
  `12b4c6e964f920806e2604ab8554e98a4b92536f`, local stdio and the
  read-only/viewer/dry-run `network` profile. Mutations, debug, cloud tools,
  telemetry and MCP network transport remain disabled.
- Use the existing settings-provided `UBIQUITI_API_KEY`; the launcher maps it
  to `UNIFI_API_KEY`. Do not recreate credentials, restore 1Password/Keychain
  fallbacks or repeat installation. The underlying key has no read-only scope
  selector and expires **November 22, 2026**.
- Native MCP exposes 26 tools and live Max/site/client/network/WLAN/WAN/DNS/
  reservation reads passed. Ordinary sandbox TCP returns errno 1; approved
  `require_escalated` execution works. Do not use GUI terminals to bypass it.
- Max/AP/switch SSH uses the verified owner key and dedicated local host pins.
  Max authorization is trusted-LAN-only. Printer and external WAN SSH were
  blocked. Home Assistant and cloud/NAS retain their separate dedicated keys.
- Never print credentials, MCP environment values or raw private API replies.
  Preserve unrelated edits and private backups; Git-lock permission remains
  required unless already authorized in the current task.

## Publication and validation

The wiki and SSH guide were verified by name in Safari and against live
publication metadata on October 22; all 13 prior receipts were retained.
Use `just wiki-review` for affected components, `just wiki-check`, then
`just wiki-deploy` after success. The existing managed publication checkout
excludes concurrent lighting/automation changes; do not acknowledge their
reviews merely to clear checks. Live `publication.json` identifies the release.

The SSH publication passed 26 wiki and six DNS tests plus the current-source/
index secret scan. Earlier infrastructure validation passed 549 unit tests and
syntax/launcher checks; the full history scan retains two documented RSA
findings. Private acceptance/publication evidence is in ignored
`build/unifi-{remaining,dns-failover,ssh}-20261022/`; preserve it.

Launcher configuration, rotation and synthetic checks are documented once in
[the MCP runbook](network-infra/unifi-mcp/README.md). Retest SSH after OS updates
or restore. Keep both AdGuards running, the duplicate native wiki A paused,
old manual Lehigh peers paused, and current radio/Sonos tuning unchanged.
