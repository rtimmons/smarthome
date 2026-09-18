# Usenet integration closure plan

## Current state — September 18, 2026, 18:14 UTC

The hybrid acquisition layout remains deployed and verified, but the first live
acceptance job has not completed. The fresh handoff audit shows the queue is
currently paused and the cart importer is failed; no manual release, reserve
reduction, or source deletion was used.

| Area | Current evidence |
| --- | --- |
| Queue | Six requests remain: five are paused and one is queued; no postprocessing is active. |
| SAB | Global queue pause is active. Both staging mounts remain active. |
| Admission | One request remains admitted; the controller is not blocked, but the admitted item has not progressed to import. |
| Automation | `usenet-capacity-admission.timer` and `usenet-cart-import.timer` are active. |
| Storage | Root free space is about **57.1 GiB**; remote staging free space is about **262.1 GiB**. |
| Hybrid layout | Marker is version 2 with native hardlinks enabled; migration receipt is `verified`. Radarr and Sonarr hardlink probes passed. |
| Importer | 34 completed journals, 24 held records, and zero disposal errors, but the importer service is failed and has not advanced the journal. |
| SAB floors | `/data/incomplete` and `/data/complete/remote/complete` remain configured with `30G` floors. |
| Health | Cloud health reports unresolved catalog failures and a Prowlarr issue; NAS health reports a failed catalog refresh. These are recorded as acceptance blockers, not waived. |
| Backups | Backup capture and restore are intentionally out of scope for this closure. Existing scheduling is not part of acceptance. |

The earlier 17:59 snapshot said the admitted request was advancing, but the
18:14 audit does not confirm that progress. Preserve the admission, queue pause,
held records, and source payload while diagnosing the failed importer; do not
manually release the queued item or restart the workflow blindly.

## Remaining acceptance

1. Diagnose and recover the failed importer using its durable journal and service
   logs, while preserving the admitted reservation and exact source inventory.
2. Let the admitted request complete through SAB postprocessing.
3. Confirm native Arr import creates the canonical hardlink, independent SHA-256
   verification succeeds, and exact source cleanup completes.
4. Confirm the importer journal advances without errors and the capacity timer
   admits the next eligible request automatically.
5. Confirm held identity records remain isolated and do not block unrelated
   eligible work. Resolve those records only with evidence; do not reacquire an
   unchanged rejected source.
6. Re-run the cloud and NAS health checks after importer recovery; resolve or
   explicitly document the catalog-refresh and Prowlarr failures before closure.
7. Record a sanitized completion receipt and update this plan with the final
   queue/import result.

Plex indexing of later imports, TV-specific acceptance, Arr-owned cleanup, and
deferred device playback remain separate follow-up work. They are not required
to declare the acquisition/import integration complete.

## File management portal — planned follow-up

Set up a small, private file-management portal using **filex** so the NAS,
download host, and Storage Box can be inspected and operated from one simple
web UI. This is an operator convenience layer, not a replacement for SAB,
Radarr, Sonarr, the importer, or the existing native NAS-copy workflow.

### Intended use cases

- Browse each host's approved filesystem roots from a browser.
- Sort directory listings by name, extension, size, and modification date;
  search for a file or folder by name and inspect its size and timestamp.
- Download individual files or folders to the operator's computer.
- Delete or move disposable download scratch, failed payloads, temporary
  archives, and other explicitly approved files.
- Copy or move selected files between the download host, NAS, and Storage Box,
  with a visible transfer state, error reporting, retry behavior, and
  verification before a source is removed.
- Keep transfers running when the browser is closed, where the selected
  filex workflow supports durable server-side progress.
- Provide read-only visibility into canonical media until a separate deletion
  policy has been reviewed and accepted.

### Proposed deployment shape

Run filex on the download host, where it can reach the three systems over the
existing private network and SSH/SFTP paths. Configure three separately named
storage roots rather than presenting one unrestricted filesystem:

| Root | Initial access | Scope |
| --- | --- | --- |
| Download host | Read/write | Approved incomplete/complete scratch and operational staging only |
| NAS | Read/write where explicitly approved | NAS cache and transfer staging; never the whole QNAP share by default |
| Storage Box | Read-only initially | Canonical library and remote scratch; write access requires a later review |

Use dedicated low-privilege credentials, host-key verification, TLS through the
existing private access path, and an application account with a strong secret.
Do not expose the portal directly to the public internet. Do not give the
portal shell access, unrestricted `/`, Docker control, or access to secrets,
application databases, importer journals, or backup keys.

### Safety rules

- The Storage Box remains canonical. Direct edits to canonical media must not
  bypass Arr ownership, importer journals, hardlink relationships, manifests,
  or independent verification.
