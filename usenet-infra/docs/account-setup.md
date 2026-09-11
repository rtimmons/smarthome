# Account setup and credential record

Research was refreshed against operator documentation on 2026-09-10. Create
accounts in the order below, one checkpoint at a time. Never paste a password,
API token, recovery code, or private key into chat or Git.

Eweka is the sole provider for the current baseline. The user deferred
UsenetExpress until genuine missing articles or a completion gap demonstrates
a need for fill. NZBGeek is paid, active, and connected in Prowlarr.
NZBFinder Pro is also paid and connected. Both indexers passed their live
credentialed tests. The QNAP local web address is supplied, and the user created
its enabled `usenet-deploy` account. Dedicated public-key SSH now succeeds,
with the exact NAS host key pinned under user-authorized first-use trust;
runtime/share discovery is complete. The new Usenet share, application path,
and private dashboard login are configured. Live dashboard download, browser
reconnection, and local eviction passed, as did CLI parity, restart persistence,
and cloud/NAS isolated configuration restoration. External reachability remains
unverified pending approval.
No fill-provider purchase or
clarification is pending.

| Account | Recorded status on 2026-09-10 |
| --- | --- |
| Hetzner project | Exists; protected CX43 and BX11 provisioned, no-change plans verified |
| Storage Box writer and QNAP reader | Configured; reader is server-enforced read-only and tested with a disposable sentinel |
| Eweka | Saved settings, authenticated connection test, and official 100 MB NNTP download/processing verified; charged tier and renewal details not independently verified |
| Cloud configuration backup | Refreshed after both indexers, Prowlarr application-key rotation, cloud catalog/health updates, and Direct Unpack restoration; 589 files and 2 SQLite databases verified locally; manual, with isolated startup of both pinned cloud apps and preserved config/database rows verified |
| UsenetExpress block | Deferred by the user; optional future fill only if missing articles or a completion gap warrants it |
| NZBGeek | User confirmed $12 USD paid for one year; independent account readback active through 2027-09-13 22:01:53 UTC; saved/enabled in Prowlarr and credentialed test passed with strict certificate validation |
| Prowlarr login | Forms authentication configured privately by the user |
| Prowlarr application API key | Rotated through supported ResetApiKey command; old key HTTP 401, new key HTTP 200, protected dependent environment synchronized; other XML settings unchanged, no restart |
| Prowlarr SABnzbd client | Exactly one enabled internal client; candidate, saved-credential, and standalone tests passed; second configure made no changes |
| NZBFinder | User confirmed Pro payment; authenticated Pro badge independently observed; saved/enabled in Prowlarr and live credentialed test passed with strict certificate validation; charge currency, expiry, and renewal details unverified |
| NAS deployment/dashboard login | TS-451D2/QTS 5.2.10.3577; dedicated-key SSH UID 1004/GID 100 and runtime versions verified. Host key uses authorized first-use trust. Usenet share/application path, inventory/env, 100 GiB cache reserve, and private Argon2id login configured; runtime/login, dashboard download/reconnection/eviction, and direct NAS reader write-denial passed at `http://192.168.1.66:1337` |

## 1. Hetzner account and project

