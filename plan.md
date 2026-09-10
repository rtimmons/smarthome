You are my implementation agent. Starting from a cold state, guide me interactively through creating the required accounts and then build, configure, test, and document a reproducible Usenet acquisition and storage system.

Do not merely give me instructions. Perform everything you reasonably can using the tools available to you. Stop for me only when human interaction is actually necessary, such as payment, CAPTCHA, 2FA, entering a secret that you should not see, or making an irreversible purchasing decision.

Keep this document updated as agents make progress.

## Implementation progress

Last updated: 2026-09-10

- [x] Dedicated `usenet` branch and implementation plan created.
- [x] Cold-state repository review completed; implementation lives in `usenet-infra/`.
- [x] Fresh official-source research completed for Hetzner, Usenet providers/indexers,
      application versions, and QNAP/Container Station behavior.
- [x] Material architecture decisions confirmed; Hetzner account setup is ready to provision.
- [x] Reproducible Terraform, Ansible, Compose, catalog tooling, tests, and operational
      documentation scaffolded and locally validated where installed tooling permits.
- [x] Hetzner token stored and validated without exposing it; dedicated SSH keys and
      ignored mode-0600 Terraform inputs generated.
- [x] Live Terraform plans validated: cloud is 5 additions and storage is 2 additions,
      with no changes or destroys and no existing project servers.
- [x] Provision protected CX43 cloud infrastructure, BX11 Storage Box, and
      server-enforced read-only QNAP subaccount; post-apply plans show no drift.
- [x] Bootstrap and harden the cloud VM; deploy healthy loopback-only SABnzbd and
      Prowlarr containers; connect and verify Storage Box writer access.
- [x] Install the QNAP reader public key and prove with a disposable sentinel that
      the server-enforced read-only subaccount can read but cannot overwrite/delete.
- [ ] Provision Usenet provider/indexer accounts and complete their application setup.
- [ ] Reconnoiter and bootstrap the QNAP without disturbing existing services.
- [ ] Add and validate the authenticated, LAN-only catalog dashboard on the QNAP.
- [ ] Run the authorized end-to-end test and complete the handoff documentation.

Material decisions made:

- Use the now-supported first-party Terraform resources for the Storage Box and
  read-only subaccount, isolated in a protected state from the replaceable VM.
- Start with BX11 (1 TB) at $4/month, warn at 80%, and upgrade in place before
  90% utilization through BX21 (5 TB), BX31 (10 TB), or BX41 (20 TB).
- Start with the x86 CX43 (8 shared vCPU, 16 GB RAM, 160 GB NVMe); benchmark before
  paying for a much more expensive compute tier.
- Pin SABnzbd 5.1.3, Prowlarr 2.5.2.5491, and rclone 1.75.1.
- Keep Eweka as primary; retain UsenetExpress 500 GB as the proposed fill block only
  after its checkout confirms one-time/non-expiring terms.
- Use NZBGeek plus NZBFinder because DrunkenSlug registration is closed.
- Require deliberate manifest-backed promotion and server-enforced read-only QNAP
  credentials; no unattended acquisition path is enabled.
- Make a declaratively configured OliveTin dashboard the primary cache-management
  interface. Keep the existing catalog commands as its tested backend and as the
  recovery/automation interface; do not replace the safety semantics with raw file copies.
- Treat QNAP HybridMount as an optional compatibility experiment, not a dependency.
  Never weaken the server-enforced read-only credential to make HybridMount work.

Current checkpoint: the approved $23.09/month Hetzner infrastructure is live and
the cloud bootstrap is complete. One protected CX43 VM, protected Primary IPv4
and IPv6, one firewall, one SSH-key record, one protected BX11 Storage Box, and
one protected server-enforced read-only QNAP subaccount exist. Post-apply
Terraform plans report no changes. Live authenticated pricing for this account
is $18.49/month for CX43, $0.60/month for IPv4, and $4.00/month for BX11 in
Helsinki, with a $0 setup fee and 0% VAT reported.

The VM accepts only the dedicated non-root administrator key, denies direct root
and password login, and allows inbound SSH only from the currently approved
source CIDR. SABnzbd and Prowlarr are container-healthy on VM loopback only.
Ansible automatically reads their locally generated API keys into the protected
health environment without printing or returning them. Storage Box access,
catalog failure state, SABnzbd, and VM scratch checks pass. The health command's
only current failure is expected: Prowlarr reports that no indexers are enabled
because those accounts have not been purchased yet.

### Cold-agent resume checkpoint

