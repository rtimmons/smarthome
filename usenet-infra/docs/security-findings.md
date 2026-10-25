# Historical credential findings — September 11, 2026

The expanded scanner checks the main repository's current source, index and
reachable Git history without traversing submodule repositories. Current
source/index checks pass. **The full history check fails on two exposed
RSA-2048 private keys.** No values are included here; no historical key was used
for authentication, no live credential was changed, and no history was rewritten.

| Public fingerprint | Historical paths and lifetime | Evidence about consumers |
| --- | --- | --- |
| `SHA256:sYWPugxRBp4QMTHh4w9kK5TB0wWaPwq3sSwnUUDkJvk` | `ansible/id_rsa`, later `pkg/Ansible/id_rsa` and `Ansible/id_rsa`; added `b6fb08eb435a1905303b71ac763e206849fc19c7` on 2017-07-07, removed `92a1f5d71a22265e897e3e6364c4b3a26b636c77` on 2018-01-14 | Historical inventory explicitly selected it for `pi@rypi.local`. |
| `SHA256:GeVS/NcacPnrMa67UDFReuuwO4zTrewPo/Ar6n7EeN4` | `Ansible/.ssh/id_rsa`, later `Ansible/roles/smarthome-user/files/id_rsa`; added `92a1f5d71a22265e897e3e6364c4b3a26b636c77` on 2018-01-14, removed `5746ce987f16dca2e483b932a97f56148d0af381` on 2018-01-17 | Associated with the Raspberry Pi `smarthome-user` role and historical inventory `192.168.1.44` / `pi@raspberrypi.local`. No checked-in task proves that this private file was installed; live acceptance is unverified. |

Both public fingerprints were derived offline and checked against the matching
historical public-key files. They are distinct keys and neither matches any of
the six current inventoried dedicated identities (five Usenet plus Home
Assistant). This comparison does **not** establish that old authorized-key
entries have been removed everywhere.

Treat these keys as exposed. On September 11, 2026, the user confirmed both
known Raspberry Pi consumers were retired or wiped. This closes remediation
for those known consumers; it does not prove absence of reuse on unknown hosts.
If another consumer is discovered, remove its authorization using a separate
current identity after verifying replacement access. Do not try
the exposed private keys against live systems to test them. Do not reuse the exposed identities. Removing files from the current
tree or rewriting Git alone does not revoke a key already obtained by others.

The scanner has no exception hiding these findings. `scripts/secret-scan` fails
on full history; `scripts/secret-scan --no-history` explicitly labels a narrower
current source/index check. Even with the known consumers retired, the
final secret-scan step of `just usenet-test` therefore fails even when functional
tests, compilation and configuration checks pass.

## Home Assistant configuration

The tracked `new-hass-configs/secrets.yaml` had one nonempty `some_password`
entry. A remote-side whole-file comparison showed it matches the live file;
no matching secret reference was found in checked local configuration or the
live root YAML files. The value is not copied into these notes. The file is now removed
from Git tracking while its ignored local copy is preserved for encrypted backup;
use the empty `secrets.example.yaml` as the public template. Do not overwrite live
HA secrets during deployment. Deleting the tracked file does not erase history
or revoke an unknown external consumer; any future identified reuse requires
rotation through that service.

## Dependency updates

Compatible lockfile updates for snapshot-service, tinyurl-service, sonos-api,
grid-dashboard/ExpressServer and the HA config generator address all 53 alerts
returned by GitHub on September 11. Each updated lockfile reports zero npm audit
vulnerabilities. Service tests and builds pass. The four affected live add-ons were rebuilt/deployed and passed readiness
checks. The config generator is a local build tool. GitHub default-branch alerts
remain open until the branch updates reach that branch. No blanket upgrade or scanner exemption
was applied.

## October 25, 2026 remediation and remaining approvals

The current-source/index scan passes. The scanner now also checks commit messages
and reflog-only history; a synthetic abandoned-commit test verifies both and that
`--no-history` still describes a narrower check. The full scan still reports the
two historical RSA keys plus two source-visible private paths. The latter are
links retained in two local Codex checkpoint trees, not exposed backup contents.
No scanner exemptions were added.

Using current dedicated access only, a read-only audit checked one NAS, two cloud
and one HA SSH authorization files. Neither exposed public fingerprint appeared.
This is evidence for those accessible files, not proof against unknown reuse or
other machines. The earlier user confirmation that the two known Pi consumers
were retired/wiped remains the basis for their revocation disposition.

An isolated cleanup preview removed the documented historical key paths, the old
plaintext HA secrets file, private-directory paths and their local tree-checkpoint
references. A fresh clone containing all preview refs passed the expanded scanner;
the current source tree hash stayed identical. The preview rewrote 99 refs and
sanitized two checkpoint trees. It has not been applied to the active repository
or pushed. Applying it needs coordinated handling of active worktrees, five saved
stashes, reflogs, remote branches and other clones; it changes commit IDs and
removes old commit signatures. Immutable private recovery snapshots must remain
unchanged. Remote ref refresh was blocked by the unavailable SSH signing agent.
See [GitHub's removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

Pre-update backup verification found seven accidentally root-owned evidence files
inside existing service-owned configuration directories: four replay logs, two
replay topology/receipt files and the Prowlarr authentication migration receipt.
Their intended service ownership was restored, retaining mode 0600 and identical
bytes. The producing tasks now retain that ownership. The resulting encrypted
cloud archive independently verified 1,020 files and 17 SQLite databases.
A second encrypted cloud archive verified the same file/database counts after
the Seerr update. Original immutable recovery archives were not modified.

Seerr was updated to pinned stable 3.5.1; its two accounts, credentials, permissions,
API key, database integrity and native connections passed checks. See
[Seerr operations](seerr.md#october-25-security-update).

On October 25, QNAP TS-451D2 was updated through QTS with the official
TS-X53D image to **5.2.11.3661 build 20261023**, the fixed release named in
[QNAP's critical PHP advisory](https://www.qnap.com/en/security-advisory/qsa-26-18).
The vendor checksum matched before installation. After reboot, SSH reported
5.2.11/build 20261023, the four-disk RAID was healthy, SMARTHOME domain trust
passed, and hosted containers restarted. The original dedicated SSH key was
preserved; see [home-folder recovery](qnap-bootstrap.md#october-25-ssh-recovery).

Plex was updated through App Center using the checksum-verified official Intel
QNAP package to **1.43.5.11029-6bf8af3f0**. App Center and the live Plex API
confirmed the update. Playback was idle before installation. Server identity,
token and five library-definition fingerprints matched before and after; no
media scan or acquisition was initiated. This does not establish post-update
Apple TV/Roku playback or a fresh managed-profile authorization test. Fresh
three-scope encrypted NAS settings backups passed both before and after
installation, including required off-host upload and readback verification.

QTS retained required app updates and automatically updated License Center to
1.9.61. App Center still offers an HBS update; that separate package has not
been updated as part of this firmware/Plex checkpoint. QTS also reported its
firmware-policy migration to automatic quality updates at the configured time;
no additional policy change was made by the agent.
