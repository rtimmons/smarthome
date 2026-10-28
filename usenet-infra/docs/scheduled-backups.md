# Scheduled configuration and NAS backups

> **Private-library migration coordination:** the [current NAS plan](../../docs/plan-nas-storage-and-access.md#fromdrobo-data-migration)
> permits temporarily excluding the private-library dataset from affected jobs,
> moving it on the NAS, and re-seeding from `PrivatePlexLibrary` afterward.
> Preserve the existing B2 recovery copy. If the replacement seed excludes this
> dataset, its completion plus a settings sample restore does **not** authorize
> deleting the old mixed backup repository. Apply the [complete retirement condition](../../docs/plan-nas-data-protection.md#private-library-migration-exception)
> before any earlier seed-completion follow-up retires that history.

## Backblaze B2 coverage

On October 17, 2026, the user confirmed that B2 should protect irreplaceable
files and configuration, initially including both Mac Time Machine shares, while
excluding replaceable media. On October 19, the user retired the SpaceGray backup.
After the October 28 private-library exclusion, both `Backup 1` and
`B2 QuDedup 20261027` select exactly:

- `Public/RyMongo Backups`
- `Public/Saved Downloads`
- `Usenet/Backups`
- `SpaceBlackTimeMachine`

The private dataset now lives at `/share/PrivatePlexLibrary` and is temporarily
excluded from both jobs. Retain its existing B2 history until new-root coverage
and the protection plan's recovery gates pass. At migration handoff both jobs
were stopped; legacy daily 02:00 scheduling remains enabled and the replacement
remains manual at 10 MiB/s. Coordinate resumption with Time Machine recovery.
Source-removal edits preserved retention, destinations and all other job settings.

On October 19, `SpaceGrayTimeMachineShare` was removed from the job's future
source selection and its QNAP share/data were deleted through Control Panel.
Read-only verification confirmed both the share and underlying directory absent
after background deletion completed (about 411 GiB removed). The current laptop
(`SpaceBlack M4 Max`) uses `SpaceBlackTimeMachine`,
which remains selected and intact. Existing B2 versions were not manually purged.

The former whole-`FromDrobo` selection included replaceable movies/TV, remote
mounts and caches. Those paths are no longer selected. Source files are never
deleted by the job, and no existing B2 versions were manually purged. Retention
remains the latest 30 versions, with backups daily at 02:00 NAS local time
(America/New_York). Snapshots remain enabled; preservation of ACLs and extended
attributes is enabled for recovery of the newly included data. As of October 27,
quick integrity checks run Mondays at 16:00; full content checks run on the first
of each month at 17:00. These replace the former 06:00 schedules, which overlapped
the daily upload. Full content checks download data and consume bandwidth; account
egress allowances must be considered separately from storage charges.

On October 19, the user-requested upload cap was saved through HBS as **10 MB/s**,
with **Always on** and all seven days selected. Read-only configuration verification
confirmed 10,485,760 bytes/second (HBS uses binary megabytes). Download remains
unlimited. Select Saturday and Sunday explicitly: choosing Always on alone retains
the dialog's weekday selection. The job was idle when changed; no backup was
interrupted or manually started. This reduces backup traffic during Plex use,
but playback under a capped backup has not yet been verified.

The October 17 audit verified 30 consecutive successful runs of the **previous
selection**, most recently at 02:20 Eastern. The first expanded run completed
successfully on October 18 at 14:15 Eastern, transferring about 1.85 decimal TB.
The October 19 run also succeeded, finishing at 04:42 after transferring about
355 GB; its selected source size was 4.845 decimal TB. HBS reported the October 19
06:00 quick integrity check as `Good`. These are job and integrity-check results;
a B2 sample restore was not yet verified. The October 25 settings-file sample
below subsequently passed. Do not equate a successful upload or a
quick integrity result with demonstrated recovery of the selected sources.

Client-side encryption is disabled, and HBS does not allow it to be enabled
on this existing job. Any encrypted replacement needs its own reviewed recovery
password, destination, migration and retention plan. B2 bucket privacy,
server-side encryption, application-key permissions and lifecycle policy were
verified in the signed-in account: `RynapQNAP` is private, new uploads receive
SSE-B2 encryption, and the `RynapQNAPHbs3` application key is restricted to that
bucket. The bucket keeps all file versions; HBS separately retains 30 backup
versions. Object Lock is disabled. Do not change lifecycle or Object Lock rules
without checking compatibility with HBS version management.

The account audit reported 5,688.4 GB in the bucket, more than the selected current-copy
size. The roughly $34/month estimate for 4.83 TB excludes retained versions and
existing backup data. At the audit's published $6.95/TB/month rate, the bucket
alone was roughly $40/month before the expanded upload and future version growth.
No old cloud data was purged to reduce that figure. B2 storage and download
caps are unset, so no configured cap currently blocks the expanded upload.

The job's failure trigger is enabled. The Notification Center HBS email rule is
now enabled for Warning and Error across all six HBS categories, including
Custom Job Event and Job Status, to the existing recipient. The user completed
Gmail reauthorization and QNAP cleared its expired-account warning, but the
authorized test email failed at 10:48 Eastern. QNAP logged its generic
`error(401) msg(sendmail fail)`; this does not identify a Google authentication
failure. TLS connections to Gmail on ports 465 and 587 passed from the NAS backup
container. Alert delivery was still unverified at that checkpoint.
The user then ran QNAP's documented Notification Center stop/start workaround;
one authorized retry at 10:57 also failed with the same generic error. The rule
was enabled, but delivery remained unverified at that point. Notification
Center was 1.10.0.3331 on QTS 5.2.10. The October 25 reauthorization and inbox
verification below resolved delivery using the existing account.

Manage HBS jobs through QNAP's interface; database inspection is read-only.
Use the dedicated NAS identity and pinned hostname from private inputs. Do not
print account credentials, raw configuration databases or private media names.
Inspect selected source roots, run counts/status, saved schedules and sanitized
receipts. Recovery should first use a small file restored into a separate test
directory, never overwrite live source data.

## October 25 HBS update

HBS was updated through the official QNAP App Center from 26.4.5.115 to
26.4.6.205 while idle. Before updating, the existing single job showed Success
for its October 25 11:38 backup, with the five selected source folders, daily
02:00 schedule, existing B2 destination and upload limit intact.

Both SQLite configuration databases passed integrity checks before and after.
The complete `jobs`, `accounts`, `credentials`, `config` and `hbs_config` table
fingerprints matched exactly across the update; only the cloud-information
cache changed. This preserves the job selection, scheduling, retention, rate
limit and saved destination credentials without recreating a job or account.
Encrypted NAS settings archives verified before and after the update include
the HBS databases; all three post-update scopes passed off-host upload and
readback. Notification delivery was verified separately afterward, as recorded
below; a successful package update alone did not establish mail delivery.

A post-update native HBS **Quick Check** against the existing B2 backup finished
with **Good** on October 25; the job returned to **Success**. The unchanged
scheduled job remains enabled. This verifies live destination access and HBS's
quick integrity checks, not a new backup upload, full content check or sample
restore. Those distinctions follow [QNAP's integrity-check documentation](https://www.qnap.com/en/how-to/tutorial/article/data-integrity-check-in-hbs-3).

## October 25 email delivery and B2 sample restore

After the firmware and HBS updates, Notification Center reported expired Gmail
authorization. The user reauthorized the existing account, and the saved sender
and recipients were retained. The native QNAP test succeeded at 16:28 Eastern;
an independent Gmail inbox check found the matching NAS test message received
at 16:28:52. The existing HBS email rule remained enabled. No new credential,
recipient or alert rule was created, and no artificial backup failure was induced.

A one-time HBS restore used the existing B2 account and the October 25 02:00:17
backup version. It selected only `Usenet/Backups/automatic/forgejo`, restoring
seven files (17,239,788 bytes) into the new private directory
`/share/Usenet/b2-restore-test-20261025`, outside the backed-up source folders.
HBS reported Success; every restored regular file matched its original
byte-for-byte, and no symlinks were restored. The original files and backup job
were retained. The test restore job has no recurring schedule and uses Skip
files on destination conflicts; its small output remains available for review.

This proves a small B2 restore of encrypted configuration archives and receipts.
It does not prove recovery of the private originals, a full Time Machine backup,
or a replacement NAS. Earlier independent archive-decryption checks remain
separate evidence; this test compared the restored ciphertext and receipts.

## October 27 backup duration and deduplication trial

Read-only HBS history inspection showed that the long runs were transferring
hundreds of gigabytes, despite relatively little new user content. October 25
transferred 344.83 decimal GB in 9 hours 38 minutes; October 26 transferred
399.94 GB in 12 hours 12 minutes. October 27 also succeeded, transferring
355.60 GB in 11 hours 19 minutes. The daily scan was not the main delay:
October 27 finished scanning at 02:17, then spent most of the run uploading.
At the configured 10 MiB/s cap, 350 decimal GB alone takes at least 9.3 hours.

The Time Machine sparsebundle uses 266,055,680-byte bands. With QuDedup disabled,
a change within a band makes the whole band eligible for upload. HBS remains
incremental at the file level; a small logical change can therefore produce a
large transfer. Historical per-version file records may include reused entries,
so their summed size is not a reliable measure of bytes uploaded by that run.
Use the job history transfer counters for that comparison.

The integrity schedules above were saved through HBS and independently verified
without interrupting the active backup. The daily schedule, five source roots,
30-version retention, snapshots and upload cap were preserved. HBS skips a
scheduled integrity check if the backup is still running, so the later times
reduce the observed overlap but do not guarantee that every check will run.

HBS disables the QuDedup control when editing this existing job. Enabling it
requires a new backup job and separate initial upload; the current destination
and recovery history must remain available during any migration. A separate
synthetic trial uses `Usenet/b2-dedup-test-20261027/source`, with QuDedup enabled,
compression disabled, snapshots enabled and the same 10 MiB/s upload cap. It
targets its own B2 prefix and contains no user files. The fixture is one random
266,055,680-byte file, matching a Time Machine band's size. This can test block
reuse and restore correctness, but cannot establish actual Time Machine savings
or full Time Machine recovery.

Both synthetic uploads succeeded. The initial run transferred 268,402,228 bytes
in 101 seconds. Replacing exactly 1 MiB at offset 128 MiB, without changing the
file size, produced a second upload of 2,324,562 bytes in 47 seconds (about 99.1%
less transferred data). HBS displays these as 2.22 MB and 255.97 MB, using binary
units. The trial was returned to manual scheduling after its initial run, which
followed the production job.

The modified version was restored through HBS into
`Usenet/b2-dedup-test-20261027/restore`, outside the source folder. HBS reported
Success after 17 seconds, with one file restored and none skipped. An independent
read of the complete 266,055,680-byte restored file matched the modified source's
SHA-256 exactly. Both trial jobs have no recurring schedule, and their small
synthetic source, cloud backup and restore output remain available for review.
At the end of the synthetic trial, the production job still had QuDedup disabled
and no replacement seed had started. Actual Time Machine transfer savings require
comparison of real band changes before treating this synthetic result as a
production forecast.

## October 27 production QuDedup seed

After the user authorized a separate production job and initial upload, HBS job
`B2 QuDedup 20261027` was created through Safari. It uses the existing B2 account
and `RynapQNAP` bucket with a separate `/B2 QuDedup 20261027.qdff` destination.
Read-only configuration inspection confirmed the same five source roots as
`Backup 1`, QuDedup enabled, compression disabled, snapshots enabled, ACL and
extended attributes preserved, 30-version retention, and an initial 10 MiB/s
upload cap at all times on all seven days. Filters and source deletion remain disabled;
the failure notification trigger is enabled. Existing encryption settings and
bucket policy were preserved.

The initial run started at **16:00:26 Eastern on October 27**. Both HBS's interface
and its run history showed it running. The source-selection estimate was 4.19 TiB;
this is a multi-day seed, with no reliable completion estimate at launch. This
checkpoint establishes creation and startup only, not a completed backup or a
verified production restore.

The user then authorized a temporary **200 Mbps** cap for the seed, returning to
the original cap afterward. HBS accepts whole-number binary MB/s values, so the
closest supported setting is **24 MiB/s**: 25,165,824 bytes/s, or 201.33 Mbps.
This was saved through Safari and independently read back. HBS explicitly says
changes to a running job apply to its next run, so only the new seed was stopped
and restarted at **16:21:38 Eastern** with the higher cap. The stopped attempt
is not a completed backup. The replacement run was verified as running; measured
throughput and completion time remain dependent on NAS processing and B2, not
just the bandwidth limit. Sending all 4.19 TiB at this cap would take about
51 hours before other overhead or deduplication savings.

### October 28 migration handoff and remaining verification

The Time Machine repair task intentionally stopped the replacement seed at
**21:38 Eastern on October 27** after finding APFS image corruption. The user's
subsequent choice returned its saved cap to **10 MiB/s** (HBS displays `10 MB/s`,
independently verified as 10,485,760 bytes/s), always on, all seven days. This
supersedes the temporary 24 MiB/s setting; do not restore the higher cap. The
stopped run transferred about 136.87 decimal GB and is not a completed production
backup. No production restore from this replacement has passed.

For the authorized private-library move, the migration task stopped the active
legacy `Backup 1` run at **10:42 Eastern on October 28** and removed only the old
private-library source from both jobs through HBS. Independent read-only
inspection confirmed the four remaining roots listed above. Neither the obsolete
private root nor `PrivatePlexLibrary` is currently selected. The move is recorded
in the [NAS migration plan](../../docs/plan-nas-storage-and-access.md#fromdrobo-data-migration).
Both jobs retain their destinations, 30-version retention, snapshots, ACL/xattrs,
other sources and 10 MiB/s caps. Existing cloud history and test evidence remain.

At handoff both jobs are stopped. The replacement and its integrity checks remain
manual; `Backup 1` still has daily 02:00 backups, Monday 16:00 quick checks and
first-of-month 17:00 full checks enabled. Stopping its run did not disable its
next scheduled start. Coordinate that schedule and any resumption with the
migration and Time Machine recovery owners. The Codex follow-up is paused and
must not undo approved exclusions or restart the replacement without a safe
handoff. Future UI actions require an unlocked Mac and a signed-in QNAP session.

Time Machine's later Verify Backups result passed according to the repair task,
but independent restore and post-verification error checks remain open. Successful
backup jobs or an uploaded copy of the previously corrupt image do not establish
usable laptop recovery or release old B2 history for deletion.

After a coordinated handoff and a successful complete production seed with no
unresolved errors, run HBS quick integrity verification and restore the small
configuration sample from that completed version into a fresh
`Usenet/b2-qudedup-restore-*` directory outside source roots, skipping conflicts.
Compare complete SHA-256 hashes and sizes with the fixed reference in ignored
`build/hbs-qudedup-20261027/restore-reference.json`: one 5.76 MB encrypted settings
archive and its receipt. Preserve this reference across follow-ups. The earlier
synthetic test does not satisfy this production restore requirement.

The configuration sample alone cannot qualify the old mixed repository for
retirement. First protect the private library from its new canonical root and
independently restore a bounded sample of usable data and applicable metadata.
Account for every other still-required source, including the repair task's
accepted Time Machine recovery strategy and useful retained history. Apply the
[complete retirement condition](../../docs/plan-nas-data-protection.md#private-library-migration-exception).
Only after all relevant gates and ownership handoffs pass, transfer daily 02:00
protection and the Monday 16:00 / first-of-month 17:00 integrity schedules to the
new job, verify them, and disable the old recurring schedule.

The user authorized conditional retirement only of `Backup 1` and its precisely
superseded `/Backup 1.qdff` history. Permanent deletion through computer use still
requires action-time confirmation with concrete verification and the exact target
ready. Preserve unrelated jobs, prefixes, sources and test evidence. Verify whether
B2 retained object versions remain before claiming storage was reclaimed. On
failure retain all existing backups and coordinate diagnosis. Later production
incremental runs must establish actual Time Machine transfer savings.

## Repository-owned encrypted settings archives

**October 8: recurring off-host NAS settings coverage is deployed and verified.**
Final `cloud-20261008T192037Z.tar.age` also passed off-host readback and
independent restore: 785 files, five databases, 44 journals and both nested
Filex bundles, including the corrected operator login escrow.
The user selected settings only. The scheduled NAS job now uploads encrypted
QNAP and Plex settings to a separate Storage Box subaccount confined to
`catalog/.backups/nas-settings`. Every upload is downloaded again and its
SHA-256 compared before success is recorded. Independent restores passed for
66 QNAP settings files and three Plex files; both Plex database snapshots opened.
NAS originals, artwork and installation binaries are excluded from these
settings archives. The separate B2 scope above does include selected originals.
Media and staging are excluded from this settings-only scope.


Enabled September 11, 2026. Schedules run on the cloud host and NAS; deleting or
turning off the Mac does not stop them. NAS-loss coverage is settings only.
These backups exclude media, unfinished download payloads, Plex artwork, and the
Plex installation binaries. Media remains on the canonical Storage Box.

| Host | Schedule | Protected state | Destination |
| --- | --- | --- | --- |
| Cloud | systemd `usenet-backup.timer`, hourly retry; skip when a success is less than 23 hours old | SAB, Prowlarr, Radarr, Sonarr, catalog state, deployment scripts/configuration | Encrypted locally, copied to `catalog/.backups/cloud` on the existing Storage Box, independently downloaded and compared |
| NAS | `usenet-backups` container cron at minute 7 each hour; same daily freshness gate | QNAP Usenet configuration, Plex preferences/databases, and native QTS/HBS settings | `/share/Usenet/Backups/automatic` plus independently verified encrypted off-host copies |
| NAS | Part of the NAS job | Already encrypted cloud archives | Pulled with the existing server-enforced read-only account into `automatic/cloud` and checked against SHA-256 receipts |

The recurring NAS schedule uploads Plex and QNAP configuration to the confined
backup account. The canonical media reader remains server-enforced read-only. Encryption
uses the existing public `qnap-admin` or `cloud-admin` recipients. Their private
keys are already recoverable from the original SOPS vault. No private recovery
master or administrator key is installed on either host for the schedule.

The October 17 native-settings extension is deployed and adds a
`nas-system` encrypted archive. It includes the newest QTS automatic settings
backup from `/.@backup_config` on the system volume, plus online SQLite snapshots
of HBS's `cc3_config.db` and `hbs.db`. The QTS snapshot must be nonempty, no more
than 64 MiB and less than 14 days old; missing, stale, linked or oversized inputs
fail capture. HBS databases are checked for integrity before encryption. Native
settings source directories are mounted read-only, and plaintext exists only in
memory or the backup container's temporary filesystem. QTS settings reflect the
native weekly snapshot's timestamp, while HBS configuration is captured daily.
This does not establish replacement-NAS boot or cross-device HBS credential
recovery. Keep the existing administrator decryption identity recoverable.

The first three-scope capture completed at 14:50:19 UTC on October 17. All three
encrypted settings archives passed off-host upload/readback, and the new native
archive was separately retrieved and decrypted on the workstation. Its three
payloads matched their manifest hashes and both HBS SQLite snapshots passed
integrity checks. The included native QTS snapshot dates from October 14.
The sanitized verification receipt is
`usenet-infra/recovery/drills/nas-system-config-20261017.json` in the checkout.

Cloud backups require an idle or fully paused SAB queue and no post-processing.
They never resume or delete queued jobs to satisfy that condition. An active
queue delays capture until the next hourly attempt. Database snapshots use
SQLite's online backup API, with source consistency checks. Plex captures only
`Preferences.xml`, `com.plexapp.plugins.library.db` and its blobs database, without
restarting Plex. Artwork can be regenerated; this is not a full Plex package copy.

NAS/local retention keeps at least seven generations and removes only this
scheduler's checksum-matching archives older than 90 days. Original master
snapshots are never pruned. Storage Box cloud and NAS settings ciphertext is currently retained
indefinitely; monitor its small daily growth. NAS snapshot capture retries short catalog refresh conflicts for up to one minute
without interrupting transfers; longer activity defers until the next hour.
The NAS status health check fails
on a failed run or when its last success is older than 36 hours. Status receipts
are on disk; no external notification service has been configured.

The first cloud, QNAP and Plex archives were retrieved from the NAS and decrypted
using administrator identities restored in the separate clean-clone drill.
Every payload matched its manifest; cloud/QNAP validators passed, and both Plex
SQLite snapshots opened successfully. This does not claim a full Plex server
startup restore or Apple TV/Roku playback test.

Deploy with `just configure-scheduled-backups` inside `usenet-infra`. The two
playbooks are `ansible/scheduled-backups.yml` and `ansible/qnap-backups.yml`.
Private NAS inventory retains:

```yaml
qnap_data_root: /share/FromDrobo
qnap_catalog_cache_dir: /share/FromDrobo/Movies
qnap_backup_root: /share/Usenet/Backups/automatic
qnap_plex_root: /share/CACHEDEV1_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server
```

After recovery, restore these current overrides before deploying older inventory.
Original SOPS-bound inventory and original recovery receipts remain immutable.

## Read-only follow-up

The [October 27 backup repair](backup-repair-2026-10-27.md) records the cloud
SQLite read-only consistency fix, approved Forgejo capture/schedule repair, fresh
off-host restores and scoped rollbacks. Subsequent unattended captures still need
observation. Neither repair changes the ongoing HBS seed or storage-readiness gates.

Use the committed [verified archive receipt](../recovery/drills/scheduled-backups-20260911.json)
as the initial evidence, then inspect current freshness. On the cloud, the status
receipt is `/srv/usenet/backups/scheduled/cloud-status.json`; inspect the timer
with the repository's dedicated connection wrapper:

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra --command ./scripts/cloud-command systemctl status usenet-backup.timer --no-pager
```

On the NAS, inspect `usenet-backups` container health and
`/share/Usenet/Backups/automatic/nas-status.json` using the dedicated NAS identity
and pinned host from the private inputs. The container's existing healthcheck
runs `scheduled-backup.py nas --check`, which emits only health/freshness fields.
Do not dump private environments or Plex preferences to inspect status. Scheduled
retries are automatic; a failed/freshness check is a reason to diagnose the
recorded run, not to resume queued downloads or interrupt a transfer.

The deployed backup helper includes `state/native-items` ownership and integrity
receipts. Independent verification of `qnap-20260913T041100Z.tar.age` passed with
scope `qnap-config`, 56 files and no media. The 1,357-byte native receipt matched
SHA-256 `50f8cd3e5fb3a5b4c444770fe6ee9845e900e534ab62409e53f5677da064aa61`.
See the [capture and archive verification receipt](../recovery/drills/native-receipt-backup-20260913.json).
This closes capture of the new receipt; it does not prove restoration onto a
replacement destination or whole-NAS recovery. Original bound snapshots remain
immutable, and ordinary freshness checks still apply.


## Confined NAS backup account recovery

Forgejo uses the same existing confined NAS backup account with a separate
`archives/forgejo/` directory and its own QNAP cron entry. It captures a stopped
Forgejo instance, encrypts repositories/database/configuration with the existing
NAS recipient, restarts Forgejo before upload, and requires off-host readback.
It does not change the three-scope NAS/Plex settings health contract above.
See the [Git-host runbook](../../git-host/README.md) for schedule, retention,
freshness checks, dated validation and restore limits.

The separate `terraform/nas-backup` root manages only the backup subaccount,
with `prevent_destroy`; never use the canonical storage root to recreate it.
Its local state and private inputs are ignored. Existing account ID 331416 is
recoverable by importing it into this root if local state is lost; inspect the
provider account first, rather than creating a duplicate. The account is
`u666991-sub2` at `u666991-sub2.your-storagebox.de`, SSH port 23.

The scheduler reads `/source/usenet/config/backup/offhost/rclone.conf`, dedicated
`id_ed25519` and pinned `known_hosts` from its read-only source mount. These
three mode-0600 files are included in the encrypted QNAP settings archive.
The local bootstrap copies live under ignored `secrets/nas-backup`. Recovery
requires the existing administrator decryption identity, then those restored
connection files; no administrator private key is installed on the NAS.

Preserve `qnap_backup_offhost_required: true` in private inventory and redeploy
only `ansible/qnap-backups.yml` when needed. It sets `NAS_OFFHOST_REQUIRED=true`;
missing connection settings or a failed upload/readback makes the job fail.
The updated freshness check requires all three distinct settings scopes to have
remotely verified archives; an older two-archive receipt cannot establish health
after the extension is deployed.
The backup account can list only its confined backup directory, and a parent
path probe to the canonical library was refused. It cannot replace the separate
read-only media credential. Remote retention is currently indefinite; local
90-day/minimum-seven retention remains unchanged. This is recoverable settings
coverage, not a tested replacement NAS boot or protection of private originals.

## Household wiki and DNS configuration

The NAS configuration inventory also includes `wiki/.env`, `wiki/.env.previous`,
versioned wiki runtime definitions, and `dns/config`, `dns/runtime`, and private
`dns/backups`. Generated wiki site files and DNS query/statistics data are excluded.
Rebuild wiki content from the repository after restoring its runtime configuration.
DNS administration credentials remain inside the encrypted private archive.
See [wiki recovery](../../docs/operations/wiki.md) and
[DNS recovery](../../docs/operations/home-dns.md) for numeric-address access and
DHCP rollback order. The primary policy snapshot is included here; full primary state requires a Home Assistant backup explicitly including `a0d7b954_adguard`. The repository seven-add-on partial backup does not include that community add-on.