Do not recreate, replace, or destroy the live Hetzner resources, and do not ask
the user to restate the already-stored Hetzner token or any generated key. Start
by reading this file and `usenet-infra/README.md`, then inspect the current Git
and ignored local state. `just usenet-terraform-plan` should remain no-change;
never apply a plan containing a destroy or replacement of the Storage Box.

The next and only immediate human action is the Eweka signup/payment. Ask the
user to create the verified 15-month Eweka unlimited offer: €104.85 prepaid
(€6.99/month effective), recurring every 15 months unless checkout shows changed
renewal terms, with 50 connections, TLS, and more than 6,597 days advertised
retention as researched on 2026-09-10. Have the user complete payment/CAPTCHA/2FA
privately and reply only that the account exists; never ask them to paste the
password into chat. No Usenet provider, block account, or indexer purchase has
yet been made.

After Eweka exists, continue the one-account-at-a-time flow in section 4 and
`usenet-infra/docs/account-setup.md`: configure Eweka in SABnzbd over TLS through
an SSH-tunneled UI, then confirm the UsenetExpress block checkout before buying,
then create/configure NZBGeek and NZBFinder in Prowlarr. Do not purchase anything
without the user's explicit approval at the checkout decision.

QNAP work is intentionally not started. An ignored dedicated `qnap-admin` keypair
has been generated, but its public key is not installed on the NAS. Before QNAP
reconnaissance, obtain from the user the exact dedicated Docker-capable
`user@LAN-host`, have the user install that public key through the supported QNAP
workflow, pin the verified NAS host key, and record the NAS data-share path and
numeric UID/GID. Do not use the Storage Box `qnap-reader` key as the NAS login key.
Do not reboot the QNAP. The QNAP implementation must include the OliveTin dashboard
described in sections 18-19; do not stop after making the fallback commands work.

Last verified on 2026-09-10:

- `just test` in `usenet-infra/` passes 10 unit tests, Python compilation,
  ShellCheck, JSON/YAML parsing, pinned Ansible syntax checking, and secret scan.
- The cloud Ansible play converges with `changed=0` and proves a fresh non-root
  SSH login before retaining SSH hardening; managed UFW rules are reconciled.
- The live read-only sentinel test allowed list/read, rejected overwrite/delete,
  preserved the SHA-256 hash, and the writer removed the disposable fixture.
- `just usenet-cloud-health` reaches all configured systems; its nonzero exit is
  expected only until at least one Prowlarr indexer is enabled.

## 1. Goal

Build this architecture:

```text
                         INTERNET

                     Usenet Provider
                           │
                       NNTP/TLS
                           │
                           ▼

                HETZNER CLOUD SERVER
               ┌─────────────────────┐
               │ SABnzbd             │
               │ Prowlarr            │
               │ local SSD scratch   │
               │ upload tooling      │
               └──────────┬──────────┘
                          │
                     rclone/SFTP
                          │
                          ▼

                HETZNER STORAGE BOX
                 ~20 TB canonical
                    content store
                          │
                     read-only
                    credentials
                          │
                          ▼

                       QNAP NAS
               ┌─────────────────────┐
               │ local selective     │
               │ content cache       │
               │                     │
               │ catalog dashboard   │
               │ browse/pull/evict   │
               │ verified CLI backend│
               └─────────────────────┘
```

Expected operating pattern:

- Approximately 20 TB maximum remote catalog.
- Approximately 1 TB/month transferred from Hetzner Storage Box to my NAS.
- The remote Storage Box is canonical.
- The QNAP contains only things I deliberately make local.
- Removing something from the QNAP must never delete it from the Storage Box.
- Acquisition and post-processing happen on the Hetzner VM, not the NAS.
- The QNAP should not need to be online for acquisition to continue.
- Normal cloud-to-NAS transfers should go directly Storage Box → QNAP rather than Storage Box → VM → QNAP.
- Day-to-day remote-versus-local decisions should be point-and-click; copying item
  IDs between terminal commands is a supported fallback, not the primary workflow.

This is a private system for content I am authorized to obtain and store.

## 2. Guiding principles

Optimize for:

1. Reproducibility.
2. Simplicity.
3. Declarative configuration.
4. Minimal externally exposed attack surface.
5. Easy disaster recovery.
6. Secrets never committed to Git.
7. Safe handling of the canonical remote copy.
8. Clear observability when something fails.
9. Avoiding unnecessary SaaS components.
10. Keeping recurring infrastructure cost near the previously estimated ~$75–90/month range unless there is a compelling reason otherwise.

Prefer:

