# Household identity rollout

The accepted design uses an AD-compatible Samba directory on Home Assistant for SMB
credentials and Authelia on Home Assistant for browser sign-in. Migration order
is QNAP, Forgejo, Arr, then the remaining hosted services. Existing local
administrators, service identities, SSH keys and application ownership remain
available during each cutover.

## How sign-in works

| Request | Authentication path | Authorization boundary |
| --- | --- | --- |
| SMB shares | Client → QNAP domain member → Samba AD on HA | QNAP share grants for AD groups; existing local recovery grants retained |
| Forgejo browser | Client → HTTPS Forgejo → Authelia OIDC → LDAPS AD + OTP | `git-users`, explicit link to existing `ryan` account; Forgejo keeps repository permissions |
| Arr browser | Client → HA Caddy → Authelia forward-auth → VPN cloud gateway → app | `arr-users` + OTP on every route, then an HA-only gateway credential |
| App-to-app calls | Existing internal routes and application API keys | Application API authorization; browser cookies are not service credentials |
| Git SSH | Existing Forgejo SSH listener and public keys | Forgejo repository grants; OIDC does not replace SSH keys |

Authelia runs on HA loopback; AD runs in a separate app network namespace.
The directory-route app exposes the existing `.10` LAN address and waits for
LDAPS before Authelia starts. A failure of the HA host affects both new domain
logins and browser SSO. QNAP local recovery administration remains available.
Neither the private directory nor browser services require inbound Internet ports.
Public DNS supplies only ACME validation; LAN DNS supplies the service addresses.

## Names and certificate trust

Keep `.home.arpa` for LAN discovery, the AD realm and existing aliases. The
directory is `dc1.ad.home.arpa` at `192.168.1.10`; the realm is `AD.HOME.ARPA`
and the NetBIOS domain is `SMARTHOME`.

Browser HTTPS uses `*.home.rytim.com` and Let's Encrypt DNS-01 validation.
`home-acme` runs on HA, uses a DNS-only DreamHost API key and tests staging
issuance before production. It has no listening ports. Certificate and account
keys persist in the add-on's `/data`; the credential persists in its `/config`.
Production publication verifies public trust, hostname, expiry and key matching
before atomically replacing the `current` certificate directory. Renewal runs
twice daily with jitter, retains keys, and leaves the previous publication intact
on failure. The client uses ACME renewal information and its normal due-date
checks; a successful check does not necessarily issue a replacement certificate.
Propagation checks use both Quad9 recursive resolvers on their supported port
9953, because the gateway intercepts ordinary port-53 traffic. Direct
authoritative checks through that intercepted path are disabled; recursive
propagation checks, ACME validation and public-chain verification remain active.

No new root certificate is required on client devices. The private CA is for
server-to-server LDAPS only, explicitly trusted by Authelia. Its signing keys
stay outside the repository and off both servers. HTTP `.home.arpa` aliases can
redirect to the public-certificate names after each service migrates. Publicly
trusted HTTPS cannot be issued for `.home.arpa` itself.

## Rollout checkpoint — October 24, 2026

* The initial AD container ran on its own QNET address. LDAPS, rejection
  of bad passwords and cleartext binds, Kerberos, and Kerberos SMB passed.
  QNAP's native SMB maintenance uses host-wide process termination, which also
  kills containerized Samba. Migration to a kernel-isolated Virtualization
  Station VM was attempted before the HA hosting decision.
  The abandoned trial guest had one CPU, 768 MiB
  RAM and an 8 GiB virtual disk. Preparation uses DHCP and masks Samba services;
  no directory state has been copied into it. The trial has not passed the
  capacity gate: the 4 GB, two-core NAS showed sustained load around 20–27,
  paging and SSH timeouts during startup. Do not cut over on this evidence.
  HA has 32 GB RAM and approximately 27 GiB available. Moving AD there is now
  approved. On October 24, the user approved removal of this unused trial VM,
  its disk/folder and Virtualization Station. The VM and trial files were deleted
  after confirming it was the only VM, powered off, with autostart disabled.
  QNAP App Center confirmed Virtualization Station was uninstalled.
  Remaining installer/seed images were checksum-verified against the preserved
  originals and removed with their empty directories. QNAP domain trust, live AD
  verification and encrypted SMB3 share/denial tests passed after uninstall.
  Original operator and host keys remain in encrypted recovery; the HA directory
  still uses those identities, despite their historical `vm/` filenames.
  The HA directory app now runs in its own network namespace. A
  separate routing app retains the directory's LAN address without changing
  HA's DHCP address or conflicting with AdGuard's host-wide DNS listeners.
  Historical repair seeds and original keys remain in controller recovery;
  VM preparation/start commands now refuse use after HA cutover. Never run two
  copies with the same directory identity and address.
