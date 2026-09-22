# Prepared replacement-server drill

Status: validated and planned; not applied. Creating billed temporary resources
awaits a spending decision. No production Terraform root or resource is part of
this plan. Use the independent `terraform/recovery-drill` root, never the
production cloud or storage root, for creation and cleanup.

The saved private plan creates exactly four resources: a temporary CX43 server
in HEL1, a separate 300 GB volume, its attachment and an SSH-only firewall.
It reuses only the existing administrator public-key resource and trusted SSH
source CIDRs. It has no Storage Box resource, production IP assignment, VPN
peer or public application port. There are no updates, replacements or deletes.
Terraform validation and inspection of the saved plan passed.

The provider's September 22 API quote is USD 0.0296/hour for the server,
USD 0.001/hour for IPv4 and USD 0.0767/GB-month for volume capacity. A two-hour
drill should cost roughly USD 0.15, subject to billing rounding. The proposed
spending ceiling is USD 1; destroy the temporary resources as soon as evidence
is collected, with a two-hour execution limit. Do not leave the server running
for later work. Recheck prices and the saved plan before applying after a delay.

## Execution and evidence

1. Apply only the saved, reviewed drill plan after spending authorization.
   Record the new resource IDs and the automatically created IPv4 identity. Independently pin the new SSH host identity
   through the provider console; do not trust a network key scan alone.
2. Install pinned dependencies/images before restoring sensitive state. Then
   restrict application egress and keep all application ports loopback-only.
   Use separate disposable state and the new volume; never attach or format the
   production repair volume. Pin the new volume ID and UUID for this drill.
3. Independently restore the newest verified cloud archive, nested Filex state
   and needed bootstrap material. Reconstruct systemd services and mount
   dependencies against the new volume. Keep acquisition disabled and exclude
   production VPN identities/routes. Use read-only canonical access, or isolated
   fixture paths where writes are necessary. Do not install a canonical writer
   key in an application container or permit any real acquisition.
4. Verify boot/service startup, restored authenticated APIs, private proxy/HTTPS,
   mount-before-application ordering and refusal to start with a required mount
   absent. Confirm restored journals, request state, quality defaults and retired
   worker guards. Record any substituted path or disabled integration explicitly;
   a fixture does not establish live provider delivery or canonical writes.
5. Shut down the restored services, collect sanitized receipts, then destroy only
   the four tracked temporary resources. Verify their absence, including the automatically created IPv4 address, with the provider.
   Preserve encrypted archives and production resources. If cleanup fails, report
   the exact retained resources and accruing charges immediately.

This is cloud replacement recovery. NAS originals and NAS/Plex replacement remain
a separate backup and hardware scope; successful isolated extraction alone is
not evidence of either machine's bootability.
