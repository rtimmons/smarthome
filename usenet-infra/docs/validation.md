# Validation and remaining acceptance

Last updated: 2026-09-11. This is an evidence ledger, not a claim that the system
is complete. A local test result does not prove NAS compatibility, authenticated
browser behavior, provider acquisition, or end-to-end recovery.

## September 11 automatic publication and Plex update

- Ran 406 local cases: 398 passed and eight opt-in integration cases skipped.
  ShellCheck, JSON/YAML checks and deployment syntax checks passed, including
  the new publisher and catalog-refresh playbooks. Source/index secret scanning
  passed. The full recipe remains nonzero because history scanning detects the
  already documented 2017–2018 RSA keys; this is not a clean whole-history audit.
- All four successful SAB jobs were published, remotely verified and cleaned.
  The publisher then reported idle with four already-published receipts and no
  failures. Cloud free space measured 132,828,790,784 bytes (123.7 GiB).
- The existing NAS browser tab refreshed without manual navigation and showed
  all five remote catalog items (four movies and the official test fixture).
- NAS relocation preserved the cache inode/device and private directory inode/
  modification time; the operation copied zero media bytes. Both cache services
  restarted against `/share/FromDrobo/Movies`.
- Plex retained the existing 5,258 entries. New movie/TV libraries are separate.
  The managed profile's actual server token listed only the two new libraries;
  direct access to the private library returned HTTP 403.
- The first real movie NAS pull completed and passed SHA-256 verification.
  A read-only Plex check found `Colony (2026)` with its media file in library 2;
  no manual scan was triggered. Actual Apple TV/Roku playback and startup-profile
  behavior remain unverified. Remote streaming and native Arr import mounts
  are not deployed.
- A supplemental backup attempt was blocked by the existing requirement for
  an empty SAB queue; three paused jobs remain. The previous verified encrypted
  backup is retained. No jobs were removed or resumed to satisfy the backup.

See [NAS/Plex layout](nas-plex-layout.md) and [workflow review](media-workflow-review.md).

## September 11 discovery and recovery acceptance

The master-key clean-clone secrets/state milestone passed; see the
[drill report](../recovery/drills/20260911T194408Z.json). The selected Radarr and
Sonarr releases initially deployed with two interactive-only indexers and one
SAB client each. The user subsequently authorized automatic search and RSS for
both apps (15-minute interval). Automatic retry, completed import and download
removal remain disabled. Read-only lookup returned movie/series results; Radarr's
trending/popular Discover feed returned 30 movies. No titles, subscriptions or
downloads were added. Both real private paths deny anonymous requests with 401.
The in-app browser blocked the VPN URL; user-browser visual login remains
unverified. The original three notices concerned disabled RSS/search/importing. The current
policy accepts only the disabled-import notice; RSS/search problems fail checks.

The final Usenet suite passed 389 of 397 cases, with eight opt-in runtime skips;
all 13 isolated proxy tests passed separately, including those eight runtime
cases. Compilation, ShellCheck, configuration parsing and all four Ansible
syntax checks passed. Current source/index scanning passes. The full history
scan still fails for the [two historical RSA keys](security-findings.md).
The final root `just test` passed all repository tests and all seven add-on
container checks before preparing this checkpoint.

The [new supplemental NAS backup](../recovery/application-backups/20260911T201003Z-bcb62179eb783aef.json)
contains 601 files and four integrity-checked SQLite databases. Its upload and
download matched byte-for-byte, authenticated decryption passed twice, and
verification also passed with the key restored by the prior clean-clone drill.
It does not establish a new application-startup or machine-replacement drill.
See [discovery operations](discovery.md) for versions, expected notices and the
supplemental restore format. Older sections below preserve earlier acceptance.

## Verified live

