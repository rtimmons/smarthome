FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends samba-ad-dc krb5-user bind9-dnsutils ldap-utils smbclient python3-samba ca-certificates openssl tini iputils-arping && rm -rf /var/lib/apt/lists/*
# Ubuntu ships the AD schema separately from the daemon.
RUN apt-get update && apt-get install -y --no-install-recommends samba-ad-provision && rm -rf /var/lib/apt/lists/*
# Required by Samba's lock-consistent offline backup implementation.
RUN apt-get update && apt-get install -y --no-install-recommends tdb-tools && rm -rf /var/lib/apt/lists/*
COPY provision.py /usr/local/libexec/provision.py
COPY run.sh /usr/local/bin/run-dc
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/run-dc"]
