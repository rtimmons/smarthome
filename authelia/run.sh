#!/bin/sh
set -eu
umask 077
# The controller removes this transport seed after the first healthy startup.
# Subsequent rebuilds use the persistent add-on configuration, never new keys.
if test -f /ssl/smarthome/authelia-seed/configuration.json; then
    if test -f /config/configuration.json && ! cmp -s /config/configuration.json /ssl/smarthome/authelia-seed/configuration.json; then
        test -f /ssl/smarthome/authelia-seed/previous.sha256
        actual=$(sha256sum /config/configuration.json | cut -d ' ' -f 1)
        test "$actual" = "$(cat /ssl/smarthome/authelia-seed/previous.sha256)"
        cp /config/configuration.json /config/configuration.previous.json
    fi
    test -f /ssl/smarthome/authelia-seed/configuration.json
    cp -R /ssl/smarthome/authelia-seed/. /config/
fi
test -s /config/configuration.json
authelia validate-config --config /config/configuration.json
# The directory is on a separate host and may boot later than HA. Retain all
# startup checks, but recover when LDAP returns instead of exhausting Supervisor's
# rapid restart limit and requiring a manual start.
child=
terminate() {
    trap - TERM INT
    test -z "$child" || kill -TERM "$child" 2>/dev/null || true
    test -z "$child" || wait "$child" 2>/dev/null || true
    exit 0
}
trap terminate TERM INT
while :; do
    authelia --config /config/configuration.json &
    child=$!
    if wait "$child"; then exit 0; fi
    echo 'Authelia exited; retrying in 30 seconds with all startup checks enabled.'
    sleep 30 &
    child=$!
    wait "$child" || true
done
