# Account setup and credential record

Research was refreshed against operator documentation on 2026-09-10. Create
accounts in the order below, one checkpoint at a time. Never paste a password,
API token, recovery code, or private key into chat or Git.

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

The default remains [Eweka](https://www.eweka.nl/en/pricing). The current offer
is €104.85 prepaid every 15 months, equivalent to €6.99/month at checkout. It
includes unlimited data/speed, 50 connections, TLS, and more than 6,597 days of
growing retention. The displayed checkout repeats every 15 months; the terms
allow future price changes with renewal notice, so record the actual renewal
line and date from the final order page.

After purchase, store the username/password only in SABnzbd's protected runtime
configuration. Configure:

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

Twenty connections is a deliberate starting point; SABnzbd recommends roughly
8–30 for most servers. Do not use plaintext NNTP.

## 3. Fill block

[UsenetExpress](https://www.usenetexpress.com/plans/) currently lists a 500 GB
block for $20, 50 allowed connections, TLS 1.2, and operator-owned US/EU farms.
That is a useful alternative path to Eweka. The public checkout does not clearly
promise that today's ordinary block is non-expiring and non-recurring. Before
buying, verify those two properties on the final order screen or with support.

If confirmed, configure it in SABnzbd as a fill server:

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

Set a quota warning around 375 GB. Lower priority plus `Optional` ensures the
block is asked only for articles the primary lacks and is not drained merely
because Eweka is temporarily unavailable.

## 4. Indexers

Start with exactly two Newznab-compatible indexers. No invite bypasses or traded
credentials are acceptable.

- [NZBGeek registration](https://nzbgeek.info/register.php) is open. Pricing,
  API limits, key location, and renewal behavior are currently login-gated.
  Provisional public reporting says $12/year, but buy one year only after the
  authenticated checkout confirms the actual price and limits. API base:
  `https://api.nzbgeek.info/api`.
- [DrunkenSlug registration](https://drunkenslug.com/register) currently says
  the bar is closed. Do not seek an invitation workaround.
- Use [NZBFinder](https://nzbfinder.ws/register) as the second indexer; signup is
  open and the service supports Newznab/Prowlarr. Its tier table is also
  login-gated. Record the exact annual charge, daily API/NZB limits, API-key
  location, and renewal behavior before payment. API base:
  `https://nzbfinder.ws/api`.

Indexer API keys live only in Prowlarr's protected application state. In
`docs/costs.md`, replace the pending values only after seeing the authenticated
checkout pages.

## Credential locations

| Credential | Location | Git policy |
|---|---|---|
| Hetzner Cloud token | ignored mode-0600 `usenet-infra/secrets/hetzner.env` | never committed |
| Terraform Storage Box passwords | encrypted/restricted Terraform state | never committed |
| VM admin key | operator SSH directory | private key never committed |
| Storage writer key | `/srv/usenet/secrets/storagebox/` | never committed |
| QNAP reader key | `/share/Container/usenet/secrets/storagebox/` | never committed |
| Usenet credentials | SABnzbd config backup | never committed |
| Indexer API keys | Prowlarr config/database backup | never committed |
| App API keys | Generated by each app and synchronized locally into `/srv/usenet/config/catalog.env` by Ansible | never committed or printed |

The repository intentionally uses ignored, permission-restricted runtime files
instead of keeping deployable secrets beside source. Application configuration
backups must be encrypted before leaving the hosts.
