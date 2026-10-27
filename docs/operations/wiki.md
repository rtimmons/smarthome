# Smarthome wiki operations

The static wiki is built from the repository and served by the isolated
`usenet-wiki` Compose project on the QNAP. The project identity and storage root
remain stable even though its coverage now includes the whole house.

## Addresses and evidence

The preferred browser and canonical metadata URL is `https://wiki.home.rytim.com/`,
protected by Ryan’s Authelia MFA. `http://wiki.home.arpa/` and the DNS-independent
`http://192.168.1.66/` remain unauthenticated LAN compatibility/recovery entrances.
Port 8090 preserves the original Usenet entrance. Publication probes continue to
use the direct NAS address so recovery does not depend on the SSO proxy.
[DNS operations](home-dns.md) records the accepted gateway-forwarding and
failover design. Build metadata and deployment receipts are not continuous
service health.

## Author and review

Run `just wiki-check`, `just wiki-build`, or `just wiki-preview` from the root.
The preview listens only on localhost port 8765. Python dependencies are locked
under `wiki/`; the wrapper selects the repository's pinned Python. Model export
uses the existing pinned Node/TypeScript toolchain.

Household explanations live in `wiki/content`. `wiki/components.json` assigns
household pages, imported canonical runbooks,
add-ons and watched source paths to a single component owner. Build-time navigation
and the runbook directory use those assignments and each page’s first heading;
there is no separate import or runbook navigation list to keep synchronized.
The build stages only these sources and reviewed assets, never the whole checkout.
Links to imported runbooks become local links; other tracked source references
remain links to the repository. Private/ignored file links fail validation.

The nested private `printer/` repository is an explicit source exception: review
fingerprints use its own Git source list, excluding its ignored runtime files.
Only the printer runbooks named in `wiki/components.json` are imported; application
source is hashed for review, not copied into the site. Private source references
are labeled as private local paths rather than linked to GitHub. Publication
metadata records the private revision and dirty state as well as the parent
revision. Both checkouts must be present for wiki checks and deployment.