| Check | Evidence/result |
| --- | --- |
| Protected cloud/storage infrastructure | CX43, Primary IPv4/IPv6, firewall, SSH key, BX11 and read-only subaccount provisioned; both Terraform roots rechecked with no changes |
| Cloud bootstrap | Earlier live Ansible convergence recorded `changed=0`; dedicated non-root SSH login, root/password denial, and restricted inbound SSH verified |
| Cloud applications | SABnzbd and Prowlarr container-healthy on VM loopback only |
| Storage writer/reader separation | Writer-created disposable sentinel readable by QNAP subaccount; overwrite/delete denied, SHA-256 preserved, writer removed fixture |
| Current cloud health | Exit 0; Storage Box, catalog-failure checks, Prowlarr, and scratch capacity pass. Seven historical SAB warnings classified: six setup hostname blocks and one Direct Unpack autotest notice; zero authentication/provider/TLS failures |
| Dedicated-key cloud UI tunnel | Workstation loopback returned SABnzbd HTTP 303 and Prowlarr HTTP 200 through `cloud-ui`; tunnel closed after smoke test |
| Eweka transport | Independent VM check verified TLS 1.3 with strict certificate validation and an NNTP 200 greeting; authentication and download are separate checks |
| Eweka configuration and authentication | Saved settings verified: `news.eweka.nl:563`, TLS with strict verification, 20 connections, priority 0, Required on, Optional off, retention 0; credential-preserving update succeeded, second configure returned `changed=false`, and SABnzbd's built-in saved-credential test passed |
| NZBGeek subscription | User confirmed $12 USD one-year payment through official Stripe checkout; independent account readback active through 2027-09-13 22:01:53 UTC. This verifies subscription status, not the Prowlarr API connection |
| NZBGeek API connection | Saved and enabled in pinned Prowlarr 2.5.2.5491; live credentialed test passed, including after application-key rotation, with global strict certificate validation enabled, HTTPS base `https://api.nzbgeek.info`, path `/api`, priority 25. Daily query/grab quotas remain unknown and unset |
| NZBFinder subscription | User confirmed Pro payment and authenticated Pro badge independently observed. Plan advertises $30/year, 20,000 API requests, unlimited downloads; currency code, final charge, expiry/renewal remain unverified |
| NZBFinder API connection | Saved entry ID 2 enabled; live credentialed test passed with HTTPS base `https://nzbfinder.ws`, path `/api`, priority 25, global strict certificate validation, and unset query/grab quotas |
| Prowlarr private login | User configured Forms authentication privately |
| Prowlarr application API-key rotation | Supported ResetApiKey command completed; old key HTTP 401, new key HTTP 200; protected dependent environment synchronized with mode 0640 and owner preserved, all other XML settings unchanged, no restart. Saved-client retest passed |
| Prowlarr SABnzbd client | Exactly one enabled client at internal Docker HTTP `sabnzbd:8080`; `prowlarr` category has `pp=3`, script `None`, empty directory, normal inherited priority. Only literal `sabnzbd` added to existing SAB host whitelist, preserving all entries and checking. Candidate, saved-credential, and standalone tests passed; second configure reported `changed=false`, `category_created=false`, `hostname_added=false` |
| SABnzbd storage and processing defaults | Applied and read back: incomplete `/data/incomplete`, complete `/data/complete`, both free-space thresholds `30G`, default category `pp=3` and no script, watched-folder scanning disabled; repair/unrar/7zip/PAR cleanup enabled and direct unpack/scripts disabled. Queue/post-processing were empty, with no enabled RSS or custom workflows. Second live apply returned `changed=[]` and `changes_needed=[]` |
| Direct Unpack after diagnostic test | The one-time autotest enabled Direct Unpack; bounded settings apply restored `direct_unpack=0`, all intended settings matched readback, and there were no active jobs |
| Official provider download and processing | Single submitted job recorded in a persistent receipt; status completed, 107,455,358 downloaded bytes, `pp=D`, recognized Repair and Unpack success, no failure message, `processing_checks_passed=true` |
| Test-item promotion | Published `sabnzbd-official-100mb-2026-09-10` under `catalog/objects/other/` with provenance and SHA-256 manifests; `rclone check --download` found 2 matching files and 0 differences |
| Encrypted cloud configuration backup | Refreshed after both indexers, application-key rotation, catalog/health updates, and Direct Unpack restoration: captured/encrypted on VM, transferred as ciphertext, locally decrypted/extracted against allowlist and SHA-256 manifest; 589 files and 2 SQLite databases passed integrity verification. Capture does not restart applications |
| QNAP read-only UI discovery | User-opened trusted Firefox session at `https://rynapqnap.local/cgi-bin/` confirms TS-451D2, QTS 5.2.10.3577, Celeron J4025 2 cores/2 threads, 4 GB RAM, and Container Station/HybridMount icons. QTS login as `usenet-deploy` verified; Telnet disabled |
| QNAP dedicated SSH login | User created `usenet-deploy` and installed the repository public key; QTS MD5 fingerprint matches the local key. First public-key SSH login succeeded on `rynapqnap.local:22` with no agent/password fallback. UID 1004, primary GID 100 (`everyone`), NAS supplementary groups 0 (`administrators`)/100; Linux 5.10.60-qnap, x86_64 |
| QNAP host-key trust | User explicitly authorized first-use trust of 3072-bit RSA host key `SHA256:jXVysXlhzn80Tk2BYg8CGNkfMCqjCEpyu0PyyHJX5RA`; pinned ignored known-hosts file mode 0600 with strict checking. This is authorized TOFU, not independent host-key verification. Three QNAP connection fields set in protected mode-0600 `.env` |
| QNAP runtime reconnaissance | Container Station 3.1.2.1742, Docker 27.1.2-qnap8, Compose 2.29.1-qnap2, overlay2, memory/swap cgroups supported; about 2 GB available RAM. Only existing `iperf3-1` container, about 1.16 MiB RAM/0% CPU. `eth0` 192.168.1.66/24 default LAN; port 1337 unused before deployment |
| QNAP share and deployment preparation | QTS Usenet share created on GPvQNAP volume, only `usenet-deploy` RW among listed users and guests denied; `/share/Usenet` resolves to `/share/CACHEDEV2_DATA/Usenet`, about 1.37 TB free/69% used. Cache root `/share/Usenet/usenet-cache`. App directory `/share/Container/usenet` created 1004:100 mode 0750, Container volume about 42 GB free. Protected inventory/env uses reader subaccount, 100 GiB cache free-space floor; user-created Argon2id dashboard auth file verified mode 0600. Authenticated dashboard login, runtime security, dashboard/CLI transfer and eviction, restart, and isolated configuration restore verified |
| QNAP build-state compatibility | First build failed on Docker/Buildx state under the unwritable Container Station package home. Scoped client state under `/share/Container/usenet/state/docker-client`, 1004:100 mode 0700, passed Compose validation and default-driver Buildx inspection; deployment continued; no stack service started during failure/probe. Subsequent live launcher-ACL and catalog alias/home-relative path fixes are recorded in the bootstrap runbook |
| QNAP runtime security | Both services use UID 1004/GID 100, read-only root, all capabilities dropped, no new privileges, no privileged mode or Docker socket; dashboard process groups are only [100], page size 4096. Listener only 192.168.1.66:1337, no global IPv6 addresses. Existing iperf3-1 remains running since 2026-08-18, restart count 0. Post-eviction idle sample: dashboard 63.65 MiB, rclone 33.02 MiB, both 0% CPU, NAS about 1.94 GB available RAM |
| QNAP CLI parity and restart | Dashboard deliberately stopped and unreachable; CLI list/status/pull worked over dedicated pinned SSH. Independent local SHA-256 checks matched 2 files/100,000,019 bytes. CLI eviction returned local 0/remote 1; remote files were re-downloaded and hashed unchanged, with unchanged manifest SHA-256 fd90dacd144b4f42ca7f955915cbac4873748f438d069589a1ac36597ffb29ec. Dashboard/rclone healthy after restart, no failures/active/stalled operations, unrelated iperf unchanged; drill took 227.5 seconds |
| Encrypted QNAP configuration backup | First live 32-file capture and complete authenticated local decrypt/checksum verification passed; media excluded, runtime config/sessions included and no hidden runtime files missing. Separate isolated startup restore passed, preserving authentication/session/history bytes; see the local restore evidence below |
| QNAP final restart state | User browser login and completed SHA-verification output/history survived the actual NAS dashboard restart. Both stack services healthy, about 108 MiB combined idle RAM, no unrelated container changes |
| QNAP anonymous access after restart | Init HTTP 200 requires login and exposes no navigation/search hints; GetDashboard, GetEntities, GetLogs, and GetActionBinding for catalog-refresh return HTTP 403 permission_denied. A deliberately nonexistent StartAction returns HTTP 404; that is invalid-request rejection, not execution-authorization proof |
| QNAP health before CLI parity | All six checks passed: Storage Box usage 100,270,080 / 1,099,511,627,776 bytes, no unresolved failures/pulls, dashboard ready with 9-second-old heartbeat, 1,372,510,670,848 free bytes and 107,374,182,400-byte reserve. Both Terraform roots rechecked with no changes |
| QNAP dashboard transfer and eviction | Authenticated summary showed one 95.4 MiB remote item, zero local items, 100 GiB reserve and about 1.2 TiB free; category/title search found it. Click download ran 23:33:28–23:34:13 UTC, remained running across closing/reopening the tab, then reported SHA verification, atomic publication and local state. Removal required the explicit remote-copy-remains checkbox; Start stayed disabled until checked. Eviction 23:36:37–23:37:07 UTC returned one remote-only/zero local items. Action history preserved user/status/output and earlier setup errors |
| Optional HybridMount UI inspection | HybridMount 1.17.5691 verified from QPKG CacheMount. Existing signed-in app opened, intro dismissed, enhancement telemetry declined; File Cloud Gateway/WebDAV Cloud/Server and Server URL/Account/Password fields observed, with no SSH-key option. Wizard closed without remote credentials, connection, or cache allocation. Not adopted based on key-only SFTP reader and documented read-only WebDAV listing limitation; no live connection failure claimed |

