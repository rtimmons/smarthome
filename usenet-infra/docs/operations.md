# Operations

Use the root `just` recipes below. Dedicated identities and pinned hosts come
from ignored `.env` and Ansible inventory. Recover missing credentials through
[secrets recovery](secrets-recovery.md); do not repeat account setup or purchases.
Application addresses are in the [README](../README.md).

## Health and requests

```sh
just usenet-native-ownership-status
just usenet-discovery-health
just usenet-cloud-health
just usenet-qnap-health
just usenet-filex-status
just usenet-seerr-status
```

Start explicit requests in Seerr or Arr. RSS and direct carts stay disabled.
Check the intended movie/episode scope and wait for import/cleanup before another
large request. A failed release needs deliberate selection of an alternative;
never replay a request with an uncertain response before reconciling its exact
Arr/SAB identity. Preserve manual pauses, failed payloads and history.

Cloud health verifies native ownership and reserves; missing native state is an
error. Retired-worker holds remain informational and their journals are retained.
Unresolved catalog errors remain failures. Inspect detailed status privately:
raw application responses and paths can contain credentials and media identities.

## Selective NAS copies

```sh
just native-list
just native-status
just native-pull 'native-<id>'
just native-evict 'native-<id>'
just catalog-list
just catalog-status
just catalog-pull '<item-id>'
just catalog-evict '<item-id>'
```

Use IDs from the current listing. Pull verifies the selected source and local
copy; eviction removes only the owned NAS copy. Canonical storage remains
read-only from the NAS. Retain the 100 GiB reserve and separate staging/library
roots. Never bypass a checksum, changed-source, ownership or destination-collision
failure. See [native media](native-media.md) and [download status](download-status.md).

Closing the browser does not cancel a running transfer. The Downloads panel
reports copy, verification and publication separately. A stale heartbeat or
interrupted transfer needs inspection; do not call it complete based on bytes
copied. Refreshing presentation does not install missing storage mounts.

## Deployment

Inspect health and active transfers first. Deploy only the affected component;
never restart Plex, the NAS or unrelated services for a Usenet refresh.

| Root recipe | Scope |
| --- | --- |
| `usenet-configure-native-ownership` | Refresh current native health helpers and verify existing ownership; no migration or application restart |
| `usenet-configure-discovery` | Deploy pinned Arr applications and verify restored explicit-request policy |
| `usenet-configure-download-status` | Refresh existing NAS transfer backend/presentation; refuses active transfers |
| `usenet-wiki-deploy` | Static private field guide, with retained-release rollback |
| `usenet-configure-filex` | Reviewed private Filex portal |
| `usenet-configure-seerr` | Private Plex-authenticated request portal |
| `usenet-configure-scheduled-backups` | Cloud and NAS configuration backup schedules |

Use `just --list` for exact recipe arguments and component bootstrap commands.
Historical cart, publisher and storage migration recipes were removed. Recover
the current layout from verified state and current mount definitions instead of
replaying the branch's development sequence. Old encrypted archives may contain
retired executables: do not enable their timers or run them after restore.

For application updates, review image pins and version checks together, capture
and independently restore a current backup, retain stopped rollback config, and
recreate only the selected idle services. Verify authenticated health, ownership,
mount guards and preserved journals before capturing a new accepted checkpoint.
Do not use floating image tags.

## Recovery and access

[Scheduled backups](scheduled-backups.md) describes freshness, off-host readback
and retained scope. [Recovery](recovery.md) covers isolated verification and
restoration; [repair storage](repair-spool.md) covers mount reconstruction.
A successful upload is not proof of a decryptable, complete archive.

For Filex, keep `just usenet-filex-ui` running and browse
`http://127.0.0.1:15213/`. Use the operator account; preserve host trust policy.
[Filex](filex.md), [Filex recovery](filex-recovery.md), [Seerr](seerr.md) and
[LAN access](lan-ui.md) contain their component-specific controls.
