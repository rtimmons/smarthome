FROM docker.io/authelia/authelia:4.39.28
ARG BUILD_VERSION=dev
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
COPY app/run.sh /usr/local/bin/household-authelia
RUN chmod 0755 /usr/local/bin/household-authelia
ENTRYPOINT ["/usr/local/bin/household-authelia"]