* The HA cutover passed: exact cold-copy file hashes, domain and every account's
  SID/GUID, password material and memberships matched. SYSVOL file hashes and
  Windows permissions matched after rebinding the inode-based ACL database.
  The original SSH host/operator and LDAPS keys were retained. HA passed an
  offline Samba restore before activation, then live LDAPS, bad-password and
  cleartext-bind denial, both household Kerberos logins, Kerberos SYSVOL access,
  database checks, UDP/TCP DNS, QNAP machine trust and Authelia HTTPS health.
  The NAS container is stopped with restart disabled and a cutover guard. Its
  original state and an independently decrypted encrypted cold copy remain.
  A native HA cold backup containing all four identity apps was also encrypted
  and decrypted independently. Its directory data was restored into a separate
  HA directory with new inodes; account identities/password material, SYSVOL
  contents and ACLs, and database checks passed. No restored listener was
  started. The disposable restore directories were removed after verification.
* Both AdGuards forward only `ad.home.arpa` to the directory. Other household
  names and independent public upstreams remain intact; gateway, UDP and TCP
  checks passed. The ordinary DNS services were not stopped.
* SYSVOL uses Samba's database-backed extended attributes, avoiding extra host
  capabilities. Fresh provisioning, repeat provisioning and permission checks
  passed. The guarded initialization repair preserves the newly created domain
  and account identities.
* QNAP joined `SMARTHOME`; native winbind verified the domain trust. Its DNS
  proxy uses the directory first and HA's resolver second. Existing local
  accounts and share grants remain. Approved domain share grants are applied:
  both household users have FromDrobo read/write and Public read-only; Ryan has
  Multimedia read-only and SpaceBlackTimeMachine read/write; Michael has
  Multimedia read/write and no Time Machine access. Actual encrypted SMB3
  create/read/write/delete and denial checks passed using synthetic files,
  which were removed afterward. Container and Usenet remain denied to both;
  the LDAP service account was denied all six shares. No recursive ACL changes
  were applied. Native domain trust passed again after all share changes, and a
  post-grant QTS settings backup was encrypted and independently decrypted.
  Its pre-join configuration has an encrypted, decrypt-verified rollback copy.
  The AD restore drill passed, including the restored database, SYSVOL ACLs,
  domain/account SIDs, human group memberships, household passwords and QNAP's
  member-machine trust secret. The resulting encrypted
  archive is retained off-NAS in the controller recovery directory.
  During Virtualization Station installation, trust and LDAPS checks timed out.
  Both subsequently passed again without changing credentials; continue to
  verify actual authenticated operations rather than relying on DNS health alone.
* Authelia is running at `https://auth.home.rytim.com`, with publicly trusted
  HTTPS and verified LDAPS. Its old HTTP aliases redirect there. It retries
  startup after directory outages, preserving its configuration and keys.
  Ryan and Michael's AD accounts exist; Ryan confirmed first-factor sign-in.
  Gmail SMTP is configured with required TLS, certificate verification and
  startup checks; Authelia restarted successfully. Ryan confirmed receipt of
  the enrollment email and completed OTP enrollment. Forgejo account linking
  and a fresh OIDC sign-out/sign-in cycle subsequently passed.
  Ryan belongs to the Git and Arr access groups. Michael has NAS groups only.
  Both initial credentials passed LDAPS and Kerberos authentication, with exact
  approved group memberships. The private 1Password import is
  `identity-private/household-logins.1password.csv` beneath controller state.
  Temporary HA bootstrap files were removed after verifying their exact bytes
  in a decrypt-checked HA backup. Authelia and ACME then restarted successfully
  from persistent configuration; the HTTPS health check passed.