Create or verify a [Hetzner account](https://accounts.hetzner.com/signUp), enable
2FA, and create a Cloud project dedicated to this system. In that project,
create a Read & Write API token for Terraform. Export it as `HCLOUD_TOKEN` only
in the operator shell or a local password-manager integration; do not place it
in a tfvars file.

From the repository root, store it without echo or shell-history exposure:

```sh
just usenet-store-hcloud-token
```

This writes `usenet-infra/secrets/hetzner.env` with mode `0600`; the entire
`secrets/` directory is ignored. Terraform invocations source that file only for
the current process and never print it.

The separate Terraform roots create the replaceable VM and a protected BX11
Storage Box. BX11 is the approved 1 TB starting tier; capacity later grows in
place through BX21 and BX31 to the eventual 20 TB BX41 target. Storage Box
resources gained first-party support in hcloud provider 1.68.0, so manual
Console ordering is no longer the default. Terraform state and saved plans
contain Storage Box passwords and must be treated as secrets. The initial
account-specific Hetzner subtotal is documented in [costs.md](costs.md).

For normal read-only reconciliation, use `just terraform-plan` in this directory
or `just usenet-terraform-plan` at the repository root. The wrapper loads the
stored token without printing it. An optional `TERRAFORM_BIN` in ignored `.env`
selects a controller-local executable when Terraform is not on `PATH`; the
current workstation uses the verified 1.16.2 binary under ignored `build/tools/`.
This controller setting does not change either protected infrastructure state.

Before the first apply, create separate Ed25519 keys with the idempotent helper:

```sh
just usenet-generate-ssh-keys
```

It creates ignored keypairs under `usenet-infra/secrets/ssh/` for:

- cloud administration;
- cloud-to-Storage-Box ingestion; and
- QNAP read-only Storage Box access; and
- administration of the dedicated QNAP account.

Keep private keys outside Git. The ingestion key belongs under
`/srv/usenet/secrets/storagebox/` on the VM. The QNAP key belongs beneath the
stable Container share selected during NAS bootstrap. Verify Storage Box host
keys independently against Hetzner's published/Console fingerprint before
creating either `known_hosts` file. Install `qnap-admin.pub` on the NAS for the
dedicated account; do not reuse the Storage Box `qnap-reader` key for NAS login.

## 2. Primary Usenet provider

The default remains [Eweka](https://www.eweka.nl/en/pricing). The
[15-month signup checkout](https://www.eweka.nl/en/checkout?p=15mo), rechecked
2026-09-10, displays €104.85 prepaid, equivalent to €6.99/month, billed every
15 months. It includes unlimited data/speed and 50 connections. The pricing
page advertises 6,597+ days of retention; the checkout currently lags at 6,595+.
The checkout does not separately guarantee an unchanged promotional renewal
price. The [terms](https://www.eweka.nl/en/terms-of-service) allow fee changes
with notice at renewal, so record the final charge, renewal amount and date
privately. The user has now confirmed that the Eweka account exists. The final
charged tier, amount and renewal details have not been independently verified;
the advertised offer above is not a receipt.

The user confirmed a successful SABnzbd connection after private credential
entry, Test Server, and Next. Independent readback now verifies every setting
below, including **Required**, and SABnzbd's built-in test passed using its
saved credentials. The settings update preserved those credentials; reapplying
it reported no changes. A separate VM check verified TLS 1.3, strict
certificate validation, and an NNTP 200 greeting. The official 100 MB test
download has now completed and passed verification and unpacking.
Store the username/password only in SABnzbd's protected runtime configuration.
Verified configuration:

| Setting | Value |
|---|---|
| Host | `news.eweka.nl` |
| Port | `563` |
| SSL/TLS | enabled, strict certificate verification |
| Connections | 20 initially |
| Priority | 0 |
| Required | yes |
| Optional | no |
| Retention | 0 (provider default) |

In [SABnzbd 5.1 server settings](https://sabnzbd.org/wiki/configuration/5.1/servers),
lower numeric priority is tried first. **Required** on Eweka pauses the queue
temporarily on connection failures, protecting a future fill block during a
primary outage. If a fill server is added later, **Optional** lets SABnzbd set
it aside after repeated connection problems; it does not provide the
primary-outage protection. Use **Strict** certificate verification and the
built-in server test before considering this setup complete.

Eweka's [TLS setup documentation](https://help.eweka.nl/kb/article/730-how-do-you-use-ssl-on-usenet/)
confirms this hostname with TLS on port 563 (443 is an encrypted alternative).
Twenty connections is a deliberate starting point, below the advertised limit;
tune only after a measured download. Do not use plaintext NNTP.

From the repository root, the bounded provider helper inspects the saved
Eweka server, applies the settings above while preserving credentials, or
repeats the built-in connection test:

```sh
just usenet-sab-provider inspect
just usenet-sab-provider configure
just usenet-sab-provider test
```

The helper uses the dedicated cloud SSH identity and prints only approved
status fields and credential-present booleans. It does not accept credentials
on the command line. From `usenet-infra/`, use `just sab-provider` with the
same subcommands.

SABnzbd's cloud storage settings have also been applied and read back live:
incomplete downloads use `/data/incomplete`, completed downloads use
`/data/complete`, and both free-space pause thresholds are `30G`. The default
category uses repair, unpack, and archive cleanup (`pp=3`) with no script.
Repair/unrar/7zip/PAR cleanup remain enabled; direct unpack, scripts, and
watched-folder scanning remain disabled. Queue and post-processing counts were
zero, with no enabled RSS feeds or custom workflows, when the settings were
applied. Inspect or reapply those bounded defaults from the repository root:

```sh
just usenet-sab-settings inspect
just usenet-sab-settings apply
```

A second live application returned empty change and remaining-drift lists.
Later, the official diagnostic autotest enabled Direct Unpack once. The
settings helper restored `direct_unpack=0`; readback matches the intended
settings and there were no active jobs. Six historical hostname-block warnings
and the one autotest notice were classified, with no authentication, provider,
or TLS failures.

The official 100 MB test completed through Eweka at normal priority, with
107,455,358 downloaded bytes and recognized successful verification/unpacking.
Its saved receipt records one submission. Check the existing result with
`just usenet-sab-smoke-test status`; `start` will not enqueue another job when
that receipt exists. The NZB metadata came from SABnzbd over HTTPS; the RAR/PAR2
payload used NNTP. The resulting two files were deliberately promoted as
`sabnzbd-official-100mb-2026-09-10`, with provenance and SHA-256 manifests;
remote byte verification found two matches and no differences. NAS dashboard
download/reconnection/eviction, CLI parity, restart persistence, and isolated
configuration restoration passed. External reachability remains unverified. See [validation](validation.md).

## 3. Indexers

NZBGeek and NZBFinder Pro are paid and connected in Prowlarr.
Start with exactly two Newznab-compatible indexers. No invite bypasses or traded
credentials are acceptable.

- [NZBGeek](https://nzbgeek.info/) is paid and active. The user confirmed a
  $12 USD one-year payment through the official Stripe checkout, and independent
  account readback confirms active status with expiry **2027-09-13 22:01:53 UTC**.
  This is $1/month equivalent, not monthly billing. The account's subscription
  guidance says renewal before expiry extends the existing period, expiry
  notices begin 30 days before expiry, and the API key stops working when the
  subscription expires. Automatic rebilling has not been independently
  confirmed; do not assume either automatic or manual-only billing.
  The saved key is managed under **My Account → API info → geek (api) key**.
  Private entry is complete: pinned Prowlarr 2.5.2.5491 now has NZBGeek saved
  and enabled, and its live credentialed test passed. Verified settings are
  host/base URL `https://api.nzbgeek.info`, API path `/api`, priority `25`,
  and global strict certificate validation enabled. Daily API and
  download quotas are unpublished/unverified in the inspected official pages.
  Query/grab quotas are therefore unset rather than guessed.
  The [public capability endpoint](https://api.nzbgeek.info/api?t=caps)
  advertises 100 results per request; that is pagination, not a daily quota.
  The [registration policy](https://nzbgeek.info/register.php?geek_policy=)
  identifies GeekHub as the subscription manager and states that payments
  are non-refundable.
- [DrunkenSlug registration](https://drunkenslug.com/register) currently says
  the bar is closed in the earlier signup check. The latest automated refresh
  returned HTTP 403, so availability has not been re-confirmed. Do not seek an
  invitation workaround; NZBFinder is already the selected and paid second indexer.
- [NZBFinder](https://nzbfinder.ws/) is the second indexer. The user confirmed
  signing in and paying for **Pro**, and the authenticated account's Pro badge
  was independently observed. Its plan display advertised **$30/year**,
  equivalent to **$2.50/month**, **20,000 API requests**, and **unlimited
  downloads**. The dollar currency code, final charged amount, subscription
  expiry, and renewal/automatic-billing terms have not been independently
  confirmed. The displayed price is not a receipt. The site says API and
  download counters reset 24 hours after each request; do not assume a fixed
  midnight reset. The service supports Newznab/Prowlarr at host/base
  `https://nzbfinder.ws` with API path `/api`. Its saved Prowlarr entry is
  enabled with priority `25`, strict certificate validation, and unset
  query/grab quotas. The live credentialed test passed. Its account key is
  managed under **My Profile**; private entry is complete. No new account,
  purchase, or key entry is needed.

Indexer API keys live only in Prowlarr's protected application state. In
`docs/costs.md`, both paid subscriptions are recorded, with NZBFinder's
unverified charge currency and renewal details left explicit.

The user configured Prowlarr's Forms login privately. Inspect or retest the
existing NZBGeek connection from the repository root:

```sh
just usenet-prowlarr-indexer inspect
just usenet-prowlarr-indexer test
```

The optional second argument chooses `nzbgeek` (the default) or `nzbfinder`.
Inspect or retest the saved NZBFinder connection:

```sh
just usenet-prowlarr-indexer inspect nzbfinder
just usenet-prowlarr-indexer enable nzbfinder
just usenet-prowlarr-indexer test nzbfinder
```

`just usenet-prowlarr-indexer enable` tests the saved credentials before
enabling, reads back the result, and repeats the saved test; an already enabled
indexer is left unchanged. Credentials stay on the VM. Both indexer connections
are complete. NZBGeek also passed a credentialed retest after the Prowlarr
application API-key rotation.

The internal SABnzbd download client is now configured and verified: exactly
one enabled client uses `sabnzbd:8080` over the private Docker network with
HTTP. Its `prowlarr` category uses repair/unpack/cleanup (`pp=3`), no script,
no separate directory, and normal inherited priority. Only the literal
`sabnzbd` was added to SABnzbd's existing host whitelist; every existing
entry and hostname checking were preserved. Candidate, saved-credential, and
standalone connection tests passed. The second configure reported
`changed=false`, `category_created=false`, and `hostname_added=false`.

```sh
just usenet-prowlarr-download-client inspect
just usenet-prowlarr-download-client configure
just usenet-prowlarr-download-client test
```

This helper uses credentials already stored on the VM. These connection checks
did not initiate acquisitions, searches, RSS grabs, or application automation.
The saved client test also passed after Prowlarr's application API key was
rotated through its supported `ResetApiKey` command. The old key returned
HTTP 401 and the new key HTTP 200; the private dependent environment was
synchronized with mode `0640` and its owner preserved. All other XML settings
were unchanged, with no application restart.

## Deferred fill-provider reference

This is retained research, not an account-setup step or acceptance blocker.
Revisit only if real missing articles or a completion gap warrants an
alternative provider. Recheck current pricing, non-expiration, and payment
terms at that time before deciding whether to buy.

On 2026-09-10, [UsenetExpress](https://www.usenetexpress.com/plans/) listed a
500 GB block for $20, 50 allowed connections, and TLS 1.2. Its
[FAQ](https://www.usenetexpress.com/faq/) describes its own spools plus
supplemental providers for older articles and confirms the US/EU endpoints.
This offers an alternative article path; it does not guarantee every article
uses wholly independent retention. The official
[selected-block checkout](https://members.usenetexpress.com/signup/9Jq5Pvyj/?product_id_page-0%5B%5D=9-13&ret=deep)
source identifies product `9-13` as a $20, non-recurring, one-time 500 GB
purchase. The selected checkout was also verified in a live browser at $20.00
with a one-time 500 GB purchase summary. Its JavaScript replaces the
uninitialized yearly-plan summary, so
the static page extractor's $90 yearly text is not the selected block's terms.
An [official July 2021 offer](https://www.usenetexpress.com/blog/post/20210701_4th_special/) described
the 500 GB block as non-expiring, but its old promotional price has expired and
the current checkout does not restate non-expiration. The current support page
and all 19 FAQ answers, including collapsed answers, also do not clarify it.
The generic renewal clauses do not resolve the block's expiration policy.
The user deferred this purchase; the unresolved expiration term does not
block the current Eweka-only baseline.

Unsent clarification retained for a future need; recheck contact details before
sending to
`sales@usenetexpress.com` or `support@usenetexpress.com`, both verified on the
[official contact page](https://www.usenetexpress.com/contact/):

> For your 500 GB block (previously listed as product 9-13), does unused data
> remain available until consumed, with no time or inactivity expiration?
> Please confirm the current price and whether there is any automatic recharge
> or recurring payment.

No support message has been sent and no purchase is recorded here.

If later needed and purchased after fresh checks, the starting fill settings are:

| Setting | Value |
|---|---|
| Host | `news-eu.usenetexpress.com` |
| Port | `563` |
| SSL/TLS | enabled, strict certificate verification |
| Connections | 8 initially |
| Priority | 10 |
| Required | no |
| Optional | yes |
| Retention | 0 |

Set a quota warning around 375 GB. Lower priority means the block is asked for
articles unavailable from higher-priority servers. Eweka's **Required** setting
protects the block during a primary connection outage; the block's **Optional**
setting allows its own transient failures to be skipped.

## Credential locations

| Credential | Location | Git policy |
|---|---|---|
| Hetzner Cloud token | ignored mode-0600 `usenet-infra/secrets/hetzner.env` | never committed |
| Terraform Storage Box passwords | encrypted/restricted Terraform state | never committed |
| VM admin key | ignored `usenet-infra/secrets/ssh/cloud-admin` | private key never committed |
| NAS admin key | ignored `usenet-infra/secrets/ssh/qnap-admin` on workstation only | private key never committed |
| Storage writer key | `/srv/usenet/secrets/storagebox/` | never committed |
| QNAP reader key | `/share/Container/usenet/secrets/storagebox/` | never committed |
| Usenet credentials | SABnzbd config backup | never committed |
| Indexer API keys | Prowlarr config/database backup | never committed |
| App API keys | Generated by each app and synchronized locally into `/srv/usenet/config/catalog.env` by Ansible | never committed or printed |
| Dashboard login material | ignored `usenet-infra/secrets/dashboard-auth.json` (Argon2id hash); copied to protected QNAP runtime and encrypted backup | never committed or printed |

The repository intentionally uses ignored, permission-restricted runtime files
instead of keeping deployable secrets beside source. Application configuration
backups must remain encrypted at rest and in transit. The cloud helper encrypts
on the VM; the QNAP helper streams through dedicated-key SSH directly into
local age without writing a plaintext archive.

The refreshed manual cloud configuration backup has been captured, encrypted on
the VM, transferred, and verified locally. It includes the application
credentials/configuration, writer identity, operational state/test receipt,
and remote catalog manifests; bulk content and controller/Terraform/QNAP
recovery material are outside its scope. Run `just usenet-backup-cloud` from
the repository root after each subsequent fill-provider or indexer setup.
The latest verified archive includes both indexer keys, the rotated Prowlarr
application key, login/client settings, restored Direct Unpack setting, and
current cloud catalog/health scripts. The older archives are preserved. The
latest filename and SHA-256 are recorded in [recovery](recovery.md).
Use `just usenet-backup-verify /absolute/path/to/archive.tar.age` to recheck an
archive; the isolated restore command is in [recovery](recovery.md).
The isolated cloud application-startup restore drill passed with saved
configuration and database rows preserved. The first live QNAP configuration
capture and isolated startup restore also passed, preserving authentication/session/history. Scheduling and an
independently verified decryption-key copy remain pending.
