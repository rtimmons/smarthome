# NAS application and recovery inventory — October 27, 2026

First bounded checkpoint for the [storage plan](plan-nas-storage-and-access.md),
[access model](plan-nas-access-model.md) and [protection policy](plan-nas-data-protection.md).
This is an inventory and pilot specification, **not a production migration**.
No account, ACL, share, schedule, application path or running service was changed
by the initial inventory. The subsequent backup repair is recorded below.
Household collections, share contents and media payloads were not traversed.

## Evidence and decision ledger

**O** means observed through dedicated SSH on October 27, approximately
16:50–17:00 Eastern. **C** means current checked-out configuration/runbook,
including explicitly identified concurrent work. **H** means historical acceptance.
**P** means proposed. Mount flags and UID observations are not effective-access
tests. No new SMB, local-user denial, restore or playback test ran here.

Private metadata, exact SIDs, release pointers and probe scripts are retained in
ignored `build/nas-service-inventory-20261027/`. No environments, credentials,
private repository listings, media titles or payload listings belong in this report.
Credential references below identify files/purposes, never secret values.

| Checkpoint | Result / limit | Next smallest useful step |
| --- | --- | --- |
| Storage readiness | **O:** RAID has zero degraded members, idle sync, zero current mismatches; UPS remains disabled. Snapshot schedule bitmap is zero. The September 2024 snapshot remains; three additional hidden app-owned snapshots correspond to today's backup window, not qualified retained rollback. **User:** no later disk-2 repair or power qualification. | Keep production moves and stress tests blocked. Preserve the October 25 disk history; diagnosis/recovery/power review is separate work. |
| NAS inventory | **O:** 12 containers: 11 running, retired NAS DC stopped. DNS discovery is unhealthy; nine other containers with health checks are healthy; iperf has none. Target `wiki`, `forgejo`, `forgejo-backups` and `infrastructure-backups` shares have no configured path. | Use service-specific checkpoints below; do not interpret proposed shares as deployed. |
| Forgejo recovery | **O:** latest success October 24 19:28:35; receipt says `ok` but exceeds the 36-hour health limit. Persistent cron has zero `home-git-backup` markers. Active admin spool is unreadable to the deployment login; no backup lock, resume marker or pending upload exists. | Read the active spool through the established bounded privileged mechanism and reconcile it with persistent cron. Then propose restoring the one missing entry and a brief Forgejo capture window. No cron write or manual capture was performed. |
| Cloud recovery | **O:** hourly timer exists; latest result failed with `BackupError`; last success October 16 16:05:45. Filex local capture is fresh (October 26 22:00:27), with a successful timer result, but its outer offsite stream is stale. | Diagnose the fixed backup-admission/source validation failure read-only; distinguish active queue/postprocessing from invalid inputs. Do not pause/resume/delete jobs or relax gates to obtain a green receipt. |
| DNS discovery | **O:** scanner health and three recent log records say `Timeout`; resolver remains healthy. No successful domain-trust result was obtained by this probe. | Diagnose the timed-out dependency separately; preserve learned state and pending journal. This rules DNS out as an initial migration pilot. |
| Concurrent HBS work | **C:** working backup runbook records a production QuDedup seed restarted October 27 16:21:38 at 24 MiB/s, alongside the original 10 MiB/s daily job. | Leave both jobs, history, temporary cap and their existing follow-up owner alone. This session did not re-read HBS job state or manage its UI. |
| HA recovery and consumers | **O:** FromDrobo CIFS mount is active, media usage, writable; no default backup mount. Latest protected archive is October 27 05:16:06, local only, Core/database, all 27 installed apps and `/ssl`; `/share` absent. | Preserve the active HA Plex consumer. Qualify native off-host HA recovery separately from NAS settings. |
| Validation | Full root `just test` passed; current-source/index secret scan passed; no new implementation tests were added for documentation. | Review only this checkpoint's four files and preserve unrelated work/index/`msg`. |
| First pilot | **O/C:** wiki has two read-only input binds, zero effective capabilities at its init process, no persistent writable mount, no DB and a retained-release rollback helper. | Recommend the wiki preparation/rehearsal below. No production identity or path cutover yet. |

### Follow-up: backup diagnosis and repair

The [October 27 repair checkpoint](../usenet-infra/docs/backup-repair-2026-10-27.md)
supersedes the two initial backup rows above. Cloud failure was a false SQLite
change signal under the backup unit's read-only restriction, first reproduced on
retained stopped test evidence. The helper now checks main/WAL bytes and metadata;
the evidence remains captured. A single-file deployment and a normal backup run
succeeded at 17:09:11 Eastern, with 1,049 files and verified Hetzner readback.
An independent off-host download/decrypt verified all files and 17 SQLite databases.
No application stopped and no archive was eligible for pruning.

