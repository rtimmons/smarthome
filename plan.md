# Usenet status

The approved operational plan completed October 8, 2026. The current workflow
and commands are in the [README](usenet-infra/README.md); operating constraints
are in the [agent guide](usenet-infra/AGENTS.md). Use those current documents
instead of replaying the branch's historical development sequence.

## Completed and verified

The [October closure receipt](usenet-infra/recovery/drills/closure-20261008.json)
and [validation summary](usenet-infra/docs/validation.md) record native movie/TV
imports and cleanup, selective NAS copies, user-confirmed playback/privacy,
Seerr/Filex browser access, recurring settings backups and isolated replacement
cloud startup. The three old held requests were deliberately discarded; preserve
all 44 journals and their disposition/integrity evidence.

## Remaining work and explicit deferrals

No operational acceptance work remains from that plan. NAS originals, artwork,
replacement NAS/Plex boot, arbitrary archive expansion and a full codec matrix
are outside its accepted scope. Configuration recovery excludes media. No new
purchase, media request or production restoration follows from plan completion.

## Cold session start

Read the agent guide and current component runbook, inspect Git status, and
preserve unrelated edits, ignored inputs and `msg`. Before live changes, inspect
health and active work with the existing wrappers. Do not restart services or
enqueue downloads merely for an audit.

## Ongoing maintenance

The Usenet workflow is maintained on `master`. Retired workers,
one-time migrations, redundant setup paths and historical runbook narratives
are removed; original encrypted snapshots, recovery receipts and journals remain
unchanged. Recovery reconstructs the current layout directly.

Validate changes, report the two documented historical key findings separately,
and protect local work. Root instructions require permission before taking a Git
lock. Publishing changes, deleting branches and removing checkouts require their
own authorization.