- Terraform for Hetzner Cloud infrastructure.
- Ansible for Linux host provisioning.
- Docker Compose for application deployment.
- Docker Compose on QNAP wherever practical.
- rclone over SFTP for Storage Box transfers.
- A small, authenticated OliveTin web dashboard over building a bespoke catalog UI.
- Declarative, least-privilege UI actions that call the same verified catalog backend
  used by the command-line wrappers.
- Git as the source of truth for non-secret configuration.
- sops + age, or an equivalently simple encrypted-secret mechanism, if secrets need to exist alongside the repository.

Do not use mutable GUI configuration when a reasonable declarative alternative exists.

Document unavoidable one-time GUI/bootstrap steps.

## 3. Do fresh research before purchasing anything

Current date is September 2026.

Verify current information from official sources rather than relying on this prompt for pricing, versions, plan names, retention, or registration availability.

In particular verify:

- Hetzner Cloud server types/pricing.
- 20 TB Hetzner Storage Box pricing and features.
- Current Hetzner Terraform provider.
- Current SABnzbd stable release/container image.
- Current Prowlarr stable release/container image.
- Eweka pricing, retention and NNTP settings.
- Suitable secondary Usenet block-provider options.
- NZBGeek pricing and registration.
- DrunkenSlug registration status.
- At least one good alternative if DrunkenSlug registration is closed.
- Current QNAP Container Station / Docker Compose behavior relevant to my NAS.
- Current OliveTin stable release, container architecture support, authentication,
  access-control, validated arguments/entities, and long-running action behavior.
- Whether this exact QNAP and a Hetzner server-enforced read-only subaccount can use
  HybridMount File Cloud Gateway caching over WebDAV without write access. Hetzner
  warns that many WebDAV clients cannot mount its read-only mode; do not assume this works.

Prefer provider/operator documentation over blogs, Reddit, affiliate review sites, or forum folklore.

Briefly tell me if anything material has changed from the architecture described here before proceeding.

## 4. Account setup

Guide me through the accounts one at a time rather than throwing a giant checklist at me.

### Hetzner

Create or verify:

- Hetzner account.
- Hetzner Cloud project dedicated to this system.
- Cloud API token suitable for Terraform.
- 20 TB Storage Box.
- SSH/SFTP access for the Storage Box.
- SSH public keys.

Do not put the Hetzner API token in Git.

If the Storage Box cannot currently be provisioned with a supported first-party Terraform mechanism, treat ordering it as a documented manual bootstrap step rather than inventing brittle automation.

### Usenet provider

Default starting choice:

- Eweka as primary unlimited provider.

Before purchase, verify whether it is still a strong choice and show me:

- current effective monthly cost,
- commitment period,
- retention,
- connection count,
- TLS support,
- renewal pricing if different.

Configure NNTP using TLS.

Do not configure plaintext NNTP.

### Secondary Usenet provider

I do not initially want two unlimited subscriptions.

Research and propose a well-regarded block account on a genuinely useful alternative network/backbone.

The prior candidate was:

- UsenetExpress 500 GB block.

Verify whether it still makes sense.

Configure it in SABnzbd as a lower-priority/fill server so it is used only when the primary cannot supply an article.

### Indexers

Start with two reputable Newznab-compatible indexers.

Prior candidates:

- NZBGeek
- DrunkenSlug

Check current signup availability.

If DrunkenSlug is closed, recommend another well-established indexer instead. Do not seek invite bypasses, buy shady invitations, or use scraped/stolen API credentials.

For each indexer record:

- account tier,
- annual cost,
- API limits,
- API endpoint,
- API-key location,
- renewal behavior.

Secrets must go into the chosen secret-management mechanism, not documentation or Git.

## 5. Content policy

Prowlarr may be installed for index/search management, but default to a conservative configuration where an arbitrary index result cannot silently become a permanent catalog entry.

Create a small provenance mechanism for permanent catalog items.

A useful per-item manifest would contain fields conceptually like:

```yaml
id:
title:
category:
source:
acquired_at:
remote_path:
size:
checksum:
notes:
```

Use sensible schemas rather than slavishly following this example.

For integration testing, use content that is clearly authorized, public-domain, freely redistributable, generated specifically for the test, or an official provider/client test mechanism.

## 6. Repository

Create a dedicated directory in this repository, something along these lines:

