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
vulnerabilities. Service tests and builds pass. These are source changes; live
add-ons require deployment, and GitHub default-branch alerts will remain open
until the updates reach that branch. No blanket upgrade or scanner exemption
was applied.