* The DreamHost DNS-only key is stored externally, and the HA ACME service is
  running. Staging and production issuance passed; the public wildcard expires
  January 22, 2027. Browser trust, public-chain validation and OIDC discovery
  passed without installing a client root CA.
* The gateway forwards `home.rytim.com` to both existing LAN resolvers. The exact
  `auth.home.rytim.com` record passed the paired transaction's UDP/TCP checks
  through both resolvers and the gateway. Public DNS has no private service A
  records; DNS-01 challenge records remain public.
* Forgejo HTTPS at `https://git.home.rytim.com` passed public certificate and
  login-page checks. Its exact private DNS alias passed the paired resolver and
  gateway transaction. The canonical HTTPS URL is deployed, and the old HTTP
  alias returns a verified 308 redirect;
  OIDC account linking and a fresh sign-out/sign-in cycle passed. The existing
  administrator remains user ID 1 with its original repository and SSH key.
  A post-link backup passed off-host download, SQLite integrity and Git-object
  verification; its restored database contains one explicit OIDC link to ID 1.
  Forgejo retains local recovery login. Arr's proxy and application changes are
  deployed as described below; browser acceptance remains pending.
* The full clean-checkout deployment exposed a startup race between Authelia
  and the directory route. Authelia now depends on the route, whose health check
  requires the production virtual address to answer LDAPS. The runtime retry
  loop remains enabled for HA boot ordering and temporary directory outages.
  Recreated directory containers also restore their own resolver to Samba on
  loopback, so AD hostname and Kerberos discovery survive Docker's regenerated
  resolver file. The HA host and other apps retain their existing DNS settings.
* The disposable checkout at `067930c` passed `git clean -dfx && just deploy`,
  followed by directory, household login, SMB permission and QNAP trust checks.
  All 66 selected credential files remained byte-identical. Its independent
  native HA backup restore retained the original Authelia configuration and
  one OTP enrollment. The backup writer now creates its output directory when
  running from freshly restored controller state.

## Arr browser gateway

The Arr migration uses `radarr`, `sonarr`, `prowlarr` and `sabnzbd` beneath
`home.rytim.com`. Caddy checks Authelia locally before forwarding any request,
including API and WebSocket paths. The `arr-users` group requires two factors;
missing authorization or an unavailable identity service fails closed.
Legacy `.home.arpa` browser routes redirect to these HTTPS names.

HA authenticates to the existing VPN-only cloud gateway using a dedicated
random service credential. The cloud checks both its Argon2id hash and HA's
actual source IP; forwarded headers cannot satisfy that restriction. Existing
numeric-address recovery credentials remain valid. The cloud gateway strips
authentication and identity headers before the application. No new listeners
or VPN routes are needed. Existing app-to-app API keys stay unchanged.

`just usenet identity arr-gateway` creates this credential once in external
controller state and stages the exact bytes into HA's protected SSL directory.
It refuses to replace an existing credential. The encrypted native HA backup
includes that directory and verifies the gateway credential when configured.
`just usenet configure-cloud-sso` updates only the cloud gateway. Live Arr
acceptance is recorded separately after browser sign-in and API checks.

The deployed gate passed public TLS validation and anonymous denial for all
four apps, including API paths. HA's machine credential reached the existing
cloud gateway from its actual LAN address. Prowlarr's scoped restart retained
the original API key and every setting except `AuthenticationMethod`; its
original configuration remains in a protected recovery directory. Cloud health
checks passed with the same pre-existing SAB warnings and retired-worker holds.
The full repository suite passed, alongside 14 isolated cloud-gateway tests and
three home-proxy authorization tests. The infrastructure unit suite completed
550 tests with 12 runtime checks skipped; its final history scan still reports
the previously documented findings.
Current source/index scanning passed separately. A new encrypted identity seal
was restored into a disposable directory: all 58 files were identical, including
the gateway credential and original CA material; the plaintext restore was removed.
Authenticated Arr browser acceptance remains unverified. The user subsequently
asked to continue without Mac interaction; this is permission to proceed, not
evidence of a successful authenticated browser check.

