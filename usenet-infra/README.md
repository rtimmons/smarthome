# Usenet acquisition and selective cache

This directory defines a private, deliberately operated system for content the
owner is authorized to obtain. SABnzbd and Prowlarr run on a replaceable Hetzner
VM. A protected Storage Box is the canonical byte store: it starts as a 1 TB
BX11 and grows in place through BX21 and BX31 to the eventual 20 TB BX41 target.
The QNAP has a separate server-enforced read-only Storage Box identity and holds
only selected, locally cached items.

Administrative web interfaces bind to cloud loopback only. Acquisition does not
depend on the QNAP, and no unattended search-to-permanent-catalog automation is
enabled. Promotion is a deliberate command that hashes locally, uploads beneath
`.incoming`, verifies the remote bytes, publishes the object, then publishes its
provenance manifest last.

Start with [account setup](docs/account-setup.md), then follow the
[QNAP bootstrap](docs/qnap-bootstrap.md). Architecture, routine operation, and
recovery are documented under `docs/`.

Capacity is reviewed at an 80% warning and upgraded before 90%; expansion is a
deliberate, reviewed Terraform change, not an automatic purchase. See
[costs](docs/costs.md) and [operations](docs/operations.md).

Normal workstation commands, run from this directory:

```sh
just catalog-list
just catalog-status
just catalog-pull "authorized-test-example"
just catalog-evict "authorized-test-example"
just cloud-health
```

Copy `.env.example` to `.env` for non-secret SSH targets. Secrets, private keys,
Terraform state, live inventory, runtime configuration, and backups are ignored
by Git. Run `just test` before applying changes.
