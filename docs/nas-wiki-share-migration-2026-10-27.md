# Wiki named-share migration — October 27, 2026

## Scope and authorization

The user authorized a **wiki-only exception** to the disk-2, power and retained-
snapshot migration gates, conditional on independent recovery and rollback.
They separately authorized adding a wiki read-only mount and recreating only the
repository NAS backup worker after confirming no capture is running. HBS, other
applications, account ownership and backup history remain outside this change.
These exceptions do not qualify the NAS for another service migration.

## Recovery and rollback prerequisites

The previously downloaded Hetzner wiki checkpoint was authenticated/decrypted
again. All outer and nested payload hashes passed. Current/retained runtime,
ACLs and site releases were independently restored into a private controller
scratch directory; retained-release checksums passed. Both source Git bundles
were independently cloned and passed full Git integrity checks. Live pointer
hashes matched the saved recovery checkpoint at the preflight.

The target is the QTS-managed `wiki` share on the existing system filesystem,
with canonical deployment root `/share/wiki`. Guest access is denied; encrypted
SMB and access-based enumeration are enabled. `wiki-reader` has read-only share
access; the existing deployment operator publishes. Admin authority remains a
platform exception. QTS ACL configuration alone is not effective-access proof.

Before the data move, retain exact current/previous environments, ACLs, backing
filesystem/inode identities, backup scripts/Compose/paths and crontab. Keep both
source and target publication locks while moving. Retain the old root as the
rollback location; use same-filesystem renames, not payload copies. Rebase only
wiki pointers, preserving numeric identities and both release payloads.

Rollback restores saved environments and backup inputs, reverses only the
recorded wiki renames after checking for later publications, and recreates only
the wiki and repository backup worker. Revert the wiki-specific controller
inventory/environment overrides separately. Never remove the share with its data
or discard the checkpoint as routine cleanup.

## Backup mapping

The backup worker keeps logical `wiki/` archive paths by overlaying the named
share read-only at `/source/usenet/wiki`. The manual capture similarly mounts it
at `/source/wiki`. `QNAP_WIKI_ROOT` selects the source; existing deployments default
to `/share/Container/usenet/wiki`. Capture records the physical source mapping in
`source_roots.wiki`, requires matching wiki pointers when configured, and refuses
active publication/migration. It excludes generated HTML and QTS recycle/snapshot
trees; versioned runtime and pointers remain protected. Restore into an isolated
local directory first, then place `wiki/` under the registered named share and
rebuild/restore HTML before starting the service. Never blindly restore the
logical archive namespace as an authoritative old Container-tree wiki.

The broader manual capture's prior timeout and unattended recovery qualification
remain separate from verifying this mapping and a new wiki-only checkpoint.
No HBS source selection, schedule, retention or credentials change.

## Migration ledger

- Independent recovery prerequisites passed.
- Named QTS share created with role-based read access. Actual runtime read/create-denial and unrelated-UID read/create-denial probes passed; share-root world access was closed without changing ownership.
- Exact rollback inputs encrypted off NAS and decryption verified. Root tests and 589 infrastructure tests passed (12 skipped); syntax checks passed. The documented historical secret-scan findings remain.
- Physical named-share cutover passed. The entire retained release directory was
  renamed on the same filesystem with its inode unchanged; no release history
  was deleted. Current/previous/candidate pointers were translated, preserving
  their individual identities. The old root retains only the publication fence.
- Durable inventory now selects `qnap_wiki_root: /share/wiki`; controller capture
  selects `QNAP_WIKI_ROOT=/share/wiki`. Encrypted preimages remain available.
- Wiki init and Caddy run at 1005:1000, group 1000 only, zero capabilities and
  no-new-privileges. Both application binds/root are read-only; runtime writes
  are denied. HTTP publication bytes are unchanged on both ports, and HTTPS
  retains the Authelia redirect. Other container start times are unchanged.
- The repository backup worker was idle before recreation. Its new wiki mount
  is read-only; crontab bytes and retention remain unchanged. Existing backup
  health/freshness checks pass, without treating the old success as new coverage.
- A new manual worker capture independently restored 469 files with all hashes
  valid. New wiki source mapping, current pointers and retained prior identity
  were verified. It did not modify scheduler status or prune any history.
- Post-migration encrypted supplement (8,290,970 bytes) was uploaded to the
  existing confined Hetzner wiki-checkpoint destination and downloaded again.
  Ciphertext hash, authenticated decryption, all nested payload hashes and an
  isolated restore of the named-share runtime/pointers passed. It references the
  preserved earlier account/HTML/printer recovery checkpoint rather than
  replacing it. Exact artifacts and receipts remain in private evidence.
- The user reran the interactive network check at 20:27 Eastern. The existing
  password matched the Samba credential; encrypted SMB session setup was denied
  and SSH password login created no session. This proves session/login denials,
  not independent authenticated tree-connect ACL tests for individual shares.

**Named-share migration complete within this wiki-only exception.** No HBS
configuration, credentials, source selection, schedule or retention changed.
No other application container was restarted. The private handoff is under
`build/wiki-identity-20261027/named-share-migration/`.

The supplement's source recovery is `smarthome.bundle` plus
`smarthome-working.patch`; place its `migration-ledger.md` at
`docs/nas-wiki-share-migration-2026-10-27.md` before running wiki checks. Use the
unchanged private printer bundle from the referenced earlier checkpoint. Source
patches are recovery evidence and may include concurrent controller documentation;
review them in an isolated checkout rather than applying them to a live checkout.

## Learnings and next steps

QTS creates a share root with platform ownership and initially permissive POSIX
other access. Configure share roles and test local operations separately; close
that root's world grant without changing application ownership. Publishers must
preserve the QTS root ACL rather than applying the legacy-root chmod.

Retained release history contained 99 directories. A recursive ACL read was
stopped when it exceeded the useful checkpoint scope; exact root metadata and
same-filesystem directory rename preserved the subtree without rewriting ACLs.
Capture now visits versioned runtime directories only, avoiding the generated
HTML and platform trees it never archived. The first cutover preflight rejected
an unsupported Docker process-list format before any service stop; the corrected
PID-bearing format verified that only cron was running before proceeding.

Next verify the first eligible unattended NAS capture and independent offsite
restore, including the new wiki mapping and a sufficiently recent native QTS
export. The proposed review window remains October 28 after 17:30 Eastern.
Keep the independent manual recovery supplement and exact rollback inputs.
Disk/power/snapshot diagnosis remains prerequisite work for another service;
this wiki exception is not a general NAS readiness clearance.

The user reported that the interactive access check took over a minute. Its
transport/preflight latency is the next scoped fix after this migration commit:
set a sub-minute non-interactive budget, diagnose stages before retries, and
avoid creating a temporary NAS container merely to read an existing credential
reference when an equally constrained existing read path can be qualified.
Password entry time is separate; timeouts must remain inconclusive rather than
being recorded as successful access denials.
