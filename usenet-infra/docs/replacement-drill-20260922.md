# Replacement-server drill

Status: executed October 8 under the approved USD 1 ceiling. Restored application
startup, storage-loss guards and retired-worker protections passed. See the
[closure receipt](../recovery/drills/closure-20261008.json) for reboot and cleanup
evidence. The independent `terraform/recovery-drill` root manages only disposable
resources; production cloud and storage roots are excluded.

The saved private plan creates exactly four resources: a temporary CX43 server
in HEL1, a separate 300 GB volume, its attachment and an SSH-only firewall.
It reuses only the existing administrator public-key resource and trusted SSH
source CIDRs. It has no Storage Box resource, production IP assignment, VPN
peer or public application port. There are no updates, replacements or deletes.
Terraform validation and inspection of the saved plan passed.

The provider's October 8 refreshed API quote is USD 0.0296/hour for the server,
USD 0.001/hour for IPv4 and USD 0.0767/GB-month for volume capacity. A two-hour
drill should cost roughly USD 0.15, subject to billing rounding. The approved
spending ceiling is USD 1; destroy the temporary resources as soon as evidence
is collected, with a two-hour execution limit. Do not leave the server running
for later work. Recheck prices and the saved plan before applying after a delay.

## Execution and evidence

1. Apply only the saved, reviewed drill plan after spending authorization.
   Record the new resource IDs and the automatically created IPv4 identity. Independently pin the new SSH host identity
   through the provider console, or generate a dedicated ephemeral host key
   locally and install it through sensitive cloud-init user data before first
   connection. October 8 used the latter method and strict pinned SSH checking;
   no network key scan or trust-on-first-use was used. Keep bootstrap material
   and Terraform state private.
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

## October 8 isolation and reproducibility notes

The drill restored 785 files, five application databases, 44 historical journals
and nested Filex state from `cloud-20261008T190549Z.tar.age`. Journal bytes matched
the verified archive. Exact reviewed Filex/Caddy images were transferred from
production; acquisition application images used the deployed version pins.

The new 300 GB volume was formatted once after asserting its exact provider ID
and absence of a filesystem, then mounted by its new UUID. Canonical storage
was substituted with an empty read-only fixture bind. Production storage writer
credentials, NAS connection and VPN routes were excluded. Reconstructed systemd
units required both repair and library mounts, stopped applications on mount
loss, and refused startup while the fixture source was absent. The underlying
unmounted library directory retained mode 0000.

Before sensitive state was uploaded, new outbound traffic was blocked. A boot
unit restores IPv4/IPv6 isolation before Docker and applications. Arr, Seerr and
Filex bind loopback. SAB's image overrides its configured bind address, so the
drill uses an internal-only Docker network; its authenticated API is checked
inside that container. SAB starts paused with an empty queue. Real indexer,
provider, NAS, Plex and canonical write integrations were not exercised.

The Filex diagnostic HTTPS proxy binds loopback for this drill. Its original
private-IP certificate is verified with an explicit CA and a loopback address
override. Because IP-address TLS does not supply SNI, the drill-only Caddy
configuration sets `default_sni 10.77.0.1`; production configuration is unchanged.
Three restored systemd native-ownership conditions skip cart-import, capacity
admission and incomplete maintenance. The older publisher is never started.

Private replay scripts, logs, resource identities and the pre-pinned ephemeral
SSH identity are retained in ignored `build/closure-20261008`. Configuration
steps format a new volume and must never be replayed against production. The
private sequence includes separate SAB network and Caddy SNI corrections before
verification. A deadline watchdog limited paid runtime to two hours, with normal
cleanup scheduled immediately after verification. This proves isolated cloud
application startup, not a complete NAS/Plex machine replacement or live media
access from a replacement host.
