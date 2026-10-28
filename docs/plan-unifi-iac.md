# UniFi configuration as code

Investigated **October 26, 2026**. This is a proposed migration, not deployed
behavior. The investigation used repository sources, read-only UniFi MCP calls,
and upstream release documentation/source. No provider was installed, no state
was imported, and no controller settings or deployment commands were changed.

## Recommendation

Use a separate Terraform root under `network-infra/unifi/`, initially managing
selected DHCP reservations and native DNS policies. Evaluate
[`badgerops/unifi` 0.4.0](https://github.com/BadgerOps/terraform-provider-unifi/releases/tag/v0.4.0)
first: its official-API approach fits the Max, and its narrow reservation
resource avoids taking ownership of unrelated client settings. Treat this as a
candidate pending local import and update acceptance, not a proven provider.

Integrate a plan/check into full `just deploy` first. After adoption and write
verification, promote explicitly accepted changes to automatic application in
that same command. Keep WAN, VPN, firewall, LAN addressing and radio changes
behind a separate network apply path until each has its own acceptance evidence.
An unconditional `terraform apply -auto-approve` is too broad for the network
carrying the deployment itself.

Terraform fits the existing cloud/storage tooling. OpenTofu is a reasonable
alternative if native state encryption is desired, but does not remove UniFi
provider limitations. Choose and pin one engine for this root; changing the
existing cloud/storage roots is unnecessary.

## What is actually in scope

The active gateway is the Cloud Gateway Max at `192.168.1.1`. The accepted
October 22 baseline is Network `10.6.106`, UniFi OS `5.1.33`, one PoE switch and
two wired APs. These versions came from the existing acceptance record, not a
fresh version query. The retained HA UniFi application is not this controller.

Fresh MCP reads on October 26 confirmed:

- Two corporate LANs: Default `192.168.1.0/24`, and printer VLAN 3
  `192.168.6.0/24`.
- Four enabled SSIDs: `sintheta`, `sintheta-iot`, `sintheta-printer`, and
  `sintheta-6-test`. The test SSID remains enabled and must not disappear during
  adoption. Printer client isolation remains enabled.
- Eleven DHCP reservations, including all seven infrastructure assignments in
  [the network inventory](operations/unifi-network-setup.md#infrastructure-address-inventory).
  Several reservations have no explicit network ID; preserve that distinction
  rather than assigning one just to satisfy an example configuration.
- WAN1 DHCP with automatic upstream DNS, the retained Internet 2 definition,
  and one No-IP DDNS configuration. The WAN2 record does not establish an active
  second connection.

The connected MCP exposes reads for these areas but not the firewall-policy,
native-DNS-policy or switch/radio inventory needed for full adoption. The
following are repository contracts requiring fresh API inventory before import:

- Eight active custom zone policies and three paused copies; Default and
  printer both remain in the built-in Internal zone.
- Two `home.arpa` forwarders, plus forwarding for `home.rytim.com`, to the HA
  and NAS resolvers; the native `wiki.home.arpa` A policy stays paused.
- Native `go` and `go.localdomain` A records targeting HA. These are currently
  recreated manually after gateway replacement.
- Site Magic advertises only the Newark and Lehigh Default LANs. Superseded
  manual Lehigh peers remain paused; the separate cloud IPsec tunnel retains
  its coordinated SHA-256 configuration.

Sources of desired behavior remain [network setup](operations/unifi-network-setup.md),
[migration acceptance](operations/unifi-post-migration.md),
[DNS policy](../network-infra/dns/policy.json),
[service hostnames](operations/service-hostnames.md#tinyurl-short-name) and
[household identity](operations/household-identity.md).

## Options and gaps

Release versions below were checked against GitHub's release API, rather than
relying on search-index versions. All three providers are community projects.

| Option | Useful coverage | Decision for this repository |
| --- | --- | --- |
| `badgerops/unifi` **0.4.0**, October 6 | Integration API with a committed `10.6.106` schema; networks, Wi-Fi, DNS policies, firewall policies and ordering; legacy API exceptions for reservations and port forwards | First pilot for reservations and native DNS. Exact version alignment is useful, but does not establish preservation of our settings on update. |
| `filipowm/unifi` **1.1.0**, July 2 | Broad settings, AP radios, switch ports, clients, WLANs and zone-policy ordering | Strong alternative if AP/switch control becomes the priority. Evaluate before adding a custom reconciler for those areas. |
| `ubiquiti-community/unifi` **0.60.0**, October 26 | Broad controller configuration and zone policies | Its released firewall schema still leaves policy ordering unmanaged. That makes it a weaker fit for reproducing the printer policy sequence. |
| Pulumi | TypeScript/Python authoring; the current bridge uses the Filipowm provider | Useful language preference, but adds another state/tool workflow without escaping that provider's coverage limits. |
| Ansible or a small Python reconciler | Can express exact API reads and writes for a bounded unsupported feature | Fallback for a specific gap. We would own normalization, diffing, identity mapping, field preservation, retries, ordering and rollback. Raw `uri` tasks do not supply a Terraform-equivalent preview. |

Primary references: [BadgerOps provider](https://github.com/BadgerOps/terraform-provider-unifi/blob/v0.4.0/README.md),
[Filipowm release](https://github.com/filipowm/terraform-provider-unifi/releases/tag/v1.1.0),
[community policy schema](https://github.com/ubiquiti-community/terraform-provider-unifi/blob/v0.60.0/docs/resources/firewall_policy.md),
[Pulumi bridge dependencies](https://github.com/pulumiverse/pulumi-unifi/blob/main/provider/go.mod),
[Ansible URI check-mode limits](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/uri_module.html).
The original [paultyng provider](https://github.com/paultyng/terraform-provider-unifi)
was archived April 30, 2026; do not start a new installation on it.

Concrete issues to resolve before expanding the pilot:

| Configuration | Coverage assessment and adoption condition |
| --- | --- |
| Reservations | BadgerOps has a dedicated MAC/fixed-IP resource with import. Start with existing assignments, without changing addresses. Inventory all eleven, but initially own only the seven documented infrastructure reservations. Preserve the other four. |
| Native DNS | BadgerOps supports `FORWARD_DOMAIN`, A records and enabled state. Import `go`/`go.localdomain` first; then forwarders and the paused wiki record after DNS acceptance. Keep individual AdGuard records and Bonjour discovery owned by the existing DNS reconciler. |
| LANs | BadgerOps models DHCP ranges, DNS, isolation and mDNS, but not every legacy setting. Capture omitted fields, including IGMP and UPnP behavior. The untagged Default network must use its observed API representation, not an invented VLAN number. |
| Wi-Fi | BadgerOps covers bands, security, isolation and roaming, but its schema lacks the existing arbitrary per-band DTIM/minimum-rate controls; device selection also needs mapping. Filipowm covers AP groups/bands but likewise does not expose every tuned WLAN field. Leave WLANs UI-owned until a controlled update proves those fields survive. |
| Firewall | BadgerOps exposes ordering, but documents protocol-filter and legacy-policy import quirks. Its suggested TCP/UDP workaround would broaden our TCP-only HA/8099 allowance: do not use it. Prove exact protocol/port matching and stable policy IDs. Treat Internal as a data source. |
| Radio/switch ports | Filipowm exposes per-band radio and per-port overrides. Its device docs warn that some zero/false values cannot be written back, and an empty exclusion list can mean trunk every VLAN. Require tested reversal and exact port semantics before ownership. |
| Site Magic and cloud VPN | BadgerOps provides VPN inventory data sources, not full management. Filipowm's Magic setting is only an enable flag, not the two-console mesh and route contract. Retain UI/runbook ownership and coordinated cloud peer handling. |
| WAN, DDNS, IDS, console management | Keep existing ownership initially. Broad provider support for some settings is not proof that the current Max configuration can be reproduced. Administrator/MFA, backups, firmware and adoption need their own workflows. |

Resource references: [reservations](https://github.com/BadgerOps/terraform-provider-unifi/blob/v0.4.0/docs/resources/dhcp_reservation.md),
[DNS](https://github.com/BadgerOps/terraform-provider-unifi/blob/v0.4.0/docs/resources/dns_policy.md),
[networks](https://github.com/BadgerOps/terraform-provider-unifi/blob/v0.4.0/docs/resources/network.md),
[Wi-Fi](https://github.com/BadgerOps/terraform-provider-unifi/blob/v0.4.0/docs/resources/wifi_broadcast.md),
[Filipowm WLANs](https://github.com/filipowm/terraform-provider-unifi/blob/v1.1.0/docs/resources/wlan.md),
[devices](https://github.com/filipowm/terraform-provider-unifi/blob/v1.1.0/docs/resources/device.md),
[Magic setting](https://github.com/filipowm/terraform-provider-unifi/blob/v1.1.0/docs/resources/setting_magic_site_to_site_vpn.md).
Filipowm's [ordering resource](https://github.com/filipowm/terraform-provider-unifi/blob/v1.1.0/docs/resources/firewall_zone_policy_order.md)
is experimental and ignores unlisted policies. Its existence does not prove
the complete effective rule sequence is controlled.

## Repository and deployment design

Proposed entry points, not commands available today:

| Command | Intended behavior |
| --- | --- |
| `just unifi check` | Offline formatting/schema/policy checks; no controller access |
| `just unifi inventory` | Read-only, sanitized inventory plus private ID mapping |
| `just unifi plan` | Refresh and save a private plan; show a redacted change summary |
| `just unifi apply` | Apply the exact reviewed saved plan and verify the affected contracts |
| `just deploy-dry-run` | Include a network plan for a full deployment, never import/apply |
| `just deploy` | Initially check managed network drift; later apply only changes admitted by a tested policy, then run HA deployment and publish the wiki once |

The root [Justfile](../Justfile) currently runs `checkout-prepare`, preflight,
then `wiki/run with-deployment --scope home-assistant -- just talos-deploy`.
Add network orchestration as a sibling of Talos, not as an HA add-on or an AP
SSH script. Preserve single-addon deploy behavior so repairing an application
does not also change routing or Wi-Fi. An explicit recovery bypass for the
network stage should report that network reconciliation was skipped.

For a full deployment, generate/validate the network plan before any writes,
apply permitted network changes, verify controller/HA/NAS reachability and the
changed service contracts, then deploy HA. Update normal, verbose and dry-run
paths together. The wiki wrapper recognizes the exact `just talos-deploy`
command shape when deriving scopes; a new orchestrator must explicitly retain
the actual add-on/config scopes and add a network receipt. Publish once, only
after success. Record partial success if network application succeeds and HA
deployment later fails; this is not an atomic cross-system transaction.

Automatic apply must inspect resource addresses, changed attributes and values,
not only Terraform's create/update/delete labels. Reject deletion/replacement,
unknown critical values, unexpected identities and changes to protected
addresses, DNS forwarders, VLANs, Wi-Fi credentials, uplinks or firewall/VPN
policy. Only promote narrowly tested additive changes, such as a new service A
record, after defining conflict checks. A reservation IP change is not inherently
safe just because Terraform calls it an in-place update. Separate state roots
can enforce scope as adoption grows; do not use routine `-target` to approximate
that separation.

UI edits to owned objects become drift requiring an explicit adopt-or-revert
decision. UI-owned objects remain out of Terraform resources. Never have two
providers or the DNS reconciler write the same object. `prevent_destroy` helps
while a resource block exists, but is insufficient by itself: removing the block
also removes that protection. A plan policy must still reject deletion.
See [plan behavior](https://developer.hashicorp.com/terraform/cli/commands/plan)
and [lifecycle limits](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle).

## State, credentials and recovery

Keep reviewed `.tf` source, synthetic fixtures and `.terraform.lock.hcl` in
Git. Keep state, plans, raw exports, ID maps, Wi-Fi/VPN secrets and the apply
credential under an owner-only external root such as
`~/.local/share/smarthome/tree/network-infra/unifi/`. Add explicit ignore rules
for any compatibility paths; the Usenet ignore rules do not cover a new root.

The existing [Terraform wrapper](../tools/checkout/terraform.py) only permits
the Usenet cloud/storage targets. It cannot run this root unchanged. Extend its
explicit target mapping or introduce a similarly constrained network wrapper;
avoid a state-file symlink because Terraform uses atomic replacement. Source
synchronization must remove stale managed source copies without deleting state
or private inputs, and must handle new reviewed source files deliberately.

Register the new durable files in the checkout manifest/recovery flow. Extend
the Usenet-only Terraform lock scan in [state.py](../tools/checkout/state.py)
and the explicit credential inventory in [credentials.py](../identity-infra/credentials.py).
Verify an encrypted capture and isolated restore of the new state and inputs;
placing files under the external tree alone does not prove recovery coverage.
Serialize operations and retain state locking. A backend on the home NAS would
create a network-repair dependency; external local state matches the current
single-controller workflow. Choose an independently reachable locking backend
if multiple machines later apply.

The existing [MCP launcher](../network-infra/unifi-mcp/README.md) now supports explicitly approved writes under its repository policy.
Its `UBIQUITI_API_KEY` is supplied only to its server process, not ordinary
`just` shells, and its key expires November 22. Provision a separate deployment
credential through the established external secret/escrow mechanism. The
observed key UI did not offer read-only scoping, so client read-only controls
must not be mistaken for restricted server authority. Never extract the MCP
key from another process or put credentials in HCL, command arguments or logs.

BadgerOps expects an explicit provider API-key value; do not assume it reads
the same environment variable as another provider. A wrapper can supply a
sensitive Terraform variable privately. State/plan files can still contain
secrets: `sensitive` controls display, not encryption. Evaluate
[OpenTofu state/plan encryption](https://opentofu.org/docs/language/state/encryption/)
if choosing that engine. Verify the appliance certificate explicitly; do not
silently inherit the MCP launcher's TLS-verification exception.

Retain native encrypted console/Network backups. Terraform covers adopted
resources, not a complete Max hardware restore. Apply failures can leave partial
changes; a state backup alone cannot undo them. Reconcile from fresh reads and
use a reviewed reverse change or the existing coordinated native restore
procedure. Never replay a backup that revives manual Lehigh routes while Site
Magic still advertises them.

## Migration checkpoints

1. **Inventory and identity.** Export a fresh native backup and obtain a private
   API inventory for DNS/firewall/radio/ports. Verify local endpoint routing and
   Integration API site UUIDs; the MCP's legacy `default` name and object IDs
   cannot be substituted for Integration API UUIDs. Preserve paused objects and
   controller-managed policies. Use a wired management path for future writes.
2. **Import without behavior changes.** Pin the engine/provider and lock file.
   Start with one reservation, then the seven infrastructure reservations and
   two short-name DNS records. Use state-only import and review HCL against live
   values. Obtain two successive ordinary plans with zero resource changes;
   do not apply an import plan that also proposes updates. See
   [Terraform import](https://developer.hashicorp.com/terraform/language/import).
3. **Prove a bounded write and reversal.** Use a disposable, unrelated DNS
   record to exercise create/update/readback/remove. Prove reservation write
   preservation separately before allowing reservation changes. Compare fields
   beyond the provider schema: a no-op plan cannot detect fields it never reads.
   Do not run upstream acceptance suites against the household site.
4. **Add deployment checks.** Implement the proposed recipes, source/state
   wrapper, redacted summaries, locking, saved-plan validation and reachability
   checks. Exercise offline plan-policy fixtures for deletion, replacement,
   critical in-place edits, unknowns and partial failures. Test the actual root
   deployment modes and wiki receipt scopes without making live network changes.
5. **Promote accepted resources.** Enable automatic apply for the approved
   subset during full deploy. Expand to native forwarding only after repeating
   exact positive/negative DNS and both-resolver failover contracts. Firewall
   adoption additionally needs ordering, TCP-only print access, DHCP/mDNS,
   blocked LAN/Internet/VPN paths and peer isolation checks. WLAN/radio adoption
   requires secret handling, field-preservation and reconnection/rollback tests.

The first useful implementation is inventory/import/plan tooling for reservations
and the two native short-name DNS records, with zero expected network changes.
Full gateway configuration and unattended network rebuild remain later work.