```text
usenet-infra/
├── README.md
├── Makefile
├── .gitignore
├── .sops.yaml
│
├── terraform/
│   ├── versions.tf
│   ├── providers.tf
│   ├── variables.tf
│   ├── main.tf
│   ├── network.tf
│   ├── firewall.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
│
├── ansible/
│   ├── inventory.example.yml
│   ├── site.yml
│   ├── cloud.yml
│   ├── qnap.yml
│   └── roles/
│
├── compose/
│   ├── cloud/
│   │   └── compose.yaml
│   └── qnap/
│       ├── compose.yaml
│       └── olivetin/
│           └── config.yaml
│
├── config/
│   ├── catalog.schema.*
│   └── examples/
│
├── scripts/
│   ├── catalog-list
│   ├── catalog-pull
│   ├── catalog-evict
│   ├── catalog-status
│   ├── catalog-promote
│   └── healthcheck
│
└── docs/
    ├── account-setup.md
    ├── architecture.md
    ├── qnap-bootstrap.md
    ├── operations.md
    ├── recovery.md
    └── costs.md
```

Change this structure where there is a concrete engineering reason.

The repository should ultimately be good enough that six months from now I can understand and reproduce the system without relying on this chat.

## 7. Terraform: Hetzner Cloud

Use the official/current Hetzner Cloud Terraform provider.

Provision at minimum:

- cloud server,
- SSH key,
- appropriate primary IP,
- Hetzner firewall,
- any useful labels,
- optionally a private network if it provides actual value.

Start with an appropriately sized general-purpose VM.

Prior thinking favored something around:

- 8 vCPU,
- 16 GB RAM,
- ~160 GB local SSD,

because PAR repair and decompression can be CPU/I/O intensive while the actual 20 TB library lives elsewhere.

Re-evaluate the current Hetzner offerings and choose the best price/performance instance.

Avoid attaching hundreds of GB of expensive cloud block storage merely to warehouse completed content.

Local VM storage is primarily:

- application state,
- SABnzbd incomplete downloads,
- completed-download staging,
- PAR repair,
- decompression,
- temporary transfer staging.

Terraform should not destroy the canonical Storage Box as an incidental consequence of rebuilding the VM.

Use Terraform version constraints and provider lock files.

Do not commit Terraform state containing secrets.

## 8. Cloud security

The cloud VM should have a deliberately tiny external attack surface.

Target:

```text
Internet:
    SSH -> allowed only as needed

Not Internet-exposed:
    SABnzbd UI
    Prowlarr UI
```

Prefer binding administrative HTTP services to localhost or an internal Docker network.

For interactive administration, SSH port forwarding is acceptable, e.g. conceptually:

```text
localhost -> SSH tunnel -> localhost:SAB
localhost -> SSH tunnel -> localhost:Prowlarr
```

Do not publish SABnzbd or Prowlarr directly to the public Internet merely for convenience.

Use:

- SSH keys,
- no SSH password login where practical,
- no root SSH login,
- sane host firewalling,
- automatic security updates if appropriate.

If restricting SSH to my current public IP is practical, make that a Terraform variable so changing networks does not require hand-editing resources.

## 9. Cloud configuration with Ansible

Provision the VM declaratively.

Ansible should install/configure at least:

- Docker Engine,
- Docker Compose V2/plugin,
- rclone if used on the host,
- required filesystem directories,
- users/groups,
- permissions,
- application directories,
- update policy,
- log rotation where appropriate.

Do not manually SSH into the machine and perform undocumented snowflake configuration unless diagnosing something.

If you temporarily make a manual change while debugging, incorporate the final version into Ansible/Compose afterward.

## 10. Cloud Docker Compose

Run at least:

- SABnzbd
- Prowlarr

Use well-maintained images and pin versions intentionally rather than blindly depending forever on `latest`.

Persist application state outside the containers.

Use a directory structure roughly like:

```text
/srv/usenet/
├── config/
│   ├── sabnzbd/
│   └── prowlarr/
├── downloads/
│   ├── incomplete/
│   └── complete/
├── scripts/
└── logs/
```

Make UID/GID ownership explicit.

Use `restart: unless-stopped` or the appropriate equivalent.

Add meaningful health checks where the applications support them.

Do not expose more ports than required.

## 11. Configure SABnzbd

Configure:

- primary NNTP provider,
- TLS,
- appropriate connection count,
- secondary block provider at lower priority,
- incomplete directory,
- completed staging directory,
- PAR verification/repair,
- unpacking,
- sensible free-space thresholds.

Do not simply max out provider connection counts. Determine enough connections to saturate the useful bandwidth without pointless overhead.

Make sure a large download cannot casually fill the VM's root filesystem and destabilize the server.

Configure clear categories only where useful for organization, not for automatic acquisition.

## 12. Configure Prowlarr

Configure the selected indexers and verify their API connectivity.

Do not initially configure broad unattended acquisition rules.