- The NAS reader credential remains server-enforced read-only wherever the
  current design requires it. A writable NAS path must be a deliberate cache
  or staging path, not an accidental broader share mount.
- Deletion of canonical media, legacy media, shared hardlink sources, active
  downloads, or importer-owned payloads is disabled or excluded from the
  initial deployment.
- Prefer filex trash/quarantine or a reviewable staging area over irreversible
  deletion. If filex cannot provide an adequate recoverable-delete boundary,
  deletion remains unavailable and the existing guarded commands remain the
  only removal path.
- A cross-host move is accepted only after destination existence, size, and
  hash or equivalent transfer verification are recorded; the source is then
  removed only when it is disposable and the operation was explicitly
  authorized.
- The portal must not alter permissions, timestamps, filenames, or directory
  layout of manifest-managed media as a side effect of browsing or copying.

### Acceptance criteria

1. Deploy filex in an isolated service with pinned, reviewable configuration
   and a documented rollback/removal path. Confirm the deployed version,
   license, update source, and current security posture before enabling writes.
2. Confirm the portal is reachable only through the intended private access
   route and that unauthenticated requests, path traversal, shell execution,
   and access outside each configured root are rejected.
3. Browse all three roots and verify that filename, type, byte size, and
   modification date agree with independent host-side listings for a small
   synthetic fixture set. Confirm ascending and descending sorting by size and
   date.
4. Download a fixture from each root and confirm the resulting local file's
   byte count and SHA-256. Confirm folders can be downloaded without exposing
   unrelated sibling paths.
5. Create, rename, and delete only synthetic files in the approved writable
   scratch paths. Confirm the deletion is recoverable or produces a durable
   audit/operation record; confirm canonical and excluded paths reject the
   same actions.
6. Transfer synthetic files in both directions between every permitted pair:
   download host ↔ NAS, download host ↔ Storage Box, and NAS ↔ Storage Box.
   Confirm progress, retry after interruption, destination integrity, source
   preservation on failure, and source removal only after an explicit verified
   move.
7. Run the portal while a real SAB/importer operation is active and confirm it
   does not pause, resume, rename, delete, or lock active application files.
   Check that the existing health and importer-status commands remain healthy.
8. Document the approved roots, credentials/host-key ownership, deletion
   policy, transfer limits, backup treatment, and emergency disable procedure
   in the Usenet operations documentation. Record sanitized acceptance evidence
   without committing real media names, paths, credentials, or hashes.

### Explicit non-goals

This follow-up does not create a general-purpose cloud drive, synchronize the
whole library, replace Plex or Arr, add NAS-loss protection, expose the portal
outside the private access boundary, or authorize bulk deletion/reorganization
of canonical media. If filex cannot safely provide the required cross-storage
operations, evaluate Filestash as the fallback before considering a custom
frontend; custom code should be limited to our safety/policy integration.

## Operating invariants

- Keep both SAB free-space floors at `30G`.
- Keep the global SAB queue resumed unless the controller fails closed or a
  live safety check requires a pause.
- Do not manually release queued requests or clear durable holds.
- Do not lower reserves, resize the VM, purchase storage, or delete canonical
  or legacy media to make admission pass.
- Keep acquisition serialized through admission, native import, verification,
  and cleanup before admitting another item.
- Preserve all importer journals, SAB history, activation provenance, and
  disposal receipts.
- Preserve the version-2 hybrid marker, local incomplete spool, remote staging
  mount, shared Arr `/storage` mount, and native hardlink mappings.
- If a timer or controller fails, inspect its durable state and live mounts
  before changing queue state. Do not replay a migration with an existing
  `hybrid-scratch-setup.json` receipt.

## Verification commands

Use the repository-owned read-only checks from the repository root:

```sh
just usenet-cart-import-status
just usenet-cloud-health
just usenet-qnap-health
```

For a sanitized queue/migration snapshot:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra \
  --command python3 build/queue-repair-20260918/run-handoff-audit.py <unique-name>
```

Private operational evidence remains in the ignored, mode-0700 directory
`usenet-infra/build/queue-repair-20260918/`. Do not commit media names,
identifiers, URL hashes, credentials, or raw logs.

## Implementation status

The deployed implementation uses local compressed acquisition scratch, remote
unpack staging, native hardlinks through the shared Arr mount, independent
canonical hashing, and exact cleanup. Same-filesystem bind mounts are validated
through the kernel mount table, with a local fallback where `findmnt` is absent;
both affected test suites pass (**60 tests**).

The migration and live hardlink probes are complete. The only outstanding
integration evidence is the current job's import, verification, cleanup, and
the next automatic admission. No backup action is required for this plan.