When restoring an older native HA backup, run `just usenet identity arr-gateway`
after restoring the controller identity seal. This reinstalls the same gateway
credential into SSL state without replacing the cloud credential or any user key.

## Remaining service assessment

| Service | Current authentication | Next integration boundary |
| --- | --- | --- |
| QNAP SMB | Verified AD accounts and preserved local recovery accounts | Keep the native domain join and share groups; browser proxy authentication cannot authenticate SMB. |
| QNAP administration | Existing local administrator; domain membership is active | Preserve emergency administration independently of the browser identity service. |
| Catalog / OliveTin | Local operator login, with explicit action ACLs | Evaluate its native OAuth2 user-info mapping against the installed version; retain the existing operator permissions and recovery login. |
| Jellyfin / Moonfin | Jellyfin 12.3.0; existing `ryan` administrator uses its local provider; no auth plugin installed | Verify plugin compatibility and explicit linkage to the existing profile before enabling AD or OIDC. Preserve profile identity, library grants and native clients. |
| Plex and Seerr | Native Plex login plus the explicitly approved dedicated Moonfin request account | Preserve those client and API flows; do not put browser redirects in front of native playback or the request integration. |
| HA administration and community add-ons | Existing HA authentication and ingress | Keep HA ingress as the authenticated boundary pending a separate supported integration. |