If Prowlarr is connected to SABnzbd, ensure that deliberate human action is still required to initiate an acquisition.

## 13. Storage Box layout

Design a clean canonical hierarchy.

For example:

```text
catalog/
├── movies/
├── television/
├── audio/
├── books/
├── software/
├── archives/
└── other/
```

Do not assume these exact categories are ideal; choose something maintainable.

Each permanent catalog object should be associated with provenance metadata.

Avoid relying exclusively on filenames for identity.

## 14. Storage Box credentials and QNAP safety

I want the QNAP unable to accidentally delete the canonical catalog.

Take advantage of Hetzner Storage Box sub-account restrictions/read-only support if currently available.

A desirable pattern is:

```text
Storage Box main account
    full write access
    used only by cloud ingestion

catalog directory
    populated by cloud VM

QNAP-specific subaccount
    restricted to catalog directory
    READ ONLY
```

If Storage Box sub-account directory semantics require a slightly different layout, adapt accordingly.

The result that matters is:

**credentials present on the QNAP must not have permission to modify or delete the canonical remote catalog.**

Use SSH-key authentication where supported.

Verify server fingerprints rather than blindly accepting them.

## 15. Moving completed acquisitions to Storage Box

Do not download directly into an SFTP/rclone mount.

SABnzbd should:

1. download locally,
2. verify,
3. repair if needed,
4. unpack locally,
5. finish locally,
6. then transfer the completed object to Storage Box.

Implement a robust promotion mechanism.

Possible approaches include:

- SAB post-processing script,
- host-side transfer queue,
- small transfer service.

Choose the least fragile implementation.

Requirements:

- partial uploads must not appear as complete catalog entries;
- failed uploads remain recoverable;
- a successful transfer is verified before local staging is removed;
- retries are safe/idempotent;
- promotion updates catalog metadata;
- failure is obvious in logs/status.

Avoid a polling monstrosity if SAB's supported post-processing mechanism handles the workflow cleanly.

## 16. QNAP reconnaissance

Before changing the NAS, discover:

- exact QNAP model,
- CPU architecture,
- QTS vs QuTS hero,
- OS version,
- Container Station version,
- Docker version,
- Compose V2 availability,
- OliveTin image compatibility with the exact CPU architecture and kernel,
- HybridMount version, available mount modes, free-license availability, and whether
  reserved cache is supported on this model/OS,
- existing shares,
- relevant filesystem paths,
- available local storage,
- intended destination share for cached content,
- NAS LAN address.

Do not assume `/share/CACHEDEV1_DATA/...` or another model-specific physical path.

Prefer stable QNAP shared-folder paths such as `/share/<ShareName>/...` when appropriate.

Do not interfere with unrelated containers or NAS services.

## 17. QNAP bootstrap

Minimize non-declarative setup.

Human/manual steps may include:

- installing/updating Container Station,
- temporarily enabling SSH,
- confirming an administrative account that can SSH,
- creating a dedicated QNAP shared folder if QTS requires GUI/API management for it.
- approving a stable LAN-only address and local account for the catalog dashboard.

Document each unavoidable step precisely in `docs/qnap-bootstrap.md`.

After bootstrap, application configuration should come from the repository.

Current QNAP systems use Compose V2 syntax:

```text
docker compose
```

not legacy:

```text
docker-compose
```

Verify on this particular NAS.

## 18. QNAP implementation

The QNAP does NOT need SABnzbd or Prowlarr.

Its job is selective caching and providing the primary catalog-management UI.

Prefer a containerized rclone implementation under Container Station so QNAP firmware updates do not erase miscellaneous packages installed into the base OS.

Create a QNAP Compose stack using the current official/well-maintained rclone image
and a pinned OliveTin image. OliveTin is the user-facing control surface; the
existing manifest-aware catalog tool remains the implementation of list, status,
pull, evict, verification, and failure recording.

Conceptually it needs access to:

```text
/share/Container/usenet/
    configuration/scripts/UI configuration

/share/<LOCAL_LIBRARY>/
    local cached content
```

The Storage Box credential on the QNAP must be read-only remotely.

Do not put that private key or rclone secret in Git.

Run the dashboard with least privilege:

- bind it only to the NAS LAN address or loopback behind an already trusted private
  access path; do not expose it directly to the Internet;
- require authentication even on the LAN;
- expose only predefined catalog actions with validated arguments, never a general
  shell or arbitrary rclone command field;
- give it only the catalog scripts, read-only Storage Box configuration/key material,
  catalog state, transfer staging, and local cache paths it requires;
