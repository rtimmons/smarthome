# Smarthome wiki operations

The static wiki is built from the repository and served by the isolated
`usenet-wiki` Compose project on the QNAP. The named-share migration and current
acceptance state are recorded in the [October 27 ledger](../nas-wiki-share-migration-2026-10-27.md).

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

The releases directory, live-pointer directory and versioned Caddy configuration
are mounted into the wiki container, read-only. Caddy serves `live/current`, a relative symlink
to the accepted release’s `site` directory. The mount stays fixed while the
publisher atomically replaces the symlink, so ordinary HTML updates and content
rollbacks need no server restart. The share root, including private environment
files and publication locks, is not mounted. Retained release runtime files are
inside the read-only mount but outside the served site root. It has no Docker
socket, credentials, media mount,
application API connection, or writable host directory. Search and navigation run
locally in the browser. No CDN, public hosting, WAN forward, or certificate trust
change is required.

Each candidate is checksummed before transfer. The first publication using the
symlink layout recreates only the wiki container. Later publications recreate it
only if runtime files, identity or bindings change, or the existing server fails
its health/content checks. An unchanged runtime skips image and Caddy validation
work. A rejected content update switches the pointer back without restarting.
The `.env` and `.env.previous` files retain release/runtime identities for backup
and rollback; after restoring settings and rebuilding HTML, publication recreates
the derived `live/current` pointer. Do not bind-mount `current` itself: Docker
would resolve it once and keep serving the old release. The atomic replacement
uses `os.rename` through the existing host Python (`/usr/local/bin/python` on
QNAP); the firmware’s BusyBox `mv` lacks `-T`. Missing Python fails before any
pointer or runtime change.

Deployment verifies bindings,
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

`qnap_wiki_manage_reader_acl` defaults to `false`. After a local reader group is
qualified, enabling it adds that runtime GID's read/traverse access to each
candidate's site directories, and read access to site files and its Caddyfile,
before publication. It requires an existing local group and rejects
symlinked inputs. It preserves existing ACL entries, masks, owners and mode bits;
it adds read/traverse on the release directory, releases parent and live-pointer
directory required by the stable mount, but no share-root, default ACL, write or credential grant.
Every publication reapplies the scoped entries, so future releases do not depend
on manually inherited ACLs. An ACL command failure aborts before publication.

Before enabling this on an existing release, save its exact ACLs separately.
Runtime rollback restores the retained identity/environment; undoing a grant is
a separate ACL checkpoint using that saved preimage. Preserve the preimage until
acceptance, and never restore it blindly after another publisher has changed files.

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

### October 27 recovery supplement and account checkpoint

