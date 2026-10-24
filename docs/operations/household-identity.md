# Household identity rollout

The accepted design uses an AD-compatible Samba directory on Home Assistant for SMB
credentials and Authelia on Home Assistant for browser sign-in. Migration order
is QNAP, Forgejo, Arr, then the remaining hosted services. Existing local
administrators, service identities, SSH keys and application ownership remain
available during each cutover.

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
  Virtualization Station is installed; the trial guest has one CPU, 768 MiB
  RAM and an 8 GiB virtual disk. Preparation uses DHCP and masks Samba services;
  no directory state has been copied into it. The trial has not passed the
  capacity gate: the 4 GB, two-core NAS showed sustained load around 20–27,
  paging and SSH timeouts during startup. Do not cut over on this evidence.
  HA has 32 GB RAM and approximately 27 GiB available. Moving AD there is now
  approved. The trial VM's memory is saved and it is shut off, with autostart
  disabled. Its disk and original keys remain intact.
  The HA directory app now runs in its own network namespace. A
  separate routing app retains the directory's LAN address without changing
  HA's DHCP address or conflicting with AdGuard's host-wide DNS listeners.
  An interrupted first boot created the guest administrator without installing
  its SSH key. A separate repair seed reruns cloud-init with the original keys;
  it preserves the first seed and refuses use after directory migration.
  Guest disk integrity checks passed. Its dedicated SSH host and operator keys
  are preserved in encrypted controller recovery. Never run both copies with
  the same directory identity and address.
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
  and an end-to-end OIDC sign-in remain separate acceptance steps.
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
  Forgejo retains local recovery login. Arr still uses its existing authentication.
* The full clean-checkout deployment exposed a startup race between Authelia
  and the directory route. Authelia now depends on the route, whose health check
  requires the production virtual address to answer LDAPS. The runtime retry
  loop remains enabled for HA boot ordering and temporary directory outages.
  Recreated directory containers also restore their own resolver to Samba on
  loopback, so AD hostname and Kerberos discovery survive Docker's regenerated
  resolver file. The HA host and other apps retain their existing DNS settings.

## Recovery and operations

Controller private state is under
`~/.local/share/smarthome/tree/build/identity-private`; CA signing material is
under `~/.config/smarthome/pki`. The existing encrypted-checkout recovery master
is `~/.config/smarthome/recovery.agekey`. Store its complete contents as a
1Password Document and retain the encrypted archives separately. Never commit
these paths' contents or paste credentials into chat or command arguments.

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
