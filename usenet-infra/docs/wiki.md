# Smarthome wiki and legacy Usenet entrance

The Usenet field guide is now a section of the household wiki. Its canonical
source is [`../../wiki/content/media/usenet.md`](../../wiki/content/media/usenet.md).
The old HTML is retained only as a test fixture for compatibility anchors.

Use `http://wiki.home.arpa/` or numeric recovery at `http://192.168.1.66/`.
The existing `http://192.168.1.66:8090/` entrance redirects to the media guide and
preserves URL fragments. DNS/DHCP acceptance is recorded in
[DNS operations](../../docs/operations/home-dns.md).

Run `just wiki-check`, `just wiki-preview`, `just wiki-deploy`, or
`just wiki-rollback` at repository root. `just usenet-wiki-deploy` remains an
alias. Do not edit generated HTML or copy the whole checkout to the NAS.

See the canonical [wiki maintenance guide](../../docs/operations/wiki.md) for
source ownership, reviews, deployment evidence and rollback. The existing QNAP
Compose project and named wiki share remain in use. Content publication switches
`live/current` atomically inside a stable read-only mount; ordinary updates
and content rollbacks leave Caddy running. Runtime changes and the initial
upgrade from release-specific mounts recreate only the wiki container. The share
root and private environment files remain outside the container.
