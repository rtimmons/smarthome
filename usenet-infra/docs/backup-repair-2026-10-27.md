# Forgejo and cloud backup diagnosis — October 27, 2026

This follows the [application inventory](../../docs/nas-service-inventory-2026-10-27.md).
The cloud helper was repaired without stopping applications. The user approved
a Forgejo-only capture interruption and restoration of its recurring schedule.
No HBS job, seed, cap, history, account, share, application path or storage gate
was changed.

## Cloud repair

The hourly `usenet-backup.service` ran but had no success after October 16.
The deployed helper matched repository source. Inventory, SAB admission and a
disposable settings snapshot passed as the actual `usenet` identity, 1991:1991.
All nine cloud containers were running; six had healthy health checks. Output
permissions, encryption recipient and the timer were correct.

The same snapshot failed under the unit's `ProtectSystem=strict` restriction:
`A settings database changed during capture; retry during a quiet interval.`
The rejected database belonged to retained, stopped Cleanuparr replay evidence,
not a running production application. A bounded reproduction under the same
read-only restriction returned SQLite `data_version` values **2, 3, 4, 6, 8**
without any change to the main database, WAL or SHM bytes/metadata. Two independent
SQLite online snapshots were identical and passed integrity checks. The source
was 471,040 bytes, with an empty WAL and a 32,768-byte SHM index. This establishes
a false change signal in this environment; it does not establish that other
databases are idle. SQLite's [WAL documentation](https://www.sqlite.org/wal.html)
distinguishes the authoritative WAL from its shared-memory reader index.

`config-backup.py` now compares main-database and WAL identity, size, modification
and change times, and SHA-256 before/after capture. Each fingerprint rejects
changes during hashing and oversized or nonordinary inputs. SQLite still creates
the consistent online snapshot and checks its integrity. SHM is excluded from
the source fingerprint because it is a reader index. Concurrent main/WAL commits,
file replacement, source/config changes, unsafe links, active SAB jobs and
post-processing remain rejection conditions. No evidence was excluded or deleted;
no source write permission was granted and no WAL was discarded.

The candidate passed capture and encryption in a temporary unit with the
production restrictions before installation. A single Ansible copy replaced
`/srv/usenet/libexec/config-backup.py`, preserving root:usenet ownership and mode
0550. The old helper remains beside it as
`config-backup.py.564628.2026-10-27@21:08:51~`. Only this deployed program was
replaced on the cloud host; the existing timer, service definition, credentials and applications remain.
The combined cloud/NAS schedule-deployment recipe was not run.

Starting the existing backup unit produced `cloud-20261027T210901Z.tar.age`:
**1,049 files, 163,501,236 encrypted bytes**, success at **17:09:11 Eastern**.
Hetzner upload and independent ciphertext readback passed. Before starting, all
47 existing receipts were checked: the oldest was about 46 days old and **none**
was eligible for retention deletion. The fresh outer archive again carries the
Filex recovery bundle; its inner capture remains a separate recovery stream.

A separate download directly from Hetzner matched SHA-256
`3453ddeadd9292c2ded623e45a3d80c0ae806843bf9a2c1ae7ad28dd77bacd8c`.
Local decryption with the existing dedicated cloud recovery key verified every
one of the **1,049 files and 17 SQLite databases**. This closes archive recovery
for this capture, not replacement-host startup or the next unattended cycle.

Rollback is a single-file Ansible copy from the retained prior helper, preserving
owner/group/mode; inspect current content first and save the repaired helper too.
It needs no application stop and does not alter archives, but reinstates the
known false rejection. The next hourly timer should skip a success younger than
23 hours. A later unattended capture, after that threshold, remains to be observed.

## Forgejo diagnosis and approved repair

At diagnosis Forgejo was running and healthy, but neither `/etc/config/crontab`
nor active `/tmp/cron/crontabs/admin` contained its backup entry. Both files had
last been modified October 25 and differed from each other; the actor that removed the entry is not
established. The previous installer deliberately refused this mismatch. Do not
copy either complete crontab over the other or restore the old whole-file snapshot.
The backup scripts existed; the log was empty, with no lock or resume marker.

At diagnosis the latest success was October 24 at 19:28:35 Eastern, beyond
the 36-hour health limit. A fresh independent download of that archive from
Hetzner decrypted
with the existing dedicated NAS identity: **102 entries, SQLite integrity and one
Git repository's object verification passed**. This does not cover newer pushes
or establish replacement-server startup. Private restore evidence is under
`build/git-host/restore-1793135136337167000`.

After explicit approval, an application-only metadata preflight found 145 entries
and 7,010,870 bytes with more than 1.2 TB free in the archive filesystem. Forgejo
and its archive uploader were healthy; no capture/resume/pending marker existed.
Only Forgejo stopped. It restarted before upload and is healthy again.

