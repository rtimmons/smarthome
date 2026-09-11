FROM docker.io/library/caddy:2.11.4-alpine
# The official binary has cap_net_bind_service, which cannot execute with an
# empty bounding set. A fresh inode drops that xattr; these ports exceed 1024.
RUN cat /usr/bin/caddy > /usr/bin/caddy.nonroot \
    && chmod 0555 /usr/bin/caddy.nonroot \
    && mv /usr/bin/caddy.nonroot /usr/bin/caddy