The initial reader sentinel was exercised from the cloud. A subsequent direct
NAS check also read the writer-created fixture successfully; the server
rejected overwrite/delete with SSH_FX_FAILURE, the writer verified the original
SHA-256, and only that fixture was removed afterward.

The latest verified cloud archive is
`/Users/rtimmons/Projects/smarthome/usenet-infra/backups/cloud-20260910T225152Z-SIfVfDwC.tar.age`
(ignored, mode `0600`), SHA-256
`07df7ddf0ec8153b5ba5c99f458bce609c6439a2ff1bfd6b34a04c5b43d07088`.
The earlier archives are preserved but superseded.
Only the public encryption recipient is on the VM; the private key remains
on the workstation. Remote temporary ciphertext was removed after verified
local publication, and local plaintext verification directories were cleaned.
Capture, encryption, transfer, verified extraction, and a separate isolated
application-startup restore drill now pass. The first live QNAP capture, authenticated verification, and isolated startup
restore also pass. Scheduling and an independently
verified key copy remain pending. Scope and the `backup-cloud`,
`backup-verify`, and `backup-restore` commands are in [recovery](recovery.md).
This refreshed archive includes both indexer keys, the rotated Prowlarr
application key, login/client settings, restored Direct Unpack setting, and
current cloud catalog/health scripts. Archives captured before the key rotation
require rotation of their restored Prowlarr application key before reuse,
as described in [recovery](recovery.md).

