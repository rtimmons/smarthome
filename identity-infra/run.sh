#!/bin/sh
set -eu
umask 077
python3 /usr/local/libexec/provision.py
# QNAP uploads are owned by the deployment UID. Samba correctly rejects a TLS
# private key unless root owns it. Recreate the same bytes in private tmpfs;
# never weaken Samba's ownership checks or generate a replacement certificate.
mkdir -p /run/identity-tls
for name in dc.key dc-chain.crt ca.crt; do
    cat "/tls/$name" > "/run/identity-tls/$name"
    chmod 600 "/run/identity-tls/$name"
done
sed -i 's# = /tls/# = /run/identity-tls/#g' /data/etc/smb.conf
cp /data/private/krb5.conf /etc/krb5.conf
# QNET may assign a new MAC after recreation. Refresh LAN neighbor caches before
# accepting directory traffic; no host network privileges are required.
arping -U -I eth0 -c 2 192.168.1.10 >/dev/null 2>&1 || true
exec samba --interactive --no-process-group --configfile=/data/etc/smb.conf