Keep specific media titles, artists, albums, release filenames, artwork links,
and identifying catalog links/IDs out of wiki prose, examples, and imported
receipts. Use neutral aliases for operational evidence and synthetic test data.
Configured radio stations and favorites may retain the exact names needed for
playback; incidental now-playing metadata must stay private. Review the full
staged diff and commit message as well as the rendered pages: a secret scan or
successful wiki build does not establish media privacy. See the repository
[media privacy rules](../../AGENTS.md#media-privacy).

After reviewing an affected guide, run
`just wiki-review <component> '<specific reason>'`. This records the current source
fingerprint and a review date. A no-impact acknowledgement needs a meaningful
reason. The checker enforces that review happened, not that the explanation is
correct. Update source and narrative together; do not acknowledge an unfamiliar
change simply to make a check green.

Generated reference pages show desired configuration. Services include ingress,
network mode, declared host mappings and dependencies from add-on manifests.
Room and device tables come from `home-model/rooms.json`, the reviewed physical
device catalog, and generator sources. Cross-room presets and hardware reference
areas are computed at build time. Separately dated, sanitized verification
receipts show registry totals and direct Sonos/HA name comparisons; their source
digests flag stale evidence, and unreachable speakers remain unverified. Refresh
with `just areas-audit --record-verification` and `just rooms-verify --record-verification`.
Device all-off membership and scene targets use the same functions as deployment,
including exclusions, blocklists and entity deduplication. Controls show generated
automation modes without webhook IDs or action payloads. DNS records, resolvers
and filter states come from `network-infra/dns/policy.json`; runtime versions come
from the pinned version files. The coverage page lists ownership and review reasons.

The DNS-policy reference also includes the canonical service-hostname runbook:
explicit HTTP destinations, path handling, authentication boundaries, deferred
services, recovery instructions and dated acceptance. Edit
`docs/operations/service-hostnames.md` to maintain that explanation; the build
includes it on the reference page and rewrites its links to local runbooks.
DNS tables remain generated from policy, while acceptance retains its authored
date and limits. A rebuild does not perform fresh service verification.

Guide and imported-runbook contents participate in their owner’s fingerprint.
The checker rejects duplicate ownership, unowned guides/add-ons, and watch patterns
that match no files. It also validates rendered links, anchors and local assets.
New source files in a watched directory participate before staging.

Keep explanations, recovery decisions and dated observations authored. Never
generate live availability from desired state, and never ingest `.storage`,
private environment files, media listings or credential-bearing runtime dumps.
The control reference covers the TypeScript registry only; manual YAML, package
and UI-owned automations remain in their canonical runbooks.

Temporarily removed and excluded devices, and disabled add-ons, remain visible.
Do not treat source
configuration as a claim that a device is online. Runbook observations keep their
own dates; a new build does not refresh those dates.

## Publish

`just wiki-deploy` validates and publishes documentation-only updates.
`just usenet-wiki-deploy` remains an alias. Supported deployment recipes wrap
their operational command: prepare documentation first, run the deployment,
then publish once after success. Nested wrappers inherit a transaction marker;
dry runs and help/version requests bypass publication. DNS changes use their separate workflow.

Before changing services, the wrapper checks that it can read the existing wiki's
publication evidence. It fetches that evidence again after service deployment to
merge current receipts. These bounded requests use `curl` directly to the NAS,
with proxies and curl configuration disabled. On macOS it selects `/usr/bin/curl`
explicitly so Conda or another shell environment cannot substitute its own client.
Python's HTTP client and its proxy
discovery are not part of this path. A network error is never treated as empty
publication history.

Wrapped deployments and wiki-only publication print a private log path under
`build/wiki/logs/` and save combined output there, including the exit status.
Nested deployments share the outer log. These ignored files can contain operational
details; review them before sharing. Root recipe setup steps before the wiki wrapper
are not included. Deployments before this logging was added did not save console
output automatically, despite the older `/tmp/deployment-*.log` documentation.

The build carries a source revision, source fingerprint, working-tree indicator,
and build time. A receipt means its named deployment command completed
successfully; it does not imply continuous monitoring or verify unrelated scopes.
Prior receipts are merged from the live wiki. Failed publication retains local
pending receipts for `just wiki-deploy` to retry. Review the revision if source
changed before that retry.

If services deploy but the wiki fails, the command reports that distinction and
exits nonzero. Retry documentation publication; do not roll back healthy household
services solely because the wiki is unavailable.

For a connection failure, the saved output includes the requested URL and curl
error. Check connectivity from the same terminal that ran the deployment; a
successful request from a different application does not establish that terminal's
access. A preflight failure changes no services. A failure after service deployment
keeps `build/wiki/pending-receipts.json` for the wiki-only retry.

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

### Runtime identity inputs

Ansible accepts independent `qnap_wiki_uid` and `qnap_wiki_gid` inputs. They
inherit `qnap_uid` and `qnap_gid` unless explicitly overridden, preserving the
existing deployment. Both must be positive. They populate Compose's existing
`WIKI_UID` / `WIKI_GID`; deployment credentials and other runtimes are unchanged.
Do not assign new IDs in durable inventory before the account/ACL checkpoint.

Publication compares the entire candidate environment: a UID/GID change with
the same site release still recreates only the wiki container. Repeating the
same healthy release and identity does not restart it. Rejected publication
and explicit rollback restore the retained environment, including its original
identity; rollback does not adopt newly supplied UID/GID values.

The October 27 repository preparation tested default rendering, independent
overrides, root/missing-ID rejection, rejected-candidate recovery, same-release
identity changes and retained-identity rollback with synthetic local fixtures.
No live identity or path change is established by those tests. Revert only the
preparation commit to undo the input change; it leaves production state alone.

Follow the [NAS pilot checkpoints](../nas-service-inventory-2026-10-27.md#first-pilot-wiki-preparation-then-separate-identity-and-path-checkpoints)
for account qualification and live checks. Current/previous release metadata and
independent recovery of both source repositories and build inputs remain live
switch prerequisites. Test actual local/container denials as well as SMB;
retained QNAP defaults can grant access independently of container mount scope.
Keep account grants, runtime switching and the named-share move separate. The
named-share move remains subject to disk, power, snapshot and recovery readiness.

## Initial expansion acceptance (2026-10-09)

Numeric port-80 access, local search, phone-width navigation and the original
`8090/#storage` redirect were checked in a browser. Both resolvers passed direct
local-name checks. The October 22 gateway DNS forwarding/failover acceptance is
in the DNS runbook.
New, uncommitted source files are labeled as working-tree sources rather than
linked to a revision that does not contain them. Commit/push is a separate step.

The NAS configuration backup includes wiki release pointers and versioned runtime
files, and DNS configuration/runtime/private recovery snapshots. It deliberately
omits generated wiki HTML and DNS query/statistics data. After a replacement-host
restore, rebuild and publish the site before starting the restored wiki pointers;
those pointers alone cannot recreate the omitted static files.
