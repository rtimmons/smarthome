FROM ubuntu:26.04@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944
ARG BUILD_VERSION=dev
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-paramiko iproute2 iptables iputils-arping tini \
    && rm -rf /var/lib/apt/lists/*
COPY app/route.py /usr/local/libexec/directory-route.py
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/python3", "/usr/local/libexec/directory-route.py"]
