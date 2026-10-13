# Smarthome wiki operations

The static wiki is built from the repository and served by the isolated
`usenet-wiki` Compose project on the QNAP. The project identity and storage root
remain stable even though its coverage now includes the whole house.

## Addresses and evidence

The intended canonical URL is `http://wiki.home.arpa/`; the DNS-independent URL
is `http://192.168.1.66/`. Port 8090 preserves the original Usenet entrance.
Read the rollout record in [wiki-plan.md](../../wiki-plan.md) before assuming DNS or DHCP cutover
has been verified. Build metadata and deployment evidence are not live health.

## Author and review

Run `just wiki-check`, `just wiki-build`, or `just wiki-preview` from the root.
The preview listens only on localhost port 8765. Python dependencies are locked
under `wiki/`; the wrapper selects the repository's pinned Python. Model export
uses the existing pinned Node/TypeScript toolchain.

Household explanations live in `wiki/content`. `wiki/components.json` explicitly
lists imported canonical runbooks, component ownership, and watched source paths.
The build stages only these sources and reviewed assets, never the whole checkout.
Links to imported runbooks become local links; other tracked source references
remain links to the repository. Private/ignored file links fail validation.

After reviewing an affected guide, run
`just wiki-review <component> '<specific reason>'`. This records the current source
fingerprint and a review date. A no-impact acknowledgement needs a meaningful
reason. The checker enforces that review happened, not that the explanation is
correct. Update source and narrative together; do not acknowledge an unfamiliar
change simply to make a check green.

Generated reference tables show desired configuration. Temporarily removed and
excluded devices, and disabled add-ons, remain visible. Do not treat source
configuration as a claim that a device is online. Runbook observations keep their
own dates; a new build does not refresh those dates.

## Publish

`just wiki-deploy` validates and publishes documentation-only updates.
`just usenet-wiki-deploy` remains an alias. Supported deployment recipes wrap
their operational command: prepare documentation first, run the deployment,
then publish once after success. Nested wrappers inherit a transaction marker;
dry runs and help/version requests bypass publication. DNS changes use their separate workflow.

The build carries a source revision, source fingerprint, working-tree indicator,
and build time. A receipt means its named deployment command completed
successfully; it does not imply continuous monitoring or verify unrelated scopes.
Prior receipts are merged from the live wiki. Failed publication retains local
pending receipts for `just wiki-deploy` to retry. Review the revision if source
changed before that retry.

If services deploy but the wiki fails, the command reports that distinction and
exits nonzero. Retry documentation publication; do not roll back healthy household
services solely because the wiki is unavailable.

## Isolation and rollback

Only immutable static files and a versioned Caddy configuration are mounted into
the wiki container, read-only. It has no Docker socket, credentials, media mount,
application API connection, or writable host directory. Search and navigation run
locally in the browser. No CDN, public hosting, WAN forward, or certificate trust
change is required.

Each candidate is checksummed before transfer. Deployment verifies bindings,
container health, release mount, and HTTP content. A failed candidate restores
the previous runtime and environment; a failed first deployment stops only the
wiki. `just wiki-rollback` restores the retained previous release after acceptance.
Keep accepted and previous releases until the rollback window has passed.

The source is covered by checkout backup. Runtime configuration and the retained
release pointers live under the existing NAS application backup root. Restore
those settings or rebuild from source; neither procedure restores NAS media.
Use numeric addresses during a DNS failure. See [DNS operations](home-dns.md).

## Initial expansion acceptance (2026-10-09)

Numeric port-80 access, local search, phone-width navigation and the original
`8090/#storage` redirect were checked in a browser. Both DNS resolvers pass the
local-name checks; network-wide DHCP acceptance is tracked in the DNS runbook.
New, uncommitted source files are labeled as working-tree sources rather than
linked to a revision that does not contain them. Commit/push is a separate step.

The NAS configuration backup includes wiki release pointers and versioned runtime
files, and DNS configuration/runtime/private recovery snapshots. It deliberately
omits generated wiki HTML and DNS query/statistics data. After a replacement-host
restore, rebuild and publish the site before starting the restored wiki pointers;
those pointers alone cannot recreate the omitted static files.