- do not mount the Docker socket into the dashboard container;
- run as the dedicated numeric QNAP UID/GID with a read-only root filesystem where
  practical; and
- keep the UI configuration declarative and versioned in Git, with credentials kept
  in ignored runtime files or the chosen encrypted-secret mechanism.

The dashboard must invoke the same catalog backend as the CLI. It must not implement
raw remote-to-local copies that bypass manifest resolution, free-space checks, hidden
staging, SHA-256 verification, atomic publication, retry behavior, or failure records.

## 19. QNAP catalog dashboard and fallback commands

The authenticated OliveTin dashboard is the primary interface for normal cache
management. It should be usable from a desktop or phone without copying item IDs or
shell commands.

The main view should show at minimum:

- remote item count and total size;
- local item count and total size;
- available NAS capacity and configured reserve;
- transfers in progress and recorded failures;
- one row or card per catalog item with title, category, size, and state;
- clear states such as `remote only`, `downloading`, `local`, and `failed`; and
- only the action valid for the current state, such as **Download**, **Retry**, or
  **Remove local copy**.

Generate the dashboard's item choices/cards from structured catalog output rather
than requiring a free-form item ID. Refresh that data on demand and after each action.
Display long-running pull progress or, where exact byte progress is unavailable,
provide an unambiguous running state plus accessible execution output/history.

Required interactions:

### Browse and inspect

- Search or filter by title and category.
- Distinguish remote-only content from verified local content at a glance.
- Show useful failure text without requiring an SSH session for the first diagnosis.
- Provide a compact status/capacity summary on the same dashboard.

### Download to QNAP

- Select an item and press **Download**; do not require copying its ID.
- Validate that the item exists remotely and that sufficient local free space remains.
- Copy directly from Storage Box to QNAP through hidden staging.
- Support safe retry, verify all manifest SHA-256 values, atomically publish the local
  object, update local state, and refresh the dashboard.

### Remove the local copy

- Show a confirmation that explicitly says the canonical remote copy will remain.
- Delete only the QNAP object and local state record.
- Refresh the item to `remote only` after success.
- Never issue an rclone delete or other remote-mutating operation.

OliveTin execution history should provide a simple audit trail of who initiated each
operation, its arguments, status, and output. Configure timeouts so large transfers
can remain active without becoming orphaned merely because a browser closes.

Keep very simple `just` recipes for recovery, automation, testing, and advanced
operation. They are not the primary day-to-day interface.

I want recipes conceptually like:

```text
catalog-list
catalog-status
catalog-pull <item>
catalog-evict <item>
```

Behavior:

### catalog-list

Show remote catalog items with useful information such as:

- title/path,
- size,
- category,
- whether present locally.

### catalog-status

Summarize:

- remote catalog size,
- local cache size,
- transfers in progress,
- failed transfers,
- available NAS capacity.

### catalog-pull

Example:

```text
catalog-pull "some/catalog/item"
```

It should:

- validate the item exists remotely,
- verify sufficient local free space,
- copy it from Storage Box to QNAP,
- support safe resume/retry,
- verify successful completion,
- update local status.

### catalog-evict

Example:

```text
catalog-evict "some/catalog/item"
```

It should:

- delete only the QNAP copy,
- leave the remote Storage Box copy untouched.

Because the NAS credential is read-only, even a bug in this tooling should not be able to erase the canonical copy.

Do not use rclone's general-purpose Web GUI as the primary interface: it can initiate
raw transfers that bypass catalog invariants. It may be enabled temporarily for
administrative diagnosis only, bound to loopback and authenticated, then disabled.

During QNAP reconnaissance, run a time-boxed HybridMount compatibility experiment if
the installed version supports File Cloud Gateway with generic WebDAV storage:

1. use only the existing server-enforced read-only Storage Box subaccount;
2. verify that the mount can browse and read without any write permission;
3. verify the cloud/local/downloading icons and reserved-cache behavior;
4. attempt overwrite and delete against a disposable writer-created sentinel and
   require both to fail remotely; and
5. record the result in `docs/qnap-bootstrap.md`.

HybridMount is optional. If it cannot mount the read-only account, requires a writable
credential, obscures integrity/failure state, or cannot preserve the manifest-aware
workflow, stop the experiment and retain OliveTin. Do not adopt ordinary two-way sync,
an automatic bidirectional mount, or a writable remote credential as a workaround.

## 20. Transfer tuning

The expected remote-to-home traffic is around 1 TB/month.

Tune conservatively.

Make transfer concurrency and bandwidth limits configurable.

Consider:

