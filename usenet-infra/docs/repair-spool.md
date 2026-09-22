# Dedicated repair volume

The September 20, 2026 approved expansion is deployed. A 300 GB cloud block
volume backs `/srv/usenet/repair/incomplete`, bound at the existing host path
`/srv/usenet/downloads/incomplete` and SAB path `/data/incomplete`. The VM remains
CX43. Completed output and canonical media stay on the existing Storage Box,
now BX21. See the [expansion record](storage-expansion-20260920.md).

The former `/srv/usenet/downloads/incomplete-local-spool` remains untouched:
535 files, 28,639,139 bytes, independently hashed before and after copying.
It is a dated rollback source, not a synchronized copy of future downloads.
Do not delete it, reformat the new volume or replay the earlier hybrid migration.

## Ownership and capacity

`terraform/cloud/repair-spool.tf` manages the volume and attachment, with provider
deletion protection and Terraform `prevent_destroy`. The private cloud tfvars
must retain `repair_spool_enabled = true`; storage tfvars must retain `bx21`.
Older SOPS-bound inputs predate both changes and must not silently replace them.
Do not apply saved provisioning plans again. Reader-account drift was excluded.

The root-owned `config/catalog/repair-spool.json` pins the provider volume ID
and filesystem UUID. The controller verifies both resolve to the same block
device, the actual mounted filesystem matches it, and the incomplete bind has
the device/inode of `repair/incomplete`. The root disk, repair volume and remote
filesystem each retain their own inode and 30 GiB reserve checks. SAB's two
`30G` floors remain unchanged. The legacy capacity-admission worker is now
retired under native ownership; the mount checks remain available for inspection.

The post-expansion preflight measured 291.18 GiB free on the formatted repair
filesystem and 4.06 TiB remotely. This covers the recorded workload, including
full PAR2 replacement and remote import-copy fallback. Native controls enforce a 100 GiB release limit, with a 100 GiB planning
allowance for unpacked output;
free capacity alone does not bound archive expansion or concurrent arrivals.

## Mount and restart behavior

`srv-usenet-repair.mount` mounts the filesystem by UUID with
`nodev,nosuid,noexec`. The `repair-spool.conf` drop-in for
`srv-usenet-downloads-incomplete.mount` changes its source and adds
`Requires`, `BindsTo` and `After` dependencies on the repair mount. SAB and
discovery already bind to the incomplete mount: stopping it stops both SAB
and Arr. Restore the repair mount, incomplete bind, SAB and discovery in that
order, then check actual filesystem identity and API health before restoring
intake. Never assume starting SAB also restarts Arr.

Both uncovered mount directories are root-owned mode 0000 and empty. Live
verification stopped the repair mount and proved the dependencies stopped,
both underlying directories rejected writes as `usenet`, and SAB could not
start while the repair mount was effectively masked. After restoring the unit,
the services recovered and queue/history, journals, holds, feeds, global pause
and all three timer states matched the saved baseline. The first simulation
used an ineffective runtime mask beneath the existing `/etc` unit; it was
restored and repeated with a verified `LoadState=masked`. No volume was detached.

## Deployment and interruption recovery

The deployment entrypoint is `just usenet-configure-repair-spool <volume_id>`
from the root, using the ID from private cloud Terraform output. It is already
deployed. Repeating against a verified receipt refreshes the helper, checks
identity/resources/dependencies and preserves backup permissions; it does not
format, recopy or restart the services. An interrupted or mismatched receipt
is refused for explicit phase review.

The durable receipt is `state/catalog/repair-spool-setup.json`. It records the
original queue/history, feed flags, pause, timer states, fingerprints and source
inventory. It and `repair-spool-controller-before.py` are root-owned,
group-readable by the backup account, with no group/world write access.
The helper also remains readable by that account. Runtime configuration and
these receipts fall under the existing encrypted configuration-backup allowlist;
the repair payload and `/etc/systemd/system` unit files do not. Do not infer a
whole-machine recovery test or a new independently restored archive from this.

If interrupted, keep intake held and inspect the exact recorded phase and live
mounts first. `format_intent`, `formatted`, `copy_intent` and `copied` require
manual reconciliation; do not repeat formatting or copy into an occupied target.
The helper exposes `resume-quiesce` only for the unchanged original binding and
empty destination, and `resume-bound` only for an already established new bind.
Both preserve the original baseline. They are recovery actions, not generic
retry commands. The deployment's two interruptions were reconciled this way:
SAB feed-write acknowledgement required readback, and discovery needed explicit
restart after its mount dependency stopped. Both corrections have regression
coverage; the final receipt is `verified`.

For rollback, first disable feed intake, pause SAB, stop the admission/import/
incomplete-maintenance timers and wait for writers to finish. Reconcile every
new job against the old spool; never replace newer metadata with the preserved
September 20 copy. Only with a verified idle baseline may the incomplete bind
drop-in, controller and marker be restored to their saved original versions.
Stop SAB/discovery before switching mounts, preserve mode-0000 protection,
verify root-disk capacity and the exact original bind, then restore saved
settings. Retain the new volume and all receipts; deleting or detaching it
requires a separate disposition decision.

## Acceptance boundary

A 128 MiB synthetic PAR2 repair passed independent SHA-256 verification. Both
Arr users passed live hardlink probes, and the NAS reader still rejects writes
and deletion. Temporary probe files were removed. All three held requests,
44 historical journals, ten capacity holds and 27 importer holds were preserved.
The original spool was retained; no canonical media was copied or deleted.

The later native acceptance reconstructed an 80 GiB synthetic PAR2 source with
independent SHA-256 verification, while retaining both complete copies. Peak
simultaneous allocation was 171,833,499,648 bytes; 140,820,086,784 bytes remained
free at full replacement. The temporary fixture was removed. Native movie and
episode import/cleanup and the final scoped service restart also passed. See
[native cutover](native-cutover.md) for Plex discovery and the final receipt.
This demonstrates the measured case, not arbitrary archive expansion or broader
concurrency. Conservative queue controls remain enabled. The user accepted
native Arr cleanup for new requests; historical independent verification
receipts remain preserved.

## September 22 bounded concurrency and expansion

With SAB idle, two concurrent synthetic gzip streams each expanded to **50 GiB**
and passed SHA-256 verification while **100 GiB** of separate input allocation
remained reserved. The compressed fixture was 234,272,195 bytes, approximately
229:1 expansion per stream. Peak allocation was **214,982,672,384 bytes**
(200.22 GiB), with **97,677,574,144 bytes** (90.97 GiB) still free. The test took
544 seconds; all its temporary files were removed. The live queue was unchanged.

This extends the earlier 80 GiB PAR2 repair evidence with a bounded concurrency
and high-expansion case. It does not prove unbounded archive expansion or two
simultaneous 100 GiB repairs safe. Native queue controls, the 100 GiB release
limit and 30 GiB reserve floors remain unchanged. The receipt is in the
[September 22 closure record](../recovery/drills/closure-20260922.json).
