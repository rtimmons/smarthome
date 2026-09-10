# Usenet host automation

This directory provisions the Ubuntu cloud host and deploys the already
supported application stack to QNAP. It intentionally does not install,
upgrade, or otherwise alter QTS/QuTS, Container Station, or QNAP packages.

## Controller setup

Run Ansible from this directory so the local configuration and ignored paths
are unambiguous:

```sh
cp inventory.example.yml inventory.yml
just ansible-setup
just configure-cloud
just configure-qnap
```

`site.yml` runs both host groups. Host-key checking remains enabled; populate
the controller's `known_hosts` before the first run rather than bypassing it.
The Python-free QNAP path uses raw SSH commands, which Ansible cannot usefully
simulate in check mode; use syntax checking, review the rendered variables,
and run it live only after preflight inputs are correct. Cloud check mode is
useful after its initial administrator and packages have been bootstrapped.

## Required local values

Edit the ignored `inventory.yml` with real hosts, verified host-key files, the
cloud administrative source CIDRs, the QNAP dedicated account's numeric UID/GID,
and the read-only Storage Box subaccount coordinates. Keep private values in
ignored or vaulted vars files. `just generate-ssh-keys` creates separate keys
for cloud administration, Storage Box writes, Storage Box reads from QNAP, and
QNAP administration; install only each corresponding public key on its target.

Hetzner's stock Ubuntu image is bootstrapped through its initial `root` SSH
account. The first cloud run creates `cloud_admin_user`, installs the supplied
public key, grants sudo, verifies that login material, and only then disables
root/password SSH. After that successful run, change the cloud host's
`ansible_user` in ignored `inventory.yml` from `root` to the configured
administrator for every subsequent run.

Place the QNAP-only private key and an independently verified `known_hosts`
file beneath the ignored `files/secrets/storagebox/` directory, or point the
inventory variables at another protected controller path. Optional cloud
`rclone.conf` and catalog health-environment defaults are copied only when
their source variables are set. After the applications start, Ansible reads
the API keys they generated locally and atomically renders the live
`catalog.env`; keys are never printed or copied back to the controller. Neither
live file is committed because it can contain remote or application credentials.

The non-root administrator belongs to the `usenet` group. Checked-in catalog
commands are exposed through root-owned wrappers that use an allowlist helper
to run as the non-login `usenet` service account. The catalog environment and
rclone configuration are group-readable for the SSH command helper; the
Storage Box writer private key remains owner-only mode `0600`.

Before the cloud firewall is enabled, the play requires at least one explicit
`cloud_ssh_allowed_cidrs` entry, verifies that the active SSH source is covered,
and confirms the non-root administrator has a non-empty `authorized_keys` file.
SSH forwarding remains limited to local
forwarding so SABnzbd and Prowlarr can be reached through tunnels while their
Compose ports stay bound to `127.0.0.1`.

The Docker repository, signing-key fingerprint, Docker component releases,
rclone release, and Ansible collection releases are intentionally pinned to
values verified on 2026-09-10. Research and update the related values together
instead of switching them to floating `latest` channels.

## QNAP bootstrap boundary

Complete vendor-supported NAS setup first: install or update Container Station
through QNAP, enable SSH temporarily, create the intended shared folders, and
grant the dedicated account Docker plus read/write access to only its
application and cache locations. The preflight role records model/firmware,
kernel, architecture, page size, shares, capacity, network addresses, Docker,
Compose, and dedicated-account information. Deployment uses Ansible's raw SSH
transport plus existing POSIX utilities, so Python is not required on the NAS.
It stops before deployment if an existing dependency or permission is
unsuitable; it never attempts to repair the base NAS by installing packages.
