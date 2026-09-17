FROM docker.io/library/caddy:2.11.4-alpine

# QNAP supplies the dedicated numeric UID/GID at runtime. Copy the binary to
# remove any file capabilities inherited from the upstream layer.
RUN cat /usr/bin/caddy > /usr/bin/caddy.nonroot \
    && chmod 0555 /usr/bin/caddy.nonroot \
    && mv /usr/bin/caddy.nonroot /usr/bin/caddy
