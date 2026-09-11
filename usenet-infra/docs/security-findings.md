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

Treat these keys as exposed. Determine whether the historical hosts/accounts
still exist and remove any remaining authorization through a separately reviewed
access change; verify a working replacement before removing access. Do not try
the exposed private keys against live systems to test them. Revocation status
must be recorded before closing the finding. Removing files from the current
tree or rewriting Git alone does not revoke a key already obtained by others.

The scanner has no exception hiding these findings. `scripts/secret-scan` fails
on full history; `scripts/secret-scan --no-history` explicitly labels a narrower
current source/index check. Until the historical finding is dispositioned, the
final secret-scan step of `just usenet-test` therefore fails even when functional
tests, compilation and configuration checks pass.

The separate nonempty tracked Home Assistant secrets-file finding and
repository dependency alerts remain recorded in `plan.md`. Neither this scan
nor the DR tests certify all service credentials, historical files or dependencies.
