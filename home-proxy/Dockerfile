FROM docker.io/library/caddy:2.11.4-alpine
ARG BUILD_VERSION=dev
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
COPY app/Caddyfile /etc/caddy/Caddyfile
COPY app/run.sh /usr/local/bin/home-proxy-run
# Check syntax during packaging. Caddy validates the mounted certificates when
# it starts; private keys must never enter the image/build context.
RUN chmod 755 /usr/local/bin/home-proxy-run && sh -n /usr/local/bin/home-proxy-run && caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
CMD ["/usr/local/bin/home-proxy-run"]
