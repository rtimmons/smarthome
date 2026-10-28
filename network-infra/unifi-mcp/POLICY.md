# UniFi change approval policy

Every live UniFi change requires explicit approval from Ryan for the concrete
controller, site, targets and proposed changes. This applies to MCP, direct API,
UI, SSH and scheduled work, including deletions, client actions and rollback.
Enabling write support, diagnosing a problem, a tool's `confirm=true`, or a
general request to improve the network does not approve a particular change.

1. Inspect current state and read the relevant network runbooks and
   `network-infra/dns/policy.json` when DNS is affected. Preserve existing
   reservations, management reachability, printer isolation and recovery paths.
2. Prepare the exact target, before/after values, expected disruption,
   verification and rollback. Use `dry_run=true, confirm=false` to preview.
   Keep secrets and private response dumps out of Git and chat.
3. Obtain explicit approval for that plan before applying it. Existing approval
   for the same concrete plan remains valid; do not ask again unnecessarily.
   Changed targets, payloads or new risks require renewed approval.
4. Only then use `dry_run=false, confirm=true`. Verify the resulting state.
   After a timeout, inspect state before retrying. Rollback must be included in
   the approval or separately approved. Report partial completion accurately.

Checked-in policy constrains changes; it grants no autonomous or unattended
mutation authority. Do not modify policy to self-authorize a change. A proposal
that conflicts with policy must identify the conflict and obtain explicit
approval for the policy revision and concrete operation first.

The connector retains the upstream network profile: networks, Wi-Fi, DHCP,
DNS, client actions and vouchers. Debug/raw API tools, fleet administration,
device firmware/restarts and firewall tools are outside this profile. Do not
switch profiles or use another access path to bypass these requirements.
Controller database writes are forbidden.

These are agent approval requirements, not a human-authenticated approval
service. The upstream confirmation flag is supplied by the caller. The API key
itself has broader authority; a noncompliant caller could misuse it. Reads and
previews need no approval. No live mutation should be used just to test access.
