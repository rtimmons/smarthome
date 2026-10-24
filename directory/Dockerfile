FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944
ARG BUILD_VERSION=dev
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends samba-ad-dc samba-ad-provision krb5-user bind9-dnsutils ldap-utils smbclient python3-samba ca-certificates openssl tini iputils-arping tdb-tools iproute2 openssh-server sudo dnsmasq-base \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash identity-admin \
    && printf 'identity-admin ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/identity-admin \
    && chmod 0440 /etc/sudoers.d/identity-admin \
    && rm -f /etc/ssh/ssh_host_* \
    && mkdir -p /run/sshd \
    && ln -s /data/tls /tls
COPY app/run.py /usr/local/libexec/run-directory.py
COPY app/directory_state.py /usr/local/libexec/directory_state.py
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/python3", "/usr/local/libexec/run-directory.py"]
