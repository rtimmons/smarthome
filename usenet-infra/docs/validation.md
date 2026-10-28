# Validation and recovery claims

For storage migration, start with the [NAS migration plan](../../docs/plan-nas-storage-and-access.md).
It owns current scope, exceptions and acceptance. This page owns repository
checks and the limits of operational evidence; old implementation milestones are
not today's work queue.

## Required checks

Run `just --justfile usenet-infra/Justfile --working-directory usenet-infra test`
for infrastructure implementation changes. It covers unit tests, shell/YAML,
Ansible syntax and secrets. Root `just test` and `just wiki-check` cover shared
integration/documentation changes under root AGENTS.md.

The full-history secret scan reports two documented
[historical RSA keys](security-findings.md). Report them separately from a passing
`scripts/secret-scan --no-history` source/index check. Do not add exceptions or
rewrite history to make validation green. Inspect staged paths, complete diff
and commit message for media privacy as well as secrets. Offline tests do not
establish live permissions, playback, backup completion or a usable restore.

## Operational acceptance

For each changed scope, record configuration versus effective-access tests,
source/destination identity, affected consumers, recovery evidence and rollback.
Use bounded metadata and synthetic tests; do not replay downloads or traverse
entire media trees merely to reproduce a receipt. Keep raw/identifying evidence
in ignored private storage.

The private-library migration allows temporary exclusion from backups using the
existing B2 copy reported by the user. It does not require a completed replacement
seed before moving data. Follow the plan's NAS-side rename and post-move re-seed
sequence; never infer that the old mixed backup can be deleted from a settings-
only sample restore when private-library coverage was excluded.

## Evidence references and limits

- [October closure](../recovery/drills/closure-20261008.json) records the completed
  earlier deployment acceptance. Preserve its journals and immutable snapshots;
  it is not evidence of present storage health or replacement NAS boot recovery.
- [Backup runbook](scheduled-backups.md) and [backup repair](backup-repair-2026-10-27.md)
  distinguish producer captures, offsite readback, restored artifacts and pending
  unattended qualification. An upload of an old export is not fresh source recovery.
- [Wiki migration ledger](../../docs/nas-wiki-share-migration-2026-10-27.md)
  records completed identity/share, independent recovery and access-check evidence.
- [Storage preflight](../../docs/nas-preflight-2026-10-25.md) retains unresolved
  SATA/I/O, snapshot and UPS findings. “Good” disk summaries do not clear them.

NAS originals, artwork and installation binaries are outside settings-only
capture. Native HA backups and Time Machine each require their own restoration
contract. A successful sample or application restore is not a full-library,
whole-NAS, client-codec or all-user privacy guarantee.