[Jellyfin's official LDAP plugin](https://jellyfin.org/docs/general/server/plugins/#ldap)
supports directory authentication and configurable username mapping. Its native
client compatibility makes it worth evaluating before a browser-only SSO change.
The [Authelia Jellyfin guide](https://www.authelia.com/integration/openid-connect/clients/jellyfin/)
documents a separate SSO plugin, with an older tested server version than this
installation. [OliveTin's OAuth2 configuration](https://docs.olivetin.app/security/oauth2.html)
provides username and group mapping; verify the deployed implementation before
granting any catalog action through it. These are assessment findings, not
completed migrations.

## Upstream practice review — October 24, 2026

The design was checked against project-maintained guidance, rather than treating
forum examples as a security specification. This is a configuration review and
targeted runtime validation, not a penetration test or vendor certification.

| Area | Guidance and current assessment |
| --- | --- |
| AD and SMB | [Ubuntu's Samba AD guide](https://ubuntu.com/server/docs/how-to/samba/provision-samba-ad-controller/) separates directory and file-server roles. QNAP is the member file server; the HA Samba app is the DC. Reusing QNAP's own Samba process namespace proved unsafe and was abandoned. |
| LDAP | [Authelia's AD integration](https://www.authelia.com/integration/ldap/activedirectory/) uses LDAPS. The deployment verifies the private CA and server name, uses a dedicated bind account and rejects cleartext binds. Password reset/change are disabled, so the bind account needs no password-write delegation. |
| Browser proxy | [Authelia's Caddy guide](https://www.authelia.com/integration/proxies/caddy/#trusted-proxies-and-integration-security) supports native forward-auth and warns against trusting whole client subnets as proxies. Our LAN is a client allowlist, not a trusted-proxy list. Spoofed identity headers are stripped; unauthenticated API/WebSocket paths and failed auth services cannot reach Arr. |
| Git SSO | [Authelia's Forgejo guide](https://www.authelia.com/integration/openid-connect/clients/forgejo/) supports OIDC. Existing-account linkage, a confidential client, exact callback, group policy and OTP preserve Forgejo ownership. Native Git SSH and local recovery login remain independent. |
| Public certificates on private services | [Let's Encrypt DNS-01 guidance](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge) supports wildcard certificates without publicly exposing the web servers. DNS permissions are limited to list/add/remove; renewal runs in a separate app rather than the web proxy. |
| Git secrets | [SOPS documentation](https://getsops.io/docs/) supports age-encrypted Git files. The master stays outside Git and outside its payload; the new vault has authenticated decrypt, restore/readback, wrong-key and tamper tests. Historical ciphertext is retained. |

Remaining improvements are explicit:

* **Directory availability:** AD and Authelia share one HA host. A second DC on a
  separate always-on machine would remove that single host failure for directory
  login; a second browser identity/proxy instance would be a separate project.
  The underpowered NAS VM is not a suitable redundancy solution. Keep off-host
  native backups and local emergency access; a snapshot alone is not replication.
* **DNS credential scope:** DreamHost's DNS-only key still controls DNS across
  the account. Let's Encrypt recommends narrower credentials or challenge
  delegation. A dedicated `_acme-challenge.home.rytim.com` zone/provider with a
  zone-scoped token would reduce the impact of compromise. No delegation/provider
  change was made as part of this review.
* **Backup scheduling:** the successful identity restore drills are point-in-time
  evidence. Do not assume that existing NAS/cloud schedules include the new HA
  identity apps, SSL files or private controller CA. Include them explicitly in
  a recurring off-host policy and test renewal/restore after credential changes.
* **Emergency browser access:** legacy numeric HTTP recovery endpoints retain
  existing authentication but do not gain browser TLS from this rollout. Use a
  trusted management network or pinned SSH tunnel; prefer canonical HTTPS for
  ordinary sign-in. Do not disable recovery access before testing its replacement.
* **Acceptance and clients:** Arr's authenticated browser check is still pending.
  Jellyfin, Plex/Seerr and HA require their native-client/authentication behavior
  to be preserved; an indiscriminate browser redirect gate is not appropriate.

## Recovery and operations

### Git-tracked SOPS credential escrow

`identity-infra/credentials.sops.json` is the current, separate SOPS vault.
It encrypts the entire payload, including paths and checksums. Its public
recipient is in `identity-infra/.sops.yaml`; its existing private age identity is
`~/.config/smarthome/recovery.agekey`, outside the checkout and payload.
The historical `usenet-infra/vault/secrets.sops.json` and its older master remain
unchanged. Keep both recovery identities in 1Password; they are not interchangeable.

Coverage includes DreamHost DNS and Gmail SMTP credentials, all Authelia secrets
and OIDC signing/client keys, AD bootstrap/user credentials, private CA and LDAP
keys, original HA/directory/deployment/signing SSH identities, current controller
inventory/environment inputs, existing service operator credentials and four
live Arr/downloader API keys. Preserved ACME account/certificate keys and Forgejo
server secrets were additionally escrowed from the independently verified native
HA and post-link Forgejo backups. Those server exports are dated snapshots;
refresh them from a verified backup after server-side credential rotation.
The October 24 capture and independent filesystem restore verified 89 files
byte-for-byte; wrong-key, modified-ciphertext and unsafe-path tests also passed.

```sh
just --no-dotenv usenet-crypto-bootstrap
just usenet identity escrow-app-keys
just credentials capture
just credentials verify
just credentials restore --destination /absolute/new-credential-restore
```

On a fresh checkout, run the bootstrap and restore commands; the app-key escrow
command is for an already configured controller with live cloud access.

Capture never rotates keys. Verification decrypts with an isolated SOPS process,
authenticates its MAC, compares current source bytes, restores into a new private
directory and reads every file back. Restore refuses existing destinations,
unsafe paths, symlinks, checksum mismatches and wrong keys. The result separates
`tree/` controller files from `pki/`; reconcile selected files into the external
controller state and `~/.config/smarthome/pki` only after reviewing the recovery
target. No automatic overwrite or deployment occurs. Use
`SMARTHOME_RECOVERY_KEY` for a key retrieved independently from 1Password.

After a credential change, refresh its escrow, run capture/verify, review the
ciphertext-only diff and commit it. A `git clean` removes untracked source work,
so the vault and helpers must be tracked. The current-source scanner accepts only
this exact SOPS path with an encrypted payload and valid age metadata; plaintext
or renamed copies fail its checks.

SOPS protects credentials in Git. It does not make running application files
encrypted, nor replace native database backups. AD databases/SIDs/password
hashes, Authelia OTP enrollment, Forgejo repositories/account links and ACME
runtime state still require their consistent native backups. The age workstation
archive additionally preserves operational state excluded from this small vault.

Controller private state is under
`~/.local/share/smarthome/tree/build/identity-private`; CA signing material is
under `~/.config/smarthome/pki`. The existing encrypted-checkout recovery master
is `~/.config/smarthome/recovery.agekey`. Store its complete contents as a
1Password Document and retain the encrypted archives separately. Never commit
these paths' contents or paste credentials into chat or command arguments.
Certificate renewal refuses missing established CA or leaf-key material;
restore the identity seal before renewal instead of creating replacement keys.

Directory state lives in the HA `directory` app's persistent `/data`, outside
the checkout. The stopped NAS copy remains at
`/share/Container/home-identity/dc-state`; do not restart it. The controller's
`ha-cutover.json` selects HA for verification and backups. The NAS-side cutover
guard makes `just usenet identity deploy` refuse the retired container.
Use `just deploy directory` and `just deploy directory-route` for HA app updates.
Startup refuses to reprovision existing or incomplete state.
Restoration uses the preserved cold state or a Samba domain backup, never a new
domain with the same name. Cold HA backup shutdown saves portable SYSVOL ACLs;
startup rebinds them if a restore changes filesystem identity, after checking
account identities and file content. Missing or mismatched evidence fails closed.

Useful commands from the repository root:

```sh
just usenet identity status
just usenet identity verify
just usenet identity backup
just usenet identity backup-ha
just usenet identity verify-authelia-backup
just usenet identity ha-native-restore-trial
just usenet identity seal
just usenet identity inventory
```

`backup` creates a consistent Samba backup, restores it in a separate directory,
checks the database and SYSVOL permissions, and compares domain/account SIDs and
password material. It does not start the restored server. Only a passing result
is exported as a decrypt-verified age archive off the NAS. This is a directory
restore check, not a complete replacement-NAS or replacement-HA drill.

`seal` captures private identity configuration and CA material into the existing
external encrypted recovery store and verifies decryption. HA also needs cold
backups of directory, directory-route, Authelia and home-acme, including their persistent configuration and
data. Authelia's database contains MFA enrollments and must retain its original
storage encryption key. A controller bootstrap snapshot alone does not contain
later HA database changes or ACME account state.
The post-enrollment Authelia backup independently restored with SQLite integrity
passing, one enrolled TOTP record, and identical configuration including the
original storage/session/OIDC keys. The disposable plaintext restore was removed.

For internal LDAPS leaf renewal, `just usenet identity pki` reissues a certificate
within thirty days of expiry using the existing leaf key. Install the renewed
leaf through the pinned HA directory maintenance connection, preserving the
existing key and CA, then restart only the directory app and run
`just usenet identity verify`. Seal the updated recovery material. The old NAS
deployment command is blocked after migration. This remains an operator-run procedure;
public web certificate renewal is handled by the HA ACME service.

## Migration acceptance

QNAP migration must preserve local emergency administration and service users.
Record existing share access before adding equivalent domain access. In
particular, ordinary users must not gain Container/Usenet access, and Time
Machine access must retain its existing per-user scope. Do not recursively
rewrite ownership or ACLs on stored files. Verify permitted and denied SMB
operations using synthetic disposable files.

Forgejo must link the existing account to OIDC without replacing its user ID,
repositories or SSH keys. Keep registration closed and verify Git over SSH and
authenticated HTTPS. Arr migration must protect browser paths while preserving
authenticated service API integrations; a blanket `/api` bypass is not acceptable.

Authelia initially uses a private filesystem notifier for bootstrap enrollment;
that mode does not send email. Gmail SMTP with an app password is the approved
delivery method. Run `just usenet identity gmail-smtp` interactively to enter the
sending address and hidden app password. The helper verifies Gmail over TLS
without sending mail, then stores mode-0600 credentials outside the checkout.
Render and stage Authelia configuration, restart only that app, and check its
startup SMTP validation before asking the user to retry enrollment. Rendering
refuses to fall back to file notifications if an existing SMTP credential is
missing. Preserve the original session/storage/OIDC keys and MFA database.
Seal the credential and take a fresh native backup after enrollment. A valid
SMTP connection and actual receipt of enrollment email are separate checks;
human MFA enrollment remains required before browser SSO is complete.