- NAS disk performance,
- home WAN speed,
- Atlantic latency,
- Storage Box connection limits,
- ability to resume interrupted transfers.

Do not optimize benchmarks at the expense of reliability.

Use rclone transfer/check settings appropriate to SFTP and verify what checksums the Storage Box backend actually supports instead of assuming.

## 21. Catalog metadata

Implement the lightest-weight catalog that solves the problem.

I do not need Kubernetes or a distributed database.

SQLite, structured JSON/YAML manifests, or another simple format is acceptable.

I should be able to answer:

```text
What exists remotely?
What exists locally?
How large is it?
Where did it come from?
What is its authorization/provenance?
When was it acquired?
Has its integrity been checked?
```

The remote files remain the source of truth for bytes.

Catalog metadata should itself be backed up.

## 22. Secrets

Never commit:

- Usenet passwords,
- indexer API keys,
- Hetzner Cloud tokens,
- Storage Box passwords,
- SSH private keys,
- rclone cleartext credentials.

Use:

- SSH keys,
- restrictive file permissions,
- environment files excluded from Git,
- and/or sops+age.

Produce `.env.example` or equivalent showing required variable names without values.

At the end, explicitly scan the Git working tree/history for accidentally committed secrets.

## 23. Backups

Infrastructure source code is in Git.

Back up important application configuration separately from the 20 TB catalog:

- SABnzbd settings,
- Prowlarr settings/database,
- OliveTin authentication/runtime state and execution history where it is not
  reproducible from Git,
- catalog metadata,
- critical scripts/configuration.

Do not confuse Storage Box snapshots with an independent backup of the 20 TB collection.

I am primarily concerned with being able to rebuild the service configuration. The bulk content itself does not initially need an expensive second 20 TB replica unless we decide otherwise.

## 24. Observability

Create a useful health/status backend and surface the QNAP-relevant results in the
catalog dashboard. Retain the command for automation and recovery.

At minimum detect:

- VM unavailable,
- SABnzbd unhealthy,
- Prowlarr unhealthy,
- provider authentication failure,
- indexer API failure,
- Storage Box unavailable,
- Storage Box approaching capacity,
- VM scratch storage approaching capacity,
- failed remote promotions,
- QNAP local storage approaching capacity,
- catalog dashboard unavailable or unhealthy, and
- failed or stalled QNAP pulls visible in both health output and the dashboard.

Avoid deploying Prometheus/Grafana just because they exist.

Simple health scripts and container logs are enough unless monitoring requirements justify more.

## 25. Updating

Document a safe upgrade workflow:

```text
git pull
terraform plan
ansible-playbook ...
docker compose pull
docker compose up -d
healthcheck
```

Pin versions sufficiently that upgrades are deliberate.

If using Dependabot/Renovate or similar, configure it to propose changes rather than silently upgrading production.

## 26. Recovery drills

Document how to rebuild from:

### Lost cloud VM

Expected outcome:

```text
terraform apply
ansible-playbook
restore app config
docker compose up
reconnect Storage Box
```

Canonical library survives.

### Lost QNAP configuration

Recreate QNAP Compose/configuration and reconnect with read-only Storage Box credentials.

Canonical library survives.

### QNAP disk failure

Replace/restore NAS storage and selectively pull desired material again.

Canonical library survives.

### Lost Terraform state

Document the recovery/import procedure.

## 27. Testing

Do not declare success merely because containers show `running`.

Perform an end-to-end integration test with unquestionably authorized test content.

Verify:

1. Primary Usenet TLS connection succeeds.
2. Secondary provider is configured correctly.
3. Both indexers' API tests succeed.
4. SAB can process an authorized/test NZB or equivalent provider-supported test.
5. Verification/unpacking works if applicable.
6. Promotion to Storage Box succeeds.
7. Provenance/catalog record exists.
8. The catalog dashboard sees the remote item and shows it as `remote only`.
9. The item can be selected and downloaded in the dashboard without copying its ID.
10. The dashboard shows a running state and retains useful success/failure output.
11. The underlying pull stages safely and checks every manifest SHA-256 value.
12. Local status and the dashboard report the verified item as `local`.
13. The dashboard requires confirmation and removes only the NAS copy.
14. The dashboard returns the item to `remote only`, and the remote item still exists.
15. The fallback `catalog-list`, `catalog-status`, `catalog-pull`, and `catalog-evict`
    commands operate through the same backend and preserve identical safety behavior.
16. QNAP read-only credentials cannot delete or overwrite the remote item.
17. The dashboard requires authentication and is unreachable from the public Internet.
18. Restarting the relevant containers does not break configuration or execution history.
19. Git contains no credentials.