## Verified isolated cloud restore

The latest cloud archive passed an offline startup drill with the exact pinned
SABnzbd 5.1.3 and Prowlarr 2.5.2.5491 image tags on local rootless Linux/arm64
Podman. Both containers had network disabled, no published ports, only isolated
app configuration volumes and empty scratch; no writer key or decryption key
was mounted. Saved local API credentials worked. SABnzbd returned queue 0 and
history 1; Prowlarr retained both enabled indexers, its enabled SABnzbd client,
and Forms authentication.

After clean shutdown, both SQLite databases passed integrity checks. All
configuration/user/indexer/client/profile/application/proxy/tag rows in Prowlarr
and both SABnzbd history/RSS tables were unchanged. Every Prowlarr XML field
and 49 selected SABnzbd credential/provider/category/path/safety settings were
preserved. Both private plaintext trees, test containers, and volumes were
removed; sanitized evidence is `build/usenet-restore-startup-20260910.json`.
No live cloud/NAS services, canonical data, or acquisition egress were involved.
This proves app restore/startup on arm64, not replacement of the x86_64 cloud
VM, provider connectivity from the isolated copy, or QNAP restoration. See the
[repeatable recovery procedure](recovery.md#verified-offline-cloud-application-restore-drill).

## Verified isolated QNAP restore

The first live 32-file NAS archive passed local authenticated extraction and
startup with the pinned OliveTin 3000.19.0/rclone 1.75.1 image. It ran as
1004:100 with read-only root, dropped capabilities, no new privileges,
network disabled, and no published ports. The reader key and production
environment remained unmounted; an empty local catalog and cache replaced the
remote paths only in the effective test environment.

Ready HTTP 200, a successful fixture refresh, and anonymous history HTTP 403
passed. OliveTin loaded all three saved results, skipped zero, and reported no
session-load error. After clean shutdown, authentication and session bytes and
all six history result/output files were identical. No password or copied
session credential was used for authentication. The archive was unchanged;
all plaintext trees, containers, and volumes were removed. Sanitized evidence:
`build/usenet-qnap-restore-startup-20260910.json`. This checks restored startup
and retained state on local arm64, not replacement of the x86_64 NAS or a fresh
password login. See [recovery](recovery.md#verified-offline-qnap-application-restore-drill).

## Locally implemented, requiring live validation

The repository provides Terraform, cloud/QNAP Ansible roles, pinned Compose
stacks, deliberate manifest-backed promotion, selective cache commands, and the
OliveTin dashboard integration. The dashboard uses structured catalog state and
the same guarded pull/eviction backend as the CLI. Repository tests cover local
safety logic and configuration; see the current `just test` output and `tests/`
for the exact cases rather than assuming a fixed count as coverage grows.

The latest full `just usenet-test` run passed 183 tests on
2026-09-10, including 18 indexer, 17 download-client, 16 health,
14 cloud-backup cases exercising the actual age binary, 17 QNAP-backup cases,
4 reconnaissance cases, and 2 new remote-path regression cases. Python compilation,
ShellCheck, JSON/YAML parsing, pinned site and backup Ansible syntax, and the
source/history secret scan also passed, including the reconnaissance and
dynamic Docker-path changes. `git diff --check` was clean. That
count is a dated snapshot, not a substitute for rerunning the suite after
further changes. Cloud health compatibility is now verified live after the
tested catalog script was installed atomically alongside the updated health
helper. No application restart, schema-1 format migration, or content mutation
was required.

An independent offline QNAP deployment check passed 51 cases using the actual
Jinja templates, pinned Ansible 2.21.4, and a disposable Alpine 3.24 container
without network access. It exercised exact multiline/quote/dollar/backtick
payload bytes, unchanged-file inode preservation, mode repair, corrupted
decode/hash failures, preservation on chmod/move failure, and rejection of
invalid private addresses and deployment paths. This checks deployment logic;
it is not evidence that QNAP firmware or shares behave identically.

The built OliveTin 3000.19.0 image also passed the version-output smoke check
as a non-root user with read-only root filesystem, no network, and no host
mounts. Its upstream version command exits 1; deployment checks the reported
version rather than treating that exit code alone as an incompatible image.

The combined pinned dashboard image was built and exercised locally on arm64
under UID/GID 501:20, read-only root filesystem, dropped capabilities and no
Docker socket. Browser/API checks with generated local test content passed:

- Login and title/category search worked; anonymous dashboard/entity/history
  access was denied. A guest action request produced only a blocked tracking
  record with `executionStarted=false`, never a running storage operation.
- Download staged and SHA-256 verified the item, then displayed it as local.
  Local eviction required the explicit remote-copy-preservation checkbox and
  returned the item to remote only with unchanged fixture bytes.
- A deliberately slow 16.5 MiB pull continued after browser closure and repeated
  configuration refreshes. Execution output exposed progress and verification.
- After container restart, the authenticated session and three successful
  action records survived, including initiator and confirmation arguments.

These are real local container/browser checks using generated fixtures. They
do not use the live Storage Box or the QNAP and do not complete the NAS or
provider end-to-end acceptance matrix below.

The source/history secret scan passed at the current interim checkout. It must
be repeated after the remaining configuration and before final handoff.

A local successful suite should include Python unit tests/compilation,
ShellCheck, JSON/YAML parsing, pinned Ansible syntax, and the secret scan. Run
`just test` from `usenet-infra/` after changes. Repeating image startup,
login/ACL behavior, browser interaction, persistent execution history, and
network-exposure checks on the actual NAS is recorded separately below; only
the external reachability probe remains outstanding from the required flow.

## Account details and bootstrap status

- Eweka's final charged tier and renewal details have not been independently
  verified. Its saved settings, authenticated built-in test, and official
  provider download/processing have passed.
- NZBGeek's paid one-year subscription and live Prowlarr API test have passed.
  Daily API/download quotas and automatic rebilling
  remain unverified. The public capability endpoint's 100 results per request
  is a pagination limit only.
- NZBFinder Pro is paid and its saved/enabled Prowlarr connection passes.
  Charge currency, expiry, and renewal details remain unverified. The
  advertised API/download counters reset
  24 hours after each request.
- QNAP account/key access, first-use host trust, runtime discovery, selected
  shares, numeric ownership, and private dashboard credentials are complete.
  The pinned images, private login, dashboard transfer/eviction, CLI parity,
  restart persistence, and configuration restore drills passed. Observations
  and the exact trust basis are recorded in [QNAP bootstrap](qnap-bootstrap.md).
- The dashboard runs at `http://192.168.1.66:1337`. Authenticated login and
  anonymous-access denial are verified; the external reachability probe awaits
  explicit approval after automatic review rejected it. LAN binding alone
  does not prove Internet isolation.

Complete accounts one at a time through [account setup](account-setup.md). Do
not ask for or record passwords/API keys in this ledger. Eweka is the sole
provider for the current baseline. The user deferred UsenetExpress until real
missing articles or a completion gap demonstrates a need; it is not an
acceptance blocker. Recheck pricing and terms if revisiting a fill provider.
Both indexer API tests are complete. Repeat NZBGeek's without exposing its saved
key using `just usenet-prowlarr-indexer test`, or inspect approved settings
with `just usenet-prowlarr-indexer inspect`. The `enable` command tests before
enabling and verifies the result; an enabled entry is left unchanged.
The helper's optional second argument defaults to `nzbgeek`; use `nzbfinder`
for Finder, including `just usenet-prowlarr-indexer test nzbfinder`.
Repeat bounded provider checks
with `just usenet-sab-provider inspect` and `just usenet-sab-provider test`
from the repository root; `configure` reapplies the documented primary settings
while preserving saved credentials.

## End-to-end acceptance matrix

The official 100 MB NNTP test has completed live. Pinned SABnzbd 5.1.3
[UI source](https://github.com/sabnzbd/sabnzbd/blob/5.1.3/interfaces/Glitter/templates/static/javascripts/glitter.main.js#L793-L815)
uses [this official test NZB](https://sabnzbd.org/tests/test_download_100MB.nzb).
The metadata checked on 2026-09-10 is 19,584 bytes with SHA-256
`c369cfb5e00ebbba843f145e931d6616c322224a1a7267a3a9b42c1d82114ca7`.
It references four RAR volumes and PAR2 index/recovery files in
`alt.binaries.test`, posted 2025-11-22. The declared segment total is
114,967,316 bytes; the nominal test size excludes transfer/recovery overhead.
Only the NZB metadata is fetched over HTTPS; the payload exercises the
configured NNTP provider. The completed normal-priority run reported
107,455,358 downloaded bytes, `pp=D`, recognized Repair and Unpack success,
no failure message, and `processing_checks_passed=true`. Its 1.0-second
download and 0.0-second post-processing fields are coarse counters, not a
throughput benchmark. Successful verification does not imply damaged blocks
needed reconstruction.

`just usenet-sab-smoke-test status` reads the existing saved receipt and exact
job status from the repository root. Its `start` command refuses to enqueue a
new job when a receipt already exists, including an uncertain prior submission.
The completed output was promoted as `sabnzbd-official-100mb-2026-09-10` to
`catalog/objects/other/sabnzbd-official-100mb-2026-09-10`, with provenance and
SHA-256 manifests. A full remote download comparison verified both output
files with no differences. NAS dashboard download and eviction now passed against this item, including
closing/reopening the browser during the download. CLI parity and remote preservation also passed with the dashboard stopped;
the remaining recovery/failure checks follow separately.

Use one small, unquestionably authorized test item. Record its source/license
or provider test mechanism, immutable catalog ID, manifest SHA-256 and test date
without credentials. A generated file can exercise promotion/cache safety but
cannot by itself prove the NNTP/SABnzbd path. The matrix separates completed NAS checks from the remaining transfer and
recovery checks.

| Gate | Required evidence | Status |
| --- | --- | --- |
| Primary provider | Eweka built-in connection test plus authorized transfer over TLS with strict certificate verification | Passed live: saved settings, authenticated built-in test, official NNTP test download |
| Optional future fill provider | Only if a demonstrated completion gap warrants it: fresh price/terms check and tested TLS, lower priority, Optional configuration | Deferred by the user; not required for the current Eweka-only baseline |
| Indexers | Both Prowlarr built-in API tests pass with recorded limits and endpoints | Passed live: NZBGeek and NZBFinder saved/enabled with strict TLS and successful credentialed tests; unverified quota details remain explicit |
| Prowlarr download client | Saved internal SABnzbd connection passes its built-in test without exposing credentials | Passed live: one enabled internal client, candidate/saved/standalone tests and idempotent reconfiguration |
| Acquisition | Authorized NZB completes on VM scratch; verification/repair/unpack succeeds where applicable | Passed live: official 100 MB test completed with recognized verification/unpack success |
| Promotion | Manifest published only after remote bytes verify; provenance and authorization recorded | Passed live: test item, 2 remote files matched with 0 differences |
| NAS image/runtime | Exact model, kernel/page size, Docker/Compose and all pinned images work without reboot | Hardware, kernel/page size 4096, Docker 27.1.2-qnap8, Compose 2.29.1-qnap2, Container Station 3.1.2.1742, restricted runtime and resources verified; both pinned services work, no NAS reboot or unrelated container restart |
| Dashboard login/exposure | Anonymous/invalid-login catalog actions denied; authenticated session works through private path; no public listen/forwarding | Authenticated login, exact private listener, and anonymous dashboard/entities/history/action-binding denial passed. External probe was not performed because automatic approval review rejected it; private binding alone does not prove WAN closure |
| Dashboard summary/browse | Remote/local counts and sizes, capacity/reserve, active/failure counts, title/category filtering and correct item states | Passed live: 95.4 MiB fixture, remote/local transitions, 100 GiB reserve/about 1.2 TiB free, search and active execution visible |
| Point-and-click download | Select item without transcribing ID; running status and useful execution output/history remain visible | Passed live: selected official fixture; running execution and retained user/status/output history observed |
| Browser disconnect | Close/reopen browser during transfer; same execution remains observable and completes without a duplicate operation | Passed live: closed/reopened during 45-second download, still one running action, same action completed |
| Backend integrity | Hidden staging, sufficient free-space reserve, every manifest SHA-256 verified, same-filesystem atomic publication | Dashboard transfer history confirmed SHA-256 verification and atomic publication with reserve available; independent CLI pull then verified both files against their SHA-256 manifests |
| Local state | Dashboard and CLI both report verified item `local`; no staging object appears complete | Passed live: dashboard and independent CLI pull reported verified local state; CLI independently hashed both files before eviction |
| Safe failure/retry | Interrupted/stalled detection, verified staging reuse, safe retry and failure history | Covered by local tests for interrupted operations, checksum failure, verified staging reuse and successful retry; no deliberate NAS transfer fault was injected |
| Concurrent mutation | Second pull/eviction is rejected while another holds the shared lock; state refresh still works | Passed local interprocess-lock and child-process lifetime tests; no simultaneous destructive NAS action was injected |
| Local eviction | Confirmation says remote copy remains; only NAS object/state removed; item returns to `remote only` | Passed live dashboard flow: Start disabled until explicit remote-copy-remains checkbox; completed eviction returned remote-only/zero local items |
| Remote preservation | Writer verifies identical canonical bytes/hash after dashboard eviction and CLI eviction | Passed live: independent remote re-download/hash after both evictions matched 2 files/100,000,019 bytes and unchanged manifest SHA-256 |
| CLI parity | list/status/pull/evict work through the same backend while the dashboard is stopped | Passed live: dashboard stopped/unreachable, all four CLI operations succeeded; only test item evicted, remote preserved |
| NAS read-only proof | NAS credential reads fixture but cannot create/overwrite/delete a disposable writer-created sentinel | Passed live: direct NAS reader matched sentinel; server rejected overwrite/delete with SSH_FX_FAILURE, writer verified original SHA-256 and removed only the fixture |
| Restart persistence | Restart only this stack's relevant containers; authentication/configuration/history survive and abandoned work is recoverable | Passed live: scoped dashboard stop/start preserved user login and completed SHA-verification output/history; both services healthy. Interrupted-work logic is covered by local tests |
| Health failures | Storage unavailable, capacity warning, unresolved/stalled pulls and dashboard unavailability are distinguishable | Local tests cover recorded/stalled failures, capacity rejection, stale/error heartbeat and unreachable dashboard; live healthy checks pass. No NAS disk or network fault was injected |
| Configuration restore | Restore encrypted app/dashboard/catalog configuration in a controlled drill and confirm private access and test-item recovery | Passed cloud and QNAP captures/verified extraction and isolated pinned-app startup with preserved config, DB rows, authentication/session/history; separate live CLI test-item recovery passed. These drills do not replace the VM or NAS |
| Final secret audit | Working-tree/history secret scans after configuration; inspect any hits without printing secret values | Passed final source/history scan and complete 183-test validation; both Terraform roots no changes |

Preserve concise sanitized evidence for each row, including actual failure text
when a gate fails. Do not reset unrelated NAS services to obtain a passing
result. Restarting application containers does not authorize rebooting the NAS.

## Optional compatibility and performance

The [HybridMount wizard inspection](qnap-bootstrap.md#optional-hybridmount-experiment)
is complete, and the optional route was not adopted. Its actual form requires
WebDAV account/password credentials; the current reader uses key-only SFTP,
and Hetzner documents a read-only GET-only limitation that prevents reliable
listing. No credentials were entered, connection attempted, mount created,
or cache allocated. Browsing icons, reserved-cache behavior, and write denial
remain untested; this is not a live failure result. It does not block the
OliveTin/SFTP architecture or authorize a write-capable workaround.

After the small fixture passes, record a representative large-file pull's
elapsed time, throughput, NAS free capacity/reserve, retry behavior, and CPU/disk
load. Tune within the Storage Box connection budget and record any bandwidth or
concurrency changes in deployment configuration. Performance has not yet been
benchmarked on this NAS.

## September 11 LAN and commit acceptance

Both private cloud UIs passed the user's browser login check. The UniFi IPsec
connection passed selector/peer validation, explicit PFS14 rekey and automatic
reconnection after restarting only the cloud VPN service. Both LAN endpoints
returned HTTP 401 anonymously before and after recovery; direct backend ports
timed out, and the workstation default route remained unchanged. The actual
legacy gateway override and encrypted post-change backup were verified; see
[`LAN access`](lan-ui.md) and [`plan.md`](../../plan.md) for exact evidence.

Fresh `just usenet-test` passed 224 tests with seven opt-in skips, compilation,
ShellCheck, JSON/YAML, three Ansible syntax checks and secret scanning. The seven
proxy runtime cases had passed separately during implementation. Root `just test`
passed Talos 118 tests, grid 102, printer 225 including browser checks, snapshot
7, tinyurl 16, Sonos tests/builds and all seven add-on container checks. Independent
security review found no concrete commit blocker. Master-key clean-clone recovery
remains the next phase, not a capability established by these tests.

## Remaining handoff data

The required end-to-end flow, actual NAS access/bootstrap, both configuration
restore-startup drills, and final validation are recorded above. The remaining
required check is the external dashboard reachability probe. Automatic approval
review rejected the probe, and explicit user approval is still pending. The
verified private listener and anonymous-access denials do not establish that
WAN forwarding is absent.

The following operating details remain explicit:

- Eweka's final charged tier/renewal, NZBFinder's charge currency/expiry/renewal,
  and NZBGeek's unpublished daily quotas/automatic rebilling remain unverified.
  The verified Hetzner subtotal is $23.09/month and NZBGeek adds $1/month
  equivalent from its paid $12 annual term; see [costs](costs.md) for quotes
  and the unconfirmed portions of the total.
- Backups are manual. Both live captures and isolated startup drills passed;
  rerun capture after configuration changes. The September 11 clean-clone drill
  subsequently verified recovery of both legacy backup identities from the
  master-encrypted vault; the operator holds the master in 1Password and on paper.
- The authorized fixture demonstrated the workflow and preserved hashes.
  Representative large-file throughput, sustained NAS load, and tuning limits
  have not been benchmarked. The observed fixture timings are not a benchmark.

The user-authorized global automatic-search/RSS update passed all 398 Usenet
tests (390 passed, eight opt-in skips). Live policy readback verified both apps
with two enabled search/RSS indexers and a 15-minute interval. Supplemental
snapshot `20260911T210232Z-ae56b33b7f0488c7` passed encrypted NAS round-trip
verification. Automatic importing remains disabled.
