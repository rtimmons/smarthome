# Forgejo capture-account checkpoint

Updated October 29, 2026. **Account created; worker activation remains proposed.**
QTS-local `svc-forgejo-backup` is UID 1007/GID 100, with only `everyone` membership.
The user approved this restricted creation and completed password entry in QTS.
Saved UI verification shows all application/network grants unchecked, no share
access, and an explicit Public denial overriding its inherited read grant.
Recursive share propagation was unchecked. At 12:45:47 Eastern, a separate
capability-free 1007:100 probe received EACCES opening Forgejo data, configuration
and archive directories. This is filesystem denial evidence, not authenticated
SMB acceptance. Private evidence: `build/forgejo-backup-account-20261029/`.
No capture scheduler, source ACL, archive permission or worker identity changed;
the bounded privileged capture exception remains active. Continue from the
[NAS migration plan](plan-nas-storage-and-access.md); this document scopes its
`svc-forgejo-backup` follow-up, not another migration queue. The
[access model](plan-nas-access-model.md#accounts--roles) and
[data protection policy](plan-nas-data-protection.md#job-owners-and-access)
own the target roles. Existing unattended-capture qualification is a separate
acceptance item and must be recorded before changing the producer identity.

## Current implementation and the actual gap

The October 28 migration checkpoint records `/share/forgejo`, resolved through
QTS to `/share/CACHEDEV1_DATA/forgejo`, with runtime `svc-forgejo` (`1006:100`).
The share root is deployment-owned (`1004:100`), mode 0700; runtime-owned `data`
and `config` contain private files. These are dated observations, not a fresh
permission inspection.

[`git-host/backup.sh`](../git-host/backup.sh) runs from admin cron and controls
only `home-git-forgejo-1`. It validates the QTS share mapping, owns
`backup.lock` and `backup-resume-required` in the service root, checks the
23-hour eligibility gate, stops Forgejo, captures, and starts it before upload.
The helper uses UID 0/GID 100 with only `DAC_OVERRIDE`, no network, a read-only
container filesystem and read-only `/source` bind. Its only persistent writable
mount is `/share/Usenet/Backups/automatic/forgejo`. The helper receives the public
recipient and age executable, no Docker socket or private offsite/decryption key.
A previous nonroot capability probe had zero effective capabilities; changing
`--user` while retaining `--cap-add` is not a qualified solution on this NAS.

[`git-host/backup.py`](../git-host/backup.py) captures exactly `data`, `config`,
`compose.yaml`, `backup.sh`, `backup.py` and `install-cron.py`. It reads the
configured SQLite database, checks integrity, includes retained WAL/SHM, rejects
symlinks, hashes files and streams a manifest plus files into age. It requires
space for twice the input plus the existing 100 GiB reserve. Ciphertext is mode
0600; receipts are mode 0640. A new account therefore needs actual read access
to existing private descendants and an explicit archive ownership contract.
Root traversal alone is insufficient.

Publishing currently runs the same Python program inside
`usenet-backups-backups-1`. This existing uploader has the confined Storage Box
credential and performs upload, downloaded ciphertext comparison, receipt/status
updates, pending removal and local retention. Thus it currently needs archive
**write** access, not merely the future `archive-readers(forgejo)` role. Simply
granting a new producer read/write access and making the uploader read-only would
break publication. The current backup installer also requires archive owner UID
1004 and chmods its directory to 0700; deployment must not silently undo the new
permission model.

## Bounded target

Keep the archive at `/share/Usenet/Backups/automatic/forgejo`, the current HBS
selection, the existing encryption recipient, image/tool pins, retention,
reserve and 23/36-hour freshness rules. Do not create or move `forgejo-backups`
during this account checkpoint. Keep `svc-forgejo` and its data ownership intact.

| Principal | Proposed capability | Explicit exclusions |
| --- | --- | --- |
| `svc-forgejo-backup` | Nonroot capture worker; read/traverse the exact recovery inputs; create encrypted output and producer receipts in the existing Forgejo archive subtree | Source writes, other service/archive roots, Docker access, interactive/SMB access, offsite credentials, recovery private key |
| Fixed host lifecycle broker | Validate mapping, locks and eligibility; stop/start only the verified Forgejo container; launch the fixed capture worker and existing publisher | Caller-selected paths, image, container, commands, mounts or environment; general Docker API |
| Existing uploader | Preserve current confined Storage Box upload/readback and current local publication/retention writes during this checkpoint | New source mount/grant, new offsite destination, B2 account expansion |
| Deployment operator | Install protected broker/worker code and manage its definition | No transfer of deployment ownership to the capture worker |
| Runtime `svc-forgejo` | Existing service-state access | Archive mounts, archive read/write, backup-control and cloud grants |

The broker should remain host-owned and scheduled by the existing admin cron.
The dedicated account is the worker identity, not an interactive Docker operator.
A fixed broker invoking that worker satisfies the bounded lifecycle role without
giving the worker permission to call Docker. Do not add it to an administrators,
Docker or broadly privileged group. No user-facing login or share grant is needed.

The broker and worker program must be non-writable by runtime and capture
accounts, including their parent directories. Preserve separate deployment
ownership. Validate the expected container identity and bind mapping before
stopping it; refuse a substituted source, helper, output or container. A worker
must not be able to replace code later executed by the broker or publisher.
Keep locks and the resume marker broker-owned in their current location for
this checkpoint; their future move to `backup-control` is separate.

## Permission probes that must settle before implementation

1. Resolve the proposed account by QTS name and record its actual UID/GID,
   supplementary groups and enabled services; do not assume the next UID or
   grant rights through the broad `everyone` group. Use supported QTS account
   management. No password/key/login needs provisioning just to run a container
   at the numeric UID.
2. Privately inventory metadata for the bounded Forgejo recovery set and its
   ancestor directories: owner, mode, access/default ACL, mask and relevant xattrs.
   Test nonroot reads first in an isolated synthetic directory with private
   modes, nested directories and SQLite WAL/SHM. Probe creation under the current
   Forgejo umask and file replacement: default ACL inheritance can be limited by
   creation modes or later chmod. A one-time read of today's files cannot prove
   tomorrow's keys/database are readable.
3. Select an explicit source-read mechanism only after that probe. Preferred
   candidate: named-account read/traverse ACLs on the enumerated existing recovery
   set and defaults on its mutable directories, with no source write bit.
   Applying those ACLs to descendants is a **separate, reviewable ACL change**,
   not an incidental account-creation step. Compute and review effective ACL
   masks for every affected entry: increasing a mask can activate unrelated
   existing group/named-user grants. Reject a broad `chmod`, group change or
   recursive chown fallback. If durable nonroot read access cannot be demonstrated,
   retain the documented bounded root helper and report this checkpoint blocked.
4. Probe the archive handoff with synthetic files: new capture UID creates mode
   0600 ciphertext and 0640 receipts; existing publisher can read and update only
   the intended subtree; capture can read publisher status and write pending
   receipts on retry. Preserve private archive directory isolation and runtime
   denial. Explicitly account for existing files and atomic `.new`/rename/delete
   operations. Do not rely on a shared GID 100 permission change across the
   `Usenet` parent. Current uploader UID/capabilities need live confirmation.
5. Inspect source/control path ownership, QTS ACL behavior and both cron tables
   without changing them. Capture the current scripts, mappings and relevant
   ACLs as private rollback inputs. Verify no active capture or pending upload
   before a permission cutover; do not remove active locks to proceed.

The role model's eventual read-only uploader needs a later protocol split:
publication acknowledgement outside the immutable archive payload, with producer
finalization/pruning. That is not claimed here. Until implemented and qualified,
record the existing uploader's bounded local-write exception explicitly.

## Implementation and acceptance sequence

1. Finish the non-mutating probes and produce the exact account settings,
   per-path ACL delta and broker change for review. Keep identity provisioning,
   source ACLs and worker switch as separate rollback checkpoints. Refresh NAS
   health and job activity; do not interrupt the replacement HBS seed or move its
   sources. A Forgejo capture requires its own bounded service-stop window.
2. Update `git-host/backup.sh` to resolve/validate the dedicated worker identity,
   remove `DAC_OVERRIDE` from that worker, retain `--cap-drop ALL`, RO source,
   no network and resource limits, and enforce broker-owned paths. Update
   `manage.py` archive owner/permission assertions and script installation so
   `backup-update`/`backup-deploy` preserve the approved model. Change receipt
   comments/contracts in `backup.py` only to match verified behavior. Preserve
   the current publishing implementation and its bounded exception.
3. Add targeted offline tests for identity failure, wrong share/container/path,
   source denial, archive handoff/retry, lock cleanup and restart on capture
   failure. Include malicious symlink/path replacement and worker-writable
   executable rejection where the broker accepts filesystem inputs. Run
   `just git-host-test`, required infrastructure checks for affected integration,
   and root `just test` before coordinated deployment. Documentation needs
   `just wiki-check`; acknowledge only the component fingerprints reviewed.
4. In the approved bounded capture window, inspect the actual worker UID/GID,
   effective capabilities (zero), mounts and network. Prove all enumerated source
   inputs readable, synthetic writes denied, unrelated roots inaccessible and
   runtime archive denial preserved. Do not modify real service files to test
   write denial. Capture/restart must pass database/cache health and leave no
   active lock/resume marker after success.
5. Verify the full new archive independently after offsite readback: manifest
   hashes, SQLite integrity, repository integrity and required recovery inputs.
   Preserve failed/pending archives for diagnosis. Then qualify the next eligible
   unattended cycle with cron invocation evidence, new capture, verified upload
   and independent restore. A manual capture resets the 23-hour clock and is not
   unattended qualification. Record dates, IDs/counts and private evidence paths
   without repository names, secrets or incidental media identifiers.

## Rollback and completion limits

Restore the prior broker/worker scripts and exact saved ACL entries if the
nonroot worker cannot capture or the uploader cannot finish. Reconcile only this
job's entries in the active and persistent cron tables independently if changed;
never replace an entire cron table. Keep later data writes and every encrypted
archive, receipt and pending upload. Recover Forgejo through the existing
resume-marker procedure only after confirming no active capture. Disable the
new account's access if abandoning the checkpoint; do not delete/reuse its UID
while any retained objects reference it. Restore each ACL checkpoint separately
without undoing unrelated permission changes.

Completion requires both effective least-privilege tests and recovery acceptance.
Creating an account, launching a nonroot process, a passed status command, or an
uploaded archive alone proves neither. This proposal neither qualifies current
unattended backups nor retires the existing privileged-capture exception.