The fresh `forgejo-20261027T211714Z.tar.age` contains **151 entries and 7,323,588
bytes**. Success at **17:19:24 Eastern** includes verified Hetzner readback.
An independent off-host download/decrypt passed all hashes, SQLite integrity and
**both Git repositories' object verification**. Private evidence remains in
`build/git-host/restore-1793136005983773000`. This covers the current complete
application recovery unit; replacement-server startup remains untested.

The installer now saves active and persistent cron separately in private
`cron-checkpoint-*` directories, preserves each file's unrelated entries and
refuses a detected concurrent edit before writing. The approved minute-23 hourly
retry, with its unchanged 23-hour freshness gate, was restored. The first live
checkpoint is `cron-checkpoint-_1j53k7h`. Its minute probe executed at 17:22:01
Eastern; both tables contained one job and one probe, and all unrelated entries
matched their own saved table. Forgejo's HTTP database/cache health passed and
both lock/resume markers were absent. The old whole-file snapshot is retained.
Rollback uses `just git-host backup-unschedule`: remove only Forgejo's owned
job/probe from both current tables, preserving later unrelated edits and archives.
No production rollback was needed; its preservation behavior passed synthetic tests.
The actor that removed the original entry remains unknown, and survival across
later QTS/package changes and a subsequent unattended capture remain unqualified.

## Evidence and checks

Private commands, metadata, outputs, encrypted download and validation logs belong
in ignored `build/backup-diagnosis-20261027/`; no credentials, actual request/media
identifiers or raw application databases belong in Git.

All 27 focused backup tests passed, including read-only WAL evidence, committed
WAL recovery, concurrent main/WAL commits, replacement and unsafe-link rejection.
Infrastructure unit tests (583) and syntax checks passed. The full infrastructure
command fails at the history scanner: the two documented historical RSA keys
plus historical `usenet-infra/backups` and `usenet-infra/secrets` path findings.
The narrower current-source/index scan passed. No scanner exception or history
rewrite was introduced. Full root `just test` passed on retry. Its first run had
an unrelated printer
preview latency failure (121.7 ms against 100 ms); no printer source or test was
changed. The focused Forgejo suite passed all nine tests, including distinct cron
tables, removal preserving a later unrelated entry, and refusal of a concurrent
edit before writes. Wiki checks passed.

## Final checkpoint

At 17:24:36 Eastern, both cron tables contained **one Forgejo job and zero
probes**. Each file's unrelated entries matched its own saved copy in
`cron-checkpoint-mnr5m9qe`. The minute probe had executed before removal.
Forgejo's container start time remained 17:17:46, database/cache HTTP health
passed, no backup/resume marker remained, and the fresh archive receipt was
unchanged. Continuous HTTP downtime was not measured.

The cloud backup unit completed successfully with exit status zero and its
existing hourly timer remained active. No cloud application was stopped.
The next useful recovery check is a later unattended capture for each stream;
do not infer this from the minute probe or from a successful manual run.
The separate HBS seed, disk-2/power/snapshot gates, service-account separation
and wiki pilot boundaries are unchanged. No production data migration occurred.

## Future actions: unattended recovery qualification

**Open; recorded October 27.** The next recovery-maintenance session owns these
checks. Suggested review: **October 28 after 17:30 America/New_York**, after both
normal schedules have had an eligible opportunity. Re-read the actual timestamps
and timers first: busy applications, host downtime or a newer manual capture can
defer eligibility.

- [ ] **Cloud:** observe a new capture from the existing hourly timer, newer than
  the October 27 17:09:11 success. Confirm successful unit completion, a still-active
  timer, a fresh source timestamp and verified Hetzner ciphertext readback.
  Independently retrieve/decrypt that new archive and verify its files/databases.
  Record NAS mirror freshness separately; Hetzner success does not prove the NAS
  replica or B2 delivery has caught up.
- [ ] **Forgejo:** observe a new capture from the minute-23 cron job, newer than
  the October 27 17:19:24 success. Confirm one owned entry in each cron table,
  no probe, healthy application restart and no stale capture/resume markers.
  Independently verify the new off-host archive, SQLite and Git objects.
- [ ] **Cron persistence:** after the next separately approved QTS/package change
  or reboot, recheck both tables and subsequent execution. Do not trigger such
  maintenance just to test persistence; the original disappearance remains unexplained.

Both jobs skip a success younger than 23 hours. Do not force another capture,
change a timer or pause/resume work to manufacture unattended-run evidence.
Close each action only with its observed run/receipt and sanitized result in the
service ledger; keep exact logs and restore evidence private. Preserve old
archives and the separate HBS seed/follow-up. These actions do not block the
[offline wiki preparation](../../docs/nas-service-inventory-2026-10-27.md#first-pilot-wiki-preparation-then-separate-identity-and-path-checkpoints),
and their completion does not clear the disk, power or snapshot gates.
