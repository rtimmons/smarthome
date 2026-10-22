# UniFi MCP deployment handoff

## Current state — October 22, 2026

- The Max is active at `192.168.1.1:443`; USG and Cloud Key remain retired.
- The existing launcher, settings-provided `UBIQUITI_API_KEY`, source pin and
  read-only/viewer/dry-run network profile are unchanged. Do not recreate keys,
  restore credential fallbacks, reinstall or enable MCP mutations.
- This resumed session runs on the Mac and exposes **26 native UniFi tools**,
  with no controller mutation/debug entries. Live reads passed for the local
  Max/site `default`, clients, networks, four WLANs, WAN definitions, DNS filters,
  statistics and all seven expected infrastructure reservations.
- Ordinary sandbox TCP/443 returns `PermissionError`, errno 1. The same TCP/TLS
  check succeeds through approved `require_escalated` execution. Native MCP is
  already network-capable. Direct DNS/SSH/wiki work now uses the approved
  executor path; no broad security setting change or alternate credential is
  required. The earlier missing native tool forwarding is resolved.
- The DNS forwarding-only hybrid passes the unchanged UDP/TCP contract after
  pausing the duplicate native A record. Two native `home.arpa` forwarders now
  select the surviving AdGuard automatically. Each backend outage, both-down
  containment and automatic recovery passed, with both services running and
  original access lists restored. Associated printer-client allow/deny
  checks and cloud SHA-256 reconnect/PFS rekey passed. See the canonical
  follow-up for the accepted physical print, same-AP phone peer and fresh
  wire-level discovery checks and observed fresh HA Ethernet lease. Ryan
  accepted UniFi's Connected status for Site Magic without a Lehigh host.
  Both old manual peers are paused. Ryan confirmed Remote/AirPlay/Sonos controls and
  cloud-application sign-ins from the home LAN.

Preserve unrelated work and every private backup. Do not stage, commit or take
a Git lock without permission. Keep credential values and raw private responses
out of source, logs and chat.

## Scope and accepted controls

Finish read-only MCP verification against the Max. The broader authorized
network improvements and their live acceptance checks are tracked in
`docs/operations/unifi-post-migration.md`. Preserve unrelated edits and root
AGENTS.md requirements; leave changes unstaged without Git-lock permission.

The launcher pins the repository Python and upstream source, uses local stdio,
selects only the local Max and `network` profile, and forces read-only, dry-run
and viewer settings. Cloud tools, debug, external telemetry and network
transport remain disabled. Package/cache/tool environments live under ignored
`build/unifi-mcp/`. TLS verification is initially false for the appliance
certificate; a verified CA is a separate reviewed change.

The native key form offers no read-only permission selector. The dedicated key
**Codex UniFi MCP - 300 Newark** expires **November 22, 2026**. Its initial
unused value was revoked and replaced. The MCP controls do not reduce the
underlying key's privileges.

## Validation and remaining work

Native tool exposure, Max/site identity and live network/client/Wi-Fi/WAN reads
are accepted as dated October 22 evidence. Synthetic launcher tests and wiki
checks must remain current. The broader remaining work is in
`docs/operations/unifi-post-migration.md`. The LAN-only Site Magic mesh is live,
with both gateways Connected; no bidirectional host test is claimed.
The zone upgrade is live after the accepted counter/peer baseline. Eight custom
policies are active; three unreachable duplicate HA allow copies are paused,
with every drop and DHCP/mDNS policy retained. Restricted printing and the
same-AP phone peer passed; keep cellular data off during an iPhone's local-only
test and restore it afterward. Owner-approved read-only native Debug provided
the counters; console SSH and MCP mutations remain off.

Updated documentation, including automatic DNS failover, was published through
`just wiki-deploy` on October 22 at 18:11 Eastern from clean commit `83d1865`.
Safari opened the live guide by name; the generated reference lists both
forwarders and live metadata matched the reviewed source fingerprint, with 92 static
files and all 13 prior deployment receipts retained. The publication used an
isolated checkout to exclude concurrent lighting/automation implementation
edits in the main worktree. Six existing checkout-specific runbook links were
made repository-relative; their review covered only those link corrections.
The isolated wiki check passed 26 wiki tests and six DNS tests. Current-source/
index secret scanning passed. The earlier prepared infrastructure changes
passed all 549 unit tests and their syntax/launcher checks; the full history
scan retains the two documented historical RSA findings. No history was
rewritten or scan exception added.

The main worktree's unrelated Z-Wave runbook, HA client and manual automation
edits remain unstaged. Their component reviews belong to their own work;
do not acknowledge them solely to clear a whole-worktree wiki check. Private
publication metadata/logs for the DNS follow-up are preserved under
`build/unifi-dns-failover-20261022/published-wiki/`; prior migration evidence
remains under `build/unifi-remaining-20261022/`. Every encrypted backup remains
in the original ignored backup directory. Automatic local-zone failover is now
accepted: both native forwarders remain active, with unchanged gateway DHCP DNS
and native ad blocking. The Mac passed cold local answers, UDP/TCP negatives,
public resolution, ad blocking and wiki-by-name HTTP during either backend
outage. Both-unavailable local queries failed closed, the WAN trace contained
no private-zone DNS, and normal access recovered after exact ACL restoration.
An independent watchdog completed cleanly. Both AdGuards remain running and
required for this redundant design. Private drill evidence is under
`build/unifi-dns-failover-20261022/`.

Do not test controls using a real mutation or bypass restrictions with a GUI
terminal. Key rotation before November 22 remains routine upkeep.

## References and validation

- Current launcher runbook: `network-infra/unifi-mcp/README.md`.
- Canonical migration record: `docs/operations/unifi-network-setup.md`.
- Broader checklist: `docs/operations/unifi-post-migration.md`.
- Source: <https://github.com/enuno/unifi-mcp-server/releases/tag/v0.6.1>.
- Shared configuration: `/Users/rtimmons/.codex/config.toml`; never print its
  environment values. Preserve other MCP entries/settings.
- Bundled CLI:
  `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`.
  Its `mcp get --json` can include credential values; never dump that output.

```sh
build/wiki/venv/bin/python -B -m unittest discover -s network-infra/unifi-mcp -p 'test_*.py' -v
bash -n network-infra/unifi-mcp/run.sh
shellcheck network-infra/unifi-mcp/run.sh
git diff --check
just wiki-check
```