Both Forgejo cron files lacked its entry and differed from each other. After the
user approved capture and recurring stops, a fresh complete archive succeeded at
17:19:24 Eastern; independent restore verified 151 entries, SQLite and both Git
repositories. Forgejo restarted and is healthy. The schedule repair preserves
the two cron files independently; all unrelated entries were verified unchanged.
The minute probe executed and was removed; both tables retain exactly one job.
The HBS seed, storage-readiness gates and wiki pilot recommendation are unchanged.
**Open future action:** complete the [unattended recovery checklist](../usenet-infra/docs/backup-repair-2026-10-27.md#future-actions-unattended-recovery-qualification)
with new scheduled captures and post-maintenance cron evidence. The next recovery
session should review after the eligible October 28 runs, initially after 17:30
Eastern. Offline wiki preparation can proceed now; these successes do not clear
the storage gates.

The generic `just usenet qnap-recon` did not complete successfully after the
sandbox hostname failure. A narrower probe using its same connection helper
completed; this report relies on those selected fields, not a successful generic
health result. HA hostname resolution likewise required the permitted retry
outside the sandbox with the same dedicated key and hostname.

### Wiki preparation and recovery checkpoint

Preparation commit `1a29627` adds wiki-only runtime inputs with the existing
UID/GID defaults. Focused tests and a localhost rendering check with the pinned
Ansible engine passed for default, UID-only, GID-only and combined overrides.
The infrastructure suite passed 585 tests (12 skipped), plus syntax checks;
its full-history scanner still reports the known two RSA keys and historical
private paths. Current-source scanning passed. Root tests/container checks passed
on retry after the unrelated printer preview measured 102.9 ms against 100 ms.
The later documentation-only full run hit the same printer test at 103.3 ms
(224 printer tests passed); no printer code or threshold was changed. Wiki
checks and the current-source scan passed for the documentation checkpoint.

A fresh bounded NAS read found the wiki healthy at 1004:100, zero effective
capabilities, two read-only binds and no deployment lock. Current and retained
release pointers were preserved off NAS with both static releases: 216 files,
212 verified manifest entries, 3,022,400 bytes encrypted. Pointers matched before
and after capture; independent decryption and checks passed. This is a direct
runtime recovery supplement; recurring settings capture still omits site HTML.

Both source repositories were separately bundled and restored with current
tracked working-tree overlays. Bundle verification, Git object checks and an
isolated wiki build passed (102 static files); the build reused only the
controller's pinned Node tooling, with no live credentials or NAS access. The
5,903,830-byte encrypted source checkpoint also passed decryption. Private
receipts, archives and exact source revisions are under ignored
`build/wiki-identity-20261027/`. These controller copies are not a new B2 delivery
or proof of replacement-controller bootstrap.

Safari's local-user wizard exposed Public read and Multimedia write defaults,
all application grants, and checked recursive permission propagation. The pending
`svc-wiki` form instead denies all seven existing shares and every listed
application, with recursion unchecked and no administrator membership. QNAP
created the otherwise unused local `wiki-reader` group, GID 1000. Account password
entry/submission remains a human handoff; no service UID has been allocated or
used by this checkpoint. Do not treat the pending form as effective denial.

Next: finish account creation, verify its actual UID/groups and saved grants,
then run the retained synthetic ACL fixture with an explicitly selected runtime
GID. It checks read, write/create/rename/delete, private-file and share-root
traversal behavior plus read/validation of the existing wiki inputs, without a
service restart. Only a passing fixture supports a runtime-only cutover. The
named-share move remains blocked on disk/power/snapshot readiness; this migration
is **open**, not closed. Preserve all releases and the separate HBS seed.

## Common identity and permission contract

The live deployment login is QNAP-local `usenet-deploy`, UID **1004**, primary
GID **100** (`everyone`), supplementary GID **0** (`administrators`). Its home is
`/share/homes/usenet-deploy`. Preserve the home/key, pinned host trust and
`QNAP_SSH_TARGET` / Ansible `ansible_user` references. Target `svc-nas-deploy`
remains deferred until runtimes are separated. No new account exists yet.

Runtime process credentials were read from container init PIDs and, where the
application itself is PID 1, from that application. This is not an exhaustive
audit of every child process. The NAS service containers using 1004:100 have
only group 100 and zero effective capabilities at the inspected process:
wiki, dashboard, Forgejo, DNS resolver, discovery and Filex; the rclone cache
container also has that same mapping. Different service labels do not isolate
shared numeric owners. QNAP's `everyone` GID is not a suitable new private
service group by assumption.

AD `svc-authelia` and `svc-jellyfin` resolve to the existing domain SIDs (private
record; RIDs 1103 and 1112). They remain **lookup identities**, with no proposed
NAS data role. Runtime identities are host-local unless a protocol needs AD.
Existing human accounts, `git-users`, `arr-users` and local recovery accounts
are preserved. Historical encrypted SMB denial tests are documented in
[household identity](operations/household-identity.md); none were repeated here.

For every proposed service share, ordinary Ryan/Michael SMB, guest, legacy
`hass`, LDAP lookup users and unrelated runtimes should be denied direct data
access. Application login does not grant filesystem access. Test denials through
SMB **and** host UID/group/ACL traversal, inherited ACLs, alternate exports and
bind mounts. Root, Docker management and NAS administrators remain explicit
bypass authorities. No isolation claim below applies against those authorities.

## NAS application boundaries

In this table `U` means `/share/Container/usenet`; `B` means
`/share/Usenet/Backups/automatic`. All target shares are **P**. Read-only (R) and
read/write (RW) are proposed role operations unless explicitly marked observed.
Service configuration should be mounted R wherever the application permits it.

| Service and current roots (mounts O; other paths C unless stated) | Actual principal / login / credential reference | Proposed account → roles → access | Writers, deployment and dependencies | Recovery / unresolved / smallest action |
| --- | --- | --- | --- | --- |
| Wiki: `U/wiki/.env`, `.env.previous`, `releases/<release>/{site,runtime}` → `wiki` | QNAP numeric 1004:100; inspected init same IDs/group 100, capabilities zero. No app secret; HTTPS uses outer Ryan MFA, numeric/old LAN routes remain open. Publisher uses dedicated QNAP SSH. | `svc-wiki` → `wiki-reader`: R on publication/Caddyfile; runtime denied writes and all archives. Deployment operator publishes. | Two observed R binds (`site` and Caddyfile); tmpfs only for runtime writes. `qnap_wiki_root`, wiki-specific UID/GID inputs defaulting to shared `qnap_uid/gid`, `wiki/apply.sh`; all supported deployments may publish wiki afterward. DNS, HA HTTPS proxy and source/build inputs are dependencies. | Rebuild conditional; NAS capture includes pointers/runtime but deliberately omits site HTML. Private printer checkout is now a required build input. First pilot below; independently recover both repositories before claiming rebuild coverage. |
| Forgejo: `/share/Container/home-git/{data,config}` → `forgejo` | QNAP numeric 1004:100; init same IDs/group 100/capabilities zero. Existing app user/OIDC link, SSH Git keys and local recovery login; server secrets in `data/custom/conf/app.ini`, key files under data, escrow references in identity runbook. | `svc-forgejo` → `service-state(forgejo)` RW; deny `forgejo-backups`, uploader keys, other apps and household shares. `git-users` permits app access only. | Two RW data/config binds; hard-coded IDs and paths in `git-host/compose.yaml`, `manage.py`, backup helpers and identity integration. Capturer needs stop/start. Printer's private origin is hosted here; publishing the wiki depends on a local printer checkout. | Full recovery unit below. October 27 fresh capture and independent restore passed; unattended capture and isolated application startup remain prerequisites for account/path migration. |
| Jellyfin/Moonfin: `U/jellyfin-trial/{config,web-config.json,cache}` → durable `jellyfin`; cache remains disposable | Actual process UID 0/GID 100, group 100, `DAC_READ_SEARCH`; GPU device exception. AD `svc-jellyfin` lookup is distinct; original Ryan app ID/alias and hidden local recovery admin. Operator reference `usenet-infra/secrets/jellyfin/operator.json`; recovery/lookup files in external identity-private state. | `svc-jellyfin-runtime` → own state RW + `media-readers` R; private media and archives denied. Retain required root/GPU exception until tested replacement. | Config/cache RW, web config and five general-media leaves R; no private root bind. `scripts/jellyfin-trial.py`, Compose, LDAP plugin/CA and Moonfin Seerr linkage. | Pre/post-AD stopped-state exports passed historically; recurring NAS allowlist omits `jellyfin-trial`. Specify a consistent recurring export and GPU/ACL test before migration. |
| Catalog/OliveTin, refresh/copy helpers and rclone cache: `U/{state,scripts,config/catalog,compose/qnap,secrets}` → `media-control` (exact split pending) | Dashboard and cache process 1004:100/group 100/capabilities zero. OAuth owner ACL plus separate local recovery login. `secrets/dashboard-auth.json`, provider-reader key/known-host files; keep API keys private. | `svc-media-copy` → own state RW + `media-copy`: selected general cache RW, canonical reader R; private roots and backup shares denied. | Dashboard binds broad `U/state` RW; refresh and transient catalog jobs share locks/receipts. Media cache/staging pairs must remain same-filesystem. Ansible qnap roles, refresh deployer, private path overrides and native ownership are coupled. | Recurring qnap-config captures enumerated state/config; H recovery checks include native-copy receipts. Inventory shared state subpaths and each writer before splitting; do not rename receipt-owned media. |
| Filex NAS SFTP: `U/filex-sftp/{keys,.env,compose.yaml}` → `filex`; payloads stay `TransferStaging` later | Actual rclone 1004:100/group 100/capabilities zero. App SFTP login `filex-staging`; host key and authorized key are under `filex-sftp/keys`, distinct from NAS SSH. | `svc-filex` → own state + `transfer-users`; only staging RW. Classify interactive versus machine use before renaming the app login to any `svc-filex-transfer`. | Keys R; `/share/FromDrobo/FilexStaging` RW. Cloud Filex is the downstream caller. Fixed paths in NAS Compose and Filex deployer. | NAS settings capture includes keys/config, not payloads. H independent settings restores passed. Confirm client ownership and unfinished transfers; identity and payload moves are separate. |
| NAS AdGuard resolver: `U/dns/{config,data,runtime}` → `dns/resolver` | Actual 1004:100/group 100/capabilities zero. Loopback administration password in private DNS config/controller state. | `svc-dns` → resolver config/state only; required config currently writable by AdGuard. No discovery-state/backup credential grant. | Resolver config/data RW; port 53 is gateway/household infrastructure. Policy deployer and automatic scanner both affect configuration through controlled APIs. | qnap-config includes config/runtime/private backup snapshots, excludes query/statistics data. Defer migration; healthy resolver must remain available while discovery timeout is investigated. |
| DNS discovery: `U/dns/{config/automatic,runtime/automatic,backups/automatic-state}` → `dns/discovery` | Actual Python 1004:100/group 100/capabilities zero, host network. Existing HA discovery token and NAS admin credential; token has provisioning-user authority, not DNS-only scope. | `svc-discovery` → `dns-discovery` RW journal + enumerated `dns-config-reader` R; no broad resolver-directory RW. API credentials remain separately powerful. | Config R, state RW; approximately minute scans; primary HA resolver, NAS resolver, gateway and mDNS dependencies. Preserve learned policy and recovery journal. | In qnap-config scope. Current `Timeout` means no migration; inspect dependency timeouts without clearing state. |
| Remote reader: `U/secrets/storagebox`, remote Compose → `remote-reader`; mount/cache remain distinct | Actual rclone UID/GID 0:0, container supplementary groups and `SYS_ADMIN`/`DAC_OVERRIDE`; dedicated provider-issued read-only login/key. | `svc-remote-reader` label; retain justified mount-helper exception. `remote-reader` backend R + `playback-cache-writer` RW. No writable provider credential. | Credentials R; `/share/FromDrobo/Remote` shared mount propagation and `.remote-cache` RW. NAS/HA Plex, Jellyfin, copy and archive readers depend on provider access. | Key/known-host and `compose/qnap/remote.compose.yaml` are within qnap-config capture. No cache/media backup. Verify the current private environment and pinned image/binary reconstruction inputs before separating the broad credentials directory. |
| Native NAS Plex: supported `.qpkg/PlexMediaServer/.../Plex Media Server` → package-path exception | Observed main process UID/GID 0:0, broad effective capabilities. Plex account/profile/API token is separate from OS identity; multiple libraries do not imply multiple NAS runtime accounts. | `svc-plex` inventory label unless package supports it; `package-state(plex)` RW, private/general media R target. Host root can exceed these grants. | Native package/startup, all existing library roots and private grants; Seerr/Arr consumers and separate HA Plex. | Daily three-file preferences/DB settings export, artwork/binaries excluded; H SQLite restores passed, replacement startup not established. Verify supported identity controls; do not move package internals. |
| HBS/QTS/Container Station: native package/config paths → supported exceptions | Native root rsync/RTRR workers observed; complete HBS child-process census not performed. Existing QTS local administrator and B2 credential are separate identities. | `svc-originals-backup` is a proposed purpose label, not a renamed native process; source-reader and scoped uploader roles remain distinct. | HBS jobs, native weekly QTS config capture, Docker daemon; Container share protected by Container Station. Today's new seed is separately owned work. | Settings exports cover native QTS artifact and HBS DB snapshots; not replacement NAS boot. Keep platform roots and active jobs; do not edit HBS databases. |
| Retired NAS DC: `/share/Container/home-identity/{dc-state,tls,secrets}` → retained recovery exception | Container stopped, no runtime PID; old identity matches live HA domain. | No new runtime account or share; preserve cold evidence and keys. | Restart disabled/cutover guard C. Active DC is on HA. | Verified cold archive H; never start the old identity or delete it as cleanup. |
| iperf3: no persistent mounts → no data share | Actual UID/GID 0:0, default capabilities; no health check | Diagnostic/platform exception pending owner review; no data role | Existing running diagnostic listener; no benchmark started | Rebuild from deployment definition if needed. Record purpose/exposure later; not a storage pilot. |

File Station remains a retained platform dependency. This pass did not perform
a complete native-package/process census; qualify any additional package state
when it intersects a selected service cutover. No platform share was removed.

## Forgejo is one recovery unit

Selected live `app.ini` path fields, without secrets, establish:

| Component | Current source | Required preservation |
| --- | --- | --- |
| SQLite | `home-git/data/data/gitea.db` (`/var/lib/gitea/data/gitea.db` inside container) | Raw DB plus any WAL/SHM under a stopped capture; user/repo IDs, OIDC links, permissions and SSH-key records |
| Repositories | `home-git/data/git/repositories` | All Git objects, refs and repository metadata; do not substitute a source checkout for full app recovery |
| LFS | `home-git/data/git/lfs` | Objects and their database relationships |
| Attachments | `home-git/data/data/attachments` | Uploaded objects and database relationships; inventory includes full data tree, not only these directories |
| Config and keys | `home-git/data/custom/conf/app.ini`, remaining `data` and reserved `config` tree | Original application/OIDC/signing/encryption/SSH host identity; exact key paths remain private |
| Deployment/capture | `compose.yaml`, `backup.sh`, `backup.py`, `install-cron.py` | Recorded image, numeric ownership, source/output paths and host cron; preserve independent NAS decryption identity |

`git-host/backup.py` includes the entire `data` and `config` trees and those four
deployment/capture files. It rejects links and checks SQLite while Forgejo is
stopped. Bootstrap login receipts are excluded. The host scheduler has Docker
stop/start power; its worker uses **1004:100**, while publication runs inside
the **0:100** NAS backup container. Therefore capture and runtime currently
share ownership, and the publisher can read other infrastructure credentials.

Target: `svc-forgejo-backup` reads this complete consistent unit, uses a bounded
Forgejo lifecycle helper and writes only `forgejo-backups`; a separate
`svc-archive-b2` reads completed ciphertext and uses a separately scoped B2 key.
Keep per-job controls in `backup-control`, not in runtime or archive-reader scope.

Historical independent retrieval/decryption checked every file, SQLite and Git
objects; a post-OIDC archive retained original links. The October 25 B2 restore
compared seven ciphertext/receipt files. The initial stale archive predated the
newer private printer repository. The October 27 repair superseded that gap with
a fresh capture and independent verification of all 151 entries and both Git
repositories. This still does not prove replacement-server startup, attachment/LFS
retrieval through the application, or independent recovery of both current
checkouts and their unpublished inputs. Qualify those before a Forgejo data/identity
change or reliance on it as the wiki's only source recovery.

## Cloud applications and NAS archive consumers

Cloud runtime storage stays on the cloud host; proposed NAS destinations below
hold encrypted **archives**, not live cloud databases. Nine existing containers
were running; all six with health checks were healthy. `Config.User`/PUID values
are configuration evidence unless a host account/job identity is explicitly noted;
LinuxServer images have a root init and require child-process verification.

| Service / current data and credential references (O/C) | Principal and proposed separation | Consumers, protection and smallest next action |
| --- | --- | --- |
| SABnzbd: `/srv/usenet/config/sabnzbd`; incomplete/completed mounts | PUID/PGID 1991:1991 (`usenet` host account); proposed `svc-sabnzbd`, shared import group design pending. API/provider credentials remain in protected config. | Writer of scratch/completed data, Arr reader; systemd mount guards, reserves and manual pauses preserved. Settings → cloud stream → `infrastructure-backups/cloud`; October 27 outer capture/restore passed; unattended capture and NAS replica freshness remain open. |
| Prowlarr: `/srv/usenet/config/prowlarr` | PUID/PGID 1991:1991; proposed `svc-prowlarr`, own config RW; indexer/API keys in config | Arr indexer provider; settings same cloud stream. Inventory child UID and key consumers before split. |
| Radarr and Sonarr: separate `/srv/usenet/config/{radarr,sonarr}` | PUID/PGID 1991:1991; proposed `svc-radarr` / `svc-sonarr`, explicit shared import group; `arr-users` browser role is unrelated | Both bind common `/srv/usenet/library` RW plus completed scratch; hardlink/import relationship prevents blind UID split. APIs, RSS, Seerr/recovery workers and Plex notifications are consumers. Same cloud settings stream; no media move. |
| Seerr and its proxy: `/srv/usenet/config/seerr`, `compose/seerr/Caddyfile` | Configured 1991:1991; proposed `svc-seerr` and scoped proxy runtime exception. Plex login, existing Moonfin local request account and API keys preserved | App config RW, proxy config R; NAS Plex/Arr/Jellyfin linkage. Settings in cloud capture. Preserve IDs, do not replay acquisition to test. |
| Cloud browser gateway: `/etc/usenet-cloud-ui/Caddyfile` | Configured 1991:1991; proposed `svc-media-gateway`; HA-only gateway credential distinct from humans | Caddy config R; Authelia and VPN dependencies. This directory is outside cloud capture's allowlist; reconstruct from source + current escrowed gateway credential. Verify reconstruction before treating it as covered. |
| Filex portal + TLS proxy: `/etc/usenet-filex`, `/srv/usenet-filex/data`, local staging | Configured 999:982; matching host `filex` account, noninteractive. Proposed `svc-filex` on cloud is a different realm from NAS runtime. TLS/SSH keys and operator login references in Filex bootstrap escrow | DB/verification receipts RW, NAS SFTP staging and cloud source mounts; canonical roots R. Separate root capture bundles server and bootstrap state. Local bundle was included in the verified October 27 outer archive; confirm later unattended delivery and original operator trust material before any rename. |
| Recyclarr: `/srv/usenet/compose/recyclarr`, `config/catalog/recyclarr` | C configured shared Usenet identity; proposed `svc-recyclarr`, API keys R, own sync state RW | Live systemd timer present; media payload denied. Cloud capture excludes regenerable resource cache. Check current timer/user and config inclusion at its later checkpoint. |
| Seerr report/recovery workers: `/srv/usenet/libexec`, config and journals | C `usenet` (1991:1991); proposed separate `svc-seerr-recovery` scope, preserve report versus acquisition authority | Live five-minute report and fifteen-minute execute timers; HA notification/API keys and exact approved request scope. Confirm journal/config allowlist and live unit identities before runtime separation; no worker invoked here. |
| Storage Box mount / cloud deployment / VPN | Cloud host `usenet-admin` 1992:1992 deployer; `usenet` 1991:1991 runtime; provider-assigned writer login; system mount helpers/root exceptions | Proposed `svc-cloud-deploy` separate from runtime and `svc-cloud-media` shared import group as needed. Preserve existing dedicated keys, mount units, mode-0000 absent-mount guards and transport. Provider login is a documented naming exception; no replacement credential. VPN has separate on-demand recovery export. |

## Home Assistant boundary

The fresh Supervisor inventory has **27 installed apps, 23 started, four stopped**.
All 27 occur in the newest protected local automatic backup. Supervisor metadata
does not reveal every process UID/GID: host/container child credentials and each
community app's extra mounts remain **unresolved**, not assumed root or isolated.
This bounded pass inventories the recovery dependency without crawling their data
or changing HA. Native app IDs and paths remain platform exceptions; no one NAS
runtime account is proposed for all HA apps.

| Apps / service roots (C unless stated) | Identity, login and dependencies | Storage/recovery proposal and next check |
| --- | --- | --- |
| Directory, directory-route | Persistent app `/data`, addon config, SSL; existing AD SIDs/GUIDs/password material and original maintenance/CA keys. Route needs network capabilities; live NAS copy stopped. | Preserve native locations. HA native archives → `HomeAssistantBackups`; independent identity exports → infrastructure stream only if explicitly scheduled. Cold restore evidence H; recurring off-host/native restore still unqualified. |
| Authelia, home-acme, Home Web Proxy | Authelia config/MFA DB and original keys; AD `svc-authelia` lookup, SMTP/OIDC secrets. ACME `/data` + addon config + `/ssl`; DNS API key. Proxy built from source, TLS R. | Keep lookup/runtime/publisher/decryption roles separate. Native local backup includes apps/SSL; controller CA and credential escrow live outside HA. Verify native off-host recovery before identity storage changes. |
| HA Core | `/config` including DB and integration credentials; existing HA auth/ingress, Supervisor-owned processes | Included in newest native backup, unlike Talos add-on export. Recovery writer `svc-ha-backup` would access only native archive share; do not reuse `hass`. |
| MongoDB, Printer, TinyURL | MongoDB private `/data`; printer depends on DB and `/share` output/idempotency paths; TinyURL depends on DB. App/runtime IDs still to inspect | Native app backup includes DB; daily archive omits `/share`. Talos on-demand export includes `/share` but is unencrypted. Classify required output versus regenerable files and encrypt separate export before offsite use; no printer source changes here. |
| Grid Dashboard, Snapshot Service | Repository built apps; dashboard configs, snapshot service runtime; consumer API/device references remain private | Preserve native paths and native backup; no NAS service share required. Check unique persisted state before declaring entirely rebuildable. |
| Sonos API; Node Sonos HTTP API (stopped) | Native app state/presets and device access; media metadata kept private | Current native archive contains both; stopped installation is not disposal authorization. No new NAS data role. |
| HA AdGuard; UniFi Network Application | Native private app configuration/databases and existing app administrators; DNS/gateway dependencies | Included locally; separate DNS policy snapshot is not full primary state. No share move; require native restore/off-host proof and keep their operating runbooks authoritative. |
| HA Plex | Separate native Plex account/server state; active `/media/FromDrobo` SMB source **O**; mount credential account/realm and native process mapping still to verify. Do not retire legacy `hass` before accounting for this consumer | Latest protected archive now includes Plex app. NAS Plex settings stream does not cover it. Verify native offsite restoration of this app before changing the mount or retiring any NAS consumer. |
| HA Radarr; Whisparr (stopped) | Separate native installations and private app config; distinct from cloud Arr, identities/mounts not yet inspected | Included locally; do not merge credentials or infer ownership from cloud services. Bounded app-info/mount check later if their NAS dependency affects a chosen cutover. |
| Z-Wave JS; Mosquitto; Silicon Labs Multiprotocol; Matter Server (stopped); SONOFF Dongle Flasher (stopped) | Native app state, radio/device permissions and protocol credentials; actual process mapping unresolved | Preserve hardware and app identities. Native archive recovery stream; no NAS share beyond archive destination. No device operations in this inventory. |
| Terminal & SSH; Tailscale; ESPHome; Whisper; Piper | Native app configuration/keys and optional generated state; dedicated HA SSH key remains explicit | Included locally; native platform/runtime exceptions pending individual recovery audit. No storage authority transferred. |

## Backup producers, uploaders and archive policy

**P** per-share profiles remain those in the protection plan: Forgejo/Application
recovery daily source checkpoint with 36-hour alarm, proposed B2 30 daily + 12
monthly recovery points; Rebuild for proven reproducible wiki bytes; native HA
archives as their own policy. These retention/upload proposals are not deployed.

| Job / source and controls | Actual identity, schedule and observed output | Target scope, denials and evidence / prerequisite |
| --- | --- | --- |
| NAS qnap-config, plex-config, nas-system-config | Container root:100 with DAC_OVERRIDE/SETUID/SETGID; `U/config/backup` recipient/offhost/crontabs, `U/scripts`, `U/bin`. Minute 7 hourly, 23-hour due gate C. **O** last success October 27 16:15:30, all three remote ciphertext flags true. Output `B`; confined Hetzner NAS-settings credential | `svc-settings-backup` enumerated source R and `backup-control/infrastructure-capture`; writes `infrastructure-backups`. Today whole `U` is mounted R and archive parent RW, so cross-service/Forgejo archive denial is not established. H independent settings decrypt/SQLite checks; requalify enumerated mounts before split. |
| Cloud encrypted settings + NAS replica | Live systemd service `usenet:usenet` 1991:1991, hourly due/retry; cloud-admin public recipient. `/srv/usenet/backups/scheduled` → provider `catalog/.backups/cloud` → NAS `B/cloud` via reader credential | Proposed `svc-cloud-backup`, infrastructure archive writer/replica reader. Capture enumerates settings/DB/journals/Filex bundles, not media. October 27 repair: fresh capture, Hetzner readback and independent restore passed. Unattended capture and NAS mirror freshness remain open; healthy NAS scopes do not prove either. |
| Filex inner capture | Live root service (blank systemd User/Group defaults), hourly daily-due gate; `/etc/usenet-filex`, SQLite/verification receipts → `config/filex-recovery/latest.tar.age`; bootstrap bundle separately encrypted | Proposed `svc-filex-backup` or bounded root exporter exception. Only ciphertext should pass to cloud uploader. Local October 26 capture was included in the verified October 27 outer archive; later unattended delivery remains open. H independent server/bootstrap/DB restores; preserve operator CA custody. |
| Forgejo full capture + Hetzner publication | Host root cron expected minute 23 hourly; worker 1004:100; publication through root:100 backup container. `B/forgejo`, same confined provider account under `archives/forgejo`; October 27 repair restored one job in each cron table and verified a fresh complete archive | `svc-forgejo-backup` capture/control and archive writer; `svc-archive-b2` completed-archive R only. Runtime denied backup/key scope. Preserve ≥7 generations and all <90-day local archives, indefinite provider history. The minute probe passed and was removed; normal-cycle capture, post-maintenance schedule persistence and isolated app startup remain open. |
| Native QTS settings producer | Existing platform cron `4 3 * * 3 /etc/init.d/backup_conf.sh`; current artifact source `/share/CACHEDEV1_DATA/.@backup_config` | Platform/root exception; nas-system export validates artifact freshness/size plus HBS SQLite snapshots. Not a full NAS image or tested replacement boot. |
| HBS originals/laptop + encrypted-archive uploader | Existing native package/B2 credentials, selected five roots. Concurrent working runbook records old daily 02:00 latest-30 job, Monday 16:00 quick / month-day-1 17:00 full checks, plus manual QuDedup production seed | Eventually split originals/laptop from archive uploader scopes, with separate credentials and aggregate bandwidth policy. Current broad native job is not OS isolation. H small B2 ciphertext restore and synthetic QuDedup restore passed; production seed completion/restore, originals ACL recovery and Time Machine restore are unqualified. Preserve other work/history. |
| HBS one-time restore/trial jobs | Existing October 25 settings restore, October 27 synthetic dedup source/restore and production-seed follow-up C; no new job created here | Keep private evidence/test directories and independent job owner. They are outside this migration's cleanup scope. |
| Native HA automatic backup | Core/Supervisor native producer, daily/three local copies C; newest protected archive and local-only location O | Proposed QNAP-local `svc-ha-backup`: native archive read/write/prune only on `HomeAssistantBackups`; `svc-ha-backup-replica` R there + independent B2 destination. No media/other archive access. Emergency-kit custody and offsite restore remain prerequisites. |
| Talos add-on export; identity HA/AD export; Jellyfin export | Operator-triggered via dedicated HA/NAS keys; no recurring timer claimed. Talos includes repository apps + `/share`, excludes Core/SSL, unencrypted; identity export includes identity apps/SSL, age encrypted; Jellyfin stopped-state age export | Keep distinct contracts; encrypt unencrypted exports before any archive upload. Cold work requires a scoped downtime decision. Historical decrypt/restores do not prove recurring delivery. |
| VPN, checkout/durable-state and credential escrow | Operator-triggered; dedicated cloud/NAS identities, existing age/SOPS recovery keys. External controller state and private CA remain outside Git; ciphertext vault tracked | Restore/rebuild prerequisite for service definitions, private printer source and credentials. No blanket recurring offsite coverage inferred from old checkout snapshots. Preserve original bound snapshots and both recovery-key systems; never place master decryption keys on producers. |

For every stream record source checkpoint time separately from upload/replica
time. `status: ok` in an old file is not freshness. Old ciphertext and source
identity mappings remain necessary after any future rename; no history was pruned.

## First pilot: wiki preparation, then separate identity and path checkpoints

**October 27 preparation implemented locally; live checkpoints remain open.**
Start with wiki. Forgejo has
unique mutable state and is a source-recovery dependency; DNS discovery is degraded;
backup infrastructure has an active seed and newly repaired capture streams awaiting
unattended qualification. Wiki's runtime has no database, credentials,
persistent writer or media bind. That supports a small reversible pilot, but
does **not** yet qualify all its build/recovery inputs or QNAP local permissions.

1. **Preparation/rehearsal implemented (safe while storage gate remains closed).** Added
   `qnap_wiki_uid` / `qnap_wiki_gid` inputs, defaulting to today's `qnap_uid/gid`.
   Reused Compose's existing `WIKI_UID` / `WIKI_GID` contract; passed the new Ansible
   inputs through publish and rollback roles without changing `qnap_wiki_root`,
   deployment credentials or defaults for any other service. Do not populate a
   new numeric ID in durable inventory. Verify current-default rendering and
   independent override rendering. Rehearse accepted/rejected releases, unchanged
   repeat publication and rollback with synthetic local inputs; restored retained
   environments must restore their identity too. Review source/build recovery for both
   smarthome and printer; preserve exact current/previous release metadata.
   Rollback is reverting only the preparation patch; no production state changes.
2. **Synthetic NAS identity checkpoint (later, explicit qualified scope).** Check
   supported local account/group creation and collisions in Safari. Allocate
   `svc-wiki` with no admin/SMB/shell need, preserve deployment owner, and test
   R/traverse on a fixture publication with write/rename/delete and unrelated
   service/archive denial. Test QNAP ACL behavior using the actual account: the
   Filex runbook records unknown numeric UIDs being mapped to denied guest ACLs.
   Removing only fixture grants and disabling an unused pilot account reverses
   this checkpoint; no existing owner or path changes.
3. **Runtime identity checkpoint (separate decision/window).** Requires qualified
   recovery inputs, current service/backup health, no competing wiki publisher,
   saved ACLs/environment, and an agreed wiki-only interruption (propose at most
   two minutes; not yet approved). Grant only enumerated published inputs R,
   switch this runtime, keep all paths and deployment identity. Verify PID/child
   UID/groups/capabilities, R binds, local and SMB denials, both ports, matching
   publication digest, HTTPS MFA gate, direct numeric recovery route and one
   normal settings capture. Roll back saved environment/ACLs and the previous
   immutable runtime; no recursive chown, no other service restart.
4. **Named share checkpoint (after production storage gates).** Resolve a
   QTS-managed `wiki` root on the same filesystem (current source device 64519),
   exact destination absence/ACLs, and publisher/backup consumers before any
   rename. Existing Ansible asserts the old parent path; backup allowlists and
   absolute current/previous release pointers also need reviewed translation.
   Freeze all wiki publishers; use a supported same-filesystem rename only after
   those prerequisites, compare inode/metadata and update all active references.
   Verify new-path capture/rebuild and retained rollback. Reverse rename plus
   saved references after reconciling publisher writes if checks fail. Do not
   combine with account creation, ownership changes or backup-history deletion.

The runtime input preparation is implemented and its local fixture checks passed.
No wiki pilot account, live identity change, deployment or share migration is
established by this preparation checkpoint. Account qualification is next.
The follow-up above repaired cloud capture and Forgejo scheduling
and verified fresh off-host archives. Normal unattended cycles still need
observation; offline wiki preparation can proceed independently. Leave ambiguous
household files,
Public/Multimedia/FromDrobo contents, full Hetzner membership and storage redesign
deferred. The removed media apps remain removed; their leftover share is still
pending supported retirement, not forgotten or silently accepted.