The [migration ledger](../nas-service-inventory-2026-10-27.md#wiki-preparation-and-recovery-checkpoint)
records verified encrypted copies of the current/retained published releases and
fresh source bundles for both repositories. Independent source restore/build
passed using the controller's pinned Node runtime. Preserve those exact private
archives and the original publication pointers; a future rebuild need not produce
the same metadata digest because build times and working-tree state are inputs.

Local `svc-wiki` (UID 1005) and `wiki-reader` (GID 1000) now exist. The account's
QNAP primary group remains `everyone` (100); probes explicitly use 1005:1000 with
no supplementary group 100. Saved share/application denials and actual synthetic
file/share-root denials are recorded in the ledger. `test -r/-x` disagreed with
actual listing/traversal; actual operations are the acceptance checks.

The original publication read failed. After a scoped grant, all 101 site files
were readable and Caddy validated at 1005:1000. Only 186 group read entries were
added; the pre-existing ACL record is otherwise identical and retained off NAS.
The publisher's opt-in step makes future release grants explicit. Synthetic
write/create/rename/delete and share-root denials, plus exact ACL restoration,
passed. No share-wide grant or guest-denial removal was needed.

The approved runtime switch completed October 27; the container started at
18:53:11 Eastern. Init and Caddy now run as **1005:1000**, group 1000 only, with
zero capabilities and `NoNewPrivs: 1`. Both binds/root remain read-only and a
runtime create attempt was denied. Both HTTP ports served unchanged publication
bytes; numeric access, the legacy redirect and unauthenticated TLS/Authelia
redirect passed. All peer-container start times were unchanged.

Durable inventory explicitly sets the wiki UID/GID and enables reader ACLs;
pinned Ansible verified those inputs while shared defaults remain 1004:100.
The same release at 1004:100 is retained for rollback. Restore those runtime
settings and remove only the three wiki inventory overrides if rolling back this
checkpoint, after checking for later edits. ACL rollback remains separate.
When invoking the helper through an SSH stdin script, redirect the helper's stdin
from `/dev/null`. The streamed wrapper's trailing checks did not execute during
this run, so acceptance was independently read in a separate command.

The new encrypted controller checkpoint contains pointers, ACLs, account mapping,
private inventory and both source bundles, with independently verified decryption
and hashes. Combine it with the preserved unchanged release payloads. See the
[completed runtime checkpoint and limits](../nas-service-inventory-2026-10-27.md#wiki-runtime-identity-checkpoint).
Normal unattended NAS settings capture/restore remains open. The later
valid-credential network check passed: SMB refused session setup and SSH denied
the password login. No authenticated SMB share connection was opened.

The [later backup follow-up](../nas-service-inventory-2026-10-27.md#wiki-backup-and-network-verification-follow-up)
adds a verified manual Hetzner checkpoint containing a current native QTS export
and the preserved wiki recovery inputs. The latest scheduled archives were
restored and found to predate this identity change. Inspect the next eligible
normal capture separately; a manual supplement does not prove the schedule.

In particular, a fresh outer archive can still contain an older weekly native
QTS snapshot that predates the account. The later named-share migration completed
under the documented wiki-only exception; general storage gates remain closed.
Publication bytes were retained; docs can publish with the next normal release.

### Repeat the runtime account network checks

Run `just wiki-check-runtime-access` from the repository root. It decrypts the
current `identity-infra/credentials.sops.json` locally and uses the `svc-wiki`
entry when present. If missing, run interactively and enter/confirm the existing
password from 1Password. The command adds only this entry, verifies encrypted
readback, and preserves the private source at
`build/identity-private/secrets/wiki-runtime.json` for subsequent normal SOPS
captures. It never creates or resets a NAS account/password. Review and commit
the ciphertext-only vault change. Existing entries are never implicitly replaced.

Automated work shares a 55-second budget, excluding hidden password entry.
There is no NAS credential-database read, temporary container or persistent
reader. Successful receipts include stage timings; a timeout is inconclusive.
Follow AGENTS.md for dedicated HA-key failures rather than substituting access.

The existing pinned directory maintenance transport supplies the encrypted SMB3
client. It checks only share connections, never lists or reads household files.
The password comes from SOPS; it is not independently compared with the NAS
password hash. Each authenticated tree-connect denial is recorded separately. A refusal
during session setup stops further SMB attempts and is recorded as a session
denial, not proof of a current password or seven independently tested share ACLs. Bad-password, timeout and
connection errors do not pass. SSH uses the pinned NAS host key, one password
attempt and no SSH-agent identity; its receipt records whether a password prompt
occurred and confirms that no session opened.

Temporary credential files are private and removed when their checks finish.
Only sanitized receipts remain under the ignored `build/identity-private/wiki-access/`
state directory. A probe failure does not change account grants or stop any service. An initial
credential entry already saved in SOPS remains saved if a later probe fails;
its presence does not certify successful authentication.
Interpret these protocol checks alongside the separate process, bind-mount and
filesystem ACL checks; SMB denial does not establish host-process isolation.

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

## Named-share deployment and recovery

The reviewed named deployment root is `/share/wiki`, selected by private
`qnap_wiki_root`; defaults retain the legacy root for unmigrated installations.
The role requires a registered QTS share whose resolved path matches `/share/wiki`.
It preserves QTS root ownership/ACLs rather than chmodding the share on publication.
A migration/publication lock is checked before uploads. The old root is retained
with a lock to reject stale deployment inputs; do not clear it as cleanup.

`QNAP_WIKI_ROOT=/share/wiki` selects the manual and scheduled capture source.
The repository backup worker mounts that source read-only over its logical wiki
namespace; archives record `source_roots.wiki`. Recover to an isolated directory,
then restore the runtime/pointers to the named share and rebuild or restore HTML.
Current and previous environments both need the named path while retaining their
individual UID/GID values. The path checkpoint's saved rollback is distinct from
rolling back a publication or runtime identity. See the migration ledger for the
exact scope, remaining qualifications and retained private evidence.
