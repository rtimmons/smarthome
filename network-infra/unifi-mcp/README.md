# UniFi MCP on the Mac

The launcher uses [enuno/unifi-mcp-server 0.6.1](https://github.com/enuno/unifi-mcp-server/releases/tag/v0.6.1)
through Homebrew `uvx`, pinned to Git commit
`12b4c6e964f920806e2604ab8554e98a4b92536f`. Release `0.6.1` is available on
GitHub, while PyPI only publishes through `0.2.5`; retain the Git source pin.
It targets the Cloud Gateway Max at `192.168.1.1:443` over local stdio, with
no MCP network listener. The repository Python is pinned; package/cache/tool
environments stay under ignored `build/unifi-mcp/`.

## Current status — October 22, 2026

Ryan added **UBIQUITI_API_KEY** to UniFi's environment variables in the ChatGPT
MCP settings and explicitly selected that credential path. The launcher now
requires that variable, maps it to upstream's `UNIFI_API_KEY`, then removes the
duplicate variable. It does not invoke 1Password or Keychain.

The enabled configuration points to this launcher with a 120-second startup
timeout. The resumed Mac session exposes **26 native tools** from `0.6.1`, with
no controller mutation/debug entries. Live reads succeeded against the local
Max at `192.168.1.1`, site `default`: current clients, VLANs/networks, four WLANs,
WAN definitions, DNS-filter settings, statistics and DHCP reservations. All
seven expected infrastructure reservations matched. Safari corroborated the
Max identity and Network `10.6.106`.

Earlier direct-stdio initialization succeeded but live reads were blocked.
The ordinary command sandbox still denies TCP with `PermissionError`, errno 1;
the identical TCP/TLS probe succeeds through approved `require_escalated`
execution. Native MCP works independently of that command sandbox. Direct
DNS/SSH checks use the approved network-capable executor path. No credential
change, GUI terminal, reinstall or broad sandbox setting change was needed.

The dedicated key is **Codex UniFi MCP - 300 Newark**, expiring **November 22,
2026**. Its initially unused value was revoked and replaced before storage.

## Credential and registration

Keep `UBIQUITI_API_KEY` in the user-managed MCP settings. Empty or whitespace-
containing values fail before server startup. The key is never placed in
command arguments or emitted by the launcher. Keep credential values out of
repository files, logs and chat. The repository's `codex.toml` is only a launcher
registration template; preserve the owner's existing environment setting when
merging or editing registration.

The observed Network 10.6.106 key form is **Integrations > Create New API Key**.
It offers name, description and expiry, with no read-only scope selector. The
underlying credential is not constrained by the MCP server's read-only mode.

The launcher enforces the `network` profile, `UNIFI_READ_ONLY=true`, dry-run
mode and the `viewer` stdio role. Debug requests, cloud tools, external
telemetry and network transport are disabled. TLS verification is initially
disabled for this LAN appliance's certificate, as recorded in the deployment
handoff; a verified appliance CA remains a separate reviewed change.

To rotate, replace the settings-provided value with a new dedicated key,
verify live reads with a new process, then revoke the old key in UniFi. To
remove access, revoke the UniFi key and remove the server registration.

## Verification and updates

Synthetic tests verify environment mapping, invalid/missing values, protocol
stdin preservation, tracing/output privacy, the source pin and forced server
controls. They do not contact the gateway:

```sh
build/wiki/venv/bin/python -B -m unittest discover -s network-infra/unifi-mcp -p 'test_*.py' -v
bash -n network-infra/unifi-mcp/run.sh
shellcheck network-infra/unifi-mcp/run.sh
```

`just unifi-mcp-check` checks package import in a process already supplied with
`UBIQUITI_API_KEY`. It does not start a transport or read the gateway. An MCP
settings variable belongs to its server process; it is not automatically
exported into an unrelated Terminal shell.

Repeat live acceptance after a credential/package change: inspect tools with
controller mutations/debug absent, then read clients, networks/Wi-Fi and WAN
and confirm Max/site identity. These checks passed October 22; they are dated
evidence, not continuous monitoring. Do not attempt a real mutation to test
read-only mode. The API's restored inactive `Internet 2` definition alone is
not evidence of active WAN2 service.

Review upstream release notes before changing the immutable source pin, then
repeat protocol/tool-list and live-read verification. See the
[post-migration checklist](../../docs/operations/unifi-post-migration.md).