Do not reboot the entire QNAP without asking me first.

## 28. Cost verification

At the end, produce an updated recurring-cost table.

Include:

- Hetzner VM,
- IPv4 if separately charged,
- Storage Box,
- primary Usenet provider,
- secondary/block provider amortization,
- indexer subscriptions,
- any other recurring service you added.

Separate:

- monthly recurring,
- annual subscriptions converted to monthly equivalent,
- one-time purchases.

Flag anything that has pushed expected recurring cost materially beyond ~$90/month.

## 29. Documentation to leave behind

The finished repository must explain:

### `README.md`

Very short overview, primary dashboard URL/access method, and fallback commands.

### `docs/architecture.md`

Architecture, trust boundaries, data flow, dashboard-to-catalog-backend boundary, and
why the UI has neither a Docker socket nor remote write authority.

### `docs/account-setup.md`

What accounts exist, why each exists, subscription tier, renewal information and where credentials are stored.

Never include actual passwords/API keys.

### `docs/qnap-bootstrap.md`

Any manual QNAP setup required before IaC takes over, dashboard authentication/access,
and the result of the optional HybridMount read-only compatibility experiment.

### `docs/operations.md`

Normal operations:

- searching,
- intentional acquisition,
- catalog promotion,
- browsing and filtering the catalog in the dashboard,
- downloading to and removing from the NAS through dashboard controls,
- reading transfer output/history and diagnosing a failed pull,
- using listing, pull, status, and eviction commands as a fallback,
- checking failures,
- updating software.

### `docs/recovery.md`

Rebuild/recovery steps, including recreating the dashboard and using the CLI backend
while it is unavailable.

### `docs/costs.md`

Current recurring costs with date checked. Record OliveTin as no recurring software
cost and include any QNAP license only if an optional HybridMount feature is actually
adopted after testing.

## 30. How to interact with me

Work incrementally.

At the beginning:

1. Briefly restate the target architecture.
2. Research/verify the current products.
3. Tell me if you recommend changing any material architectural choice.
4. Then begin account setup.

During account signup, give me only the immediate human actions required.

For example:

```text
I need you to create the Eweka account now.

Choose: <specific verified plan>
Price: <verified price>
Reason: <one sentence>

When finished, do not paste the password here.
Tell me only that the account exists, and I will continue.
```

Do not make me manually transcribe configuration values that you can discover or apply yourself.

Once SSH/API access is available, do the implementation rather than turning the rest into a tutorial.

Before destructive actions, show me exactly what will be deleted/replaced.

Do not repeatedly ask me questions whose answers can be obtained by inspecting the existing systems.

If an implementation choice is minor, choose a sensible default and proceed.

## 31. Completion criteria

The project is complete when I can do all of the following:

- open the authenticated catalog dashboard through its private LAN access path;
- browse or filter catalog items and distinguish `remote only`, `downloading`,
  `local`, and `failed` states;
- select **Download** without copying an item ID and see its execution status;
- select **Remove local copy**, confirm the action, and see the item return to
  `remote only`; and
- perform the same operations with the recovery CLI when the dashboard is unavailable.

The underlying infrastructure and recovery interface must also support:

```text
# inspect infrastructure
terraform plan

# rebuild/configure cloud
ansible-playbook ...

# inspect containers
docker compose ps

# see catalog
just catalog-list

# make an item local
just catalog-pull <item>

# inspect status
just catalog-status

# remove only the local copy
just catalog-evict <item>
```

and the following statements are true:

- Hetzner Storage Box is the canonical content store.
- Acquisition continues even if the QNAP is offline.
- Completed cloud acquisitions are safely promoted to Storage Box.
- The QNAP can pull selectively through a point-and-click dashboard.
- Dashboard actions use the same manifest-aware, verified catalog backend as the CLI.
- The dashboard requires authentication, is not Internet-exposed, provides no general
  shell, has no Docker socket, and has no remote write authority.
- QNAP credentials cannot destroy remote content.
- Administrative web UIs are not exposed publicly.
- NNTP uses TLS.
- Infrastructure is substantially reproducible from Git.
- Secrets are not in Git.
- A complete rebuild procedure exists.
- End-to-end authorized-content testing has succeeded.
- Current operating cost is documented.
- No unattended piracy-oriented acquisition automation has been enabled.

When finished, give me a concise system handoff containing:

1. architecture actually implemented,
2. repository location,
3. dashboard and service endpoints/private access methods,
4. normal dashboard workflow plus five or fewer fallback commands,
5. recurring monthly cost,
6. known remaining limitations.
