#!/bin/sh
set -eu
umask 077
mkdir -p /run/caddy-private
chmod 700 /run/caddy-private
certificate=/ssl/smarthome/acme/current/fullchain.pem
test -s "$certificate"
credential=/ssl/smarthome/arr-gateway-authorization
test -s "$credential"
SMARTHOME_ARR_AUTH=$(cat "$credential")
case "$SMARTHOME_ARR_AUTH" in 'Basic '*) ;; *) exit 1 ;; esac
export SMARTHOME_ARR_AUTH
previous=$(sha256sum "$certificate" | cut -d ' ' -f 1)
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
server=$!
watcher=
cleanup() {
    trap - TERM INT
    if test -n "$watcher"; then kill "$watcher" 2>/dev/null || true; fi
    kill -TERM "$server" 2>/dev/null || true
    wait "$server" 2>/dev/null || true
}
trap cleanup TERM INT EXIT
(
    while kill -0 "$server" 2>/dev/null; do
        sleep 60
        current=$(sha256sum "$certificate" | cut -d ' ' -f 1) || continue
        if test "$current" != "$previous"; then
            if caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile \
                    --address unix//run/caddy-private/admin.sock --force; then
                previous=$current
            fi
        fi
    done
) &
watcher=$!
wait "$server"
