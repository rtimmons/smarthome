# Private NAS Usenet wiki

The static field guide is source-controlled under [`../wiki`](../wiki) and is
served on the private NAS at `http://192.168.1.66:8090/`. It explains the
ecosystem, this installation, routine workflows, storage boundaries and safe
first-line troubleshooting. It deliberately has no live status, media listing,
application API calls, credentials or control actions.

The private address is reachable on the home network and its existing VPN path.
There is no public listener, new VPN, separate wiki login or router exposure.
Links to existing private applications retain those applications' authentication.

## Edit and validate

Edit `wiki/index.html`, `wiki/styles.css` or the SVG assets directly. There is no
frontend build, package manager, database or browser editor. CSS and SVG links
carry a `v` query equal to the first 12 hex digits of that file’s SHA-256. Update
the corresponding link after changing an asset; the wiki tests reject stale
versions so returning browsers receive the new content. Keep real media
identities and token-bearing API/RSS links out of the page.

From `usenet-infra/`, run:

```sh
just test
```

The wiki tests resolve local files and fragments, pin the approved external and
private shortcuts, validate SVG, require mobile/keyboard behavior, and inspect the
Compose/Caddy/rollback boundary. The infrastructure test also syntax-checks the
dedicated playbook and runs current-source plus historical secret scanning under
the repository's documented policy.

## Deploy

From the repository root:

```sh
just usenet-qnap-health
just usenet-wiki-deploy
```

The dedicated Ansible playbook reruns read-only NAS preflight, requires the exact
private address and a free TCP 8090, calculates a content-addressed release,
validates Compose and Caddy, and starts only the `usenet-wiki` project. The pinned
Caddy 2.11.4 image runs as the existing non-root NAS account with a read-only root
filesystem, dropped capabilities and no Docker socket, media, secrets or writable
host mount. Only the immutable site release and Caddy configuration are mounted,
both read-only.

The live smoke check verifies the exact `192.168.1.66:8090` publication, healthy
container, expected immutable release mount and page marker. A failed update
restores the prior release environment and recreates only the wiki container. A
failed first deployment stops only that new project. Previous content releases
remain under `/share/Container/usenet/wiki/releases/`; do not remove them until a
later release is accepted and its rollback window has passed.

## Inspect and roll back

Normal updates use the same deploy recipe. The last successful prior environment
is retained on the NAS as `.env.previous`. The playbook performs automatic rollback
when its deployment smoke check fails. If a later application-level issue requires
manual rollback, first inspect the current and previous files through the dedicated
QNAP identity, confirm that `.env.previous` points to an existing immutable release,
then copy it to `.env` and recreate only the `wiki` service. Record that manual
intervention rather than deleting the failed release.

The wiki source is included in the repository and normal checkout/configuration
backup paths. That makes the page reproducible; it does not add a backup of media,
the whole NAS or external account state. Recheck delivery from a connected VPN
client after relevant network changes.

The initial September 17 UTC rollout passed exact binding, container health, live
browser delivery, idempotence and a controlled bad-candidate rollback drill. LAN
delivery passed; no connected off-LAN VPN client was available. See the sanitized
[deployment receipt](../recovery/drills/wiki-deployment-20260917.json).

The September 20 update published the accepted native request flow, separate Arr
ownership, retired cart intake, conservative limits, expanded storage and the
completed movie/episode/repair/restart evidence. Isolated deployment and live
browser delivery passed; playback and broader concurrency remain unclaimed.

A follow-up completeness audit added Filex access and staging/recovery boundaries,
selective NAS-copy instructions, verification policies, dated storage costs,
remaining health findings and precise Plex acceptance. The system diagram now
shows Arr sending jobs to SAB and the Storage Box feeding both playback and NAS
copies. Asset versions prevent stale cached diagrams/styles; the diagram can
scroll independently on narrow screens and introductory cards avoid text overlap.

The [completeness audit receipt](../recovery/drills/wiki-refresh-20260920.json)
records the final source fingerprints, nine passing wiki checks, isolated
deployment and live browser verification of the refreshed content and diagram.
