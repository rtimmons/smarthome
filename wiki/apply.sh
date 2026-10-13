#!/bin/sh
# Runs on QNAP. All runtime files remain versioned with their release.
set -eu
root=$1
mode=$2
release=$3
uid=$4
gid=$5
docker=$6
fail_smoke=${7:-false}
cd "$root"
mkdir .deploy-lock 2>/dev/null || { echo 'Another wiki deployment owns the lock.' >&2; exit 1; }
trap 'rmdir "$root/.deploy-lock"' EXIT HUP INT TERM

runtime_for() {
    runtime=$(sed -n 's/^WIKI_RUNTIME_DIR=//p' "$1")
    runtime=${runtime:-$root}
    case "$runtime" in "$root"|"$root"/releases/*/runtime) ;; *) echo 'Invalid runtime path' >&2; return 1;; esac
    test -f "$runtime/compose.yaml"
    printf '%s' "$runtime"
}

compose() {
    envfile=$1
    shift
    runtime=$(runtime_for "$envfile")
    "$docker" compose --ansi never --progress plain --project-directory "$runtime" \
        --file "$runtime/compose.yaml" --env-file "$root/$envfile" "$@"
}

smoke() {
    envfile=$1
    wiki_id=$("$docker" ps -q --filter label=com.docker.compose.project=usenet-wiki --filter label=com.docker.compose.service=wiki)
    test -n "$wiki_id" || return 1
    test "$("$docker" inspect --format '{{.State.Health.Status}}' "$wiki_id")" = healthy || return 1
    test "$("$docker" port "$wiki_id" 8090/tcp)" = '192.168.1.66:8090' || return 1
    expected=$(sed -n 's/^WIKI_RELEASE_DIR=//p' "$envfile")
    "$docker" inspect --format '{{range .Mounts}}{{println .Source}}{{end}}' "$wiki_id" | grep -Fx "$expected/site" >/dev/null || return 1
    if grep -q '^WIKI_RUNTIME_DIR=' "$envfile"; then
        test "$("$docker" port "$wiki_id" 8080/tcp)" = '192.168.1.66:80' || return 1
        "$docker" exec "$wiki_id" wget -q -O - http://127.0.0.1:8080/ | grep -F 'Smarthome field guide' >/dev/null || return 1
        actual=$("$docker" exec "$wiki_id" wget -q -O - http://127.0.0.1:8080/publication.json | sha256sum | cut -d ' ' -f 1)
        wanted=$(sha256sum "$expected/site/publication.json" | cut -d ' ' -f 1)
        test "$actual" = "$wanted" || return 1
    else
        "$docker" exec "$wiki_id" wget -q -O - http://127.0.0.1:8090/ | grep -F 'Usenet field guide' >/dev/null || return 1
    fi
}

restore() {
    if test -f .env.rollback; then
        cp -p .env.rollback .env.restored
        mv -f .env.restored .env
        compose .env up -d --wait --wait-timeout 90 --force-recreate wiki
        smoke .env
    else
        compose .env down --remove-orphans
        rm -f .env
    fi
}

if test "$mode" = rollback; then
    test -f .env.previous || { echo 'No previous release retained.' >&2; exit 1; }
    cp -p .env .env.rollback
    cp -p .env.previous .env.candidate
else
    case "$release" in *[!a-f0-9]*|'') echo 'Invalid release identity' >&2; exit 1;; esac
    candidate="$root/releases/$release"
    (cd "$candidate" && sha256sum -c SHA256SUMS >/dev/null)
    cat > .env.candidate <<EOF
WIKI_UID=$uid
WIKI_GID=$gid
WIKI_BIND_ADDRESS=192.168.1.66
WIKI_PORT=8090
WIKI_ROOT=$root
WIKI_RELEASE_DIR=$candidate
WIKI_RUNTIME_DIR=$candidate/runtime
EOF
    chmod 0600 .env.candidate
    compose .env.candidate config --quiet
    if ! "$docker" image inspect usenet-wiki:caddy-2.11.4-nonroot >/dev/null 2>&1; then
        compose .env.candidate build --pull wiki
    fi
    compose .env.candidate run --rm --no-deps --entrypoint caddy wiki validate --config /etc/caddy/Caddyfile --adapter caddyfile
    if test "$fail_smoke" != true && test -f .env && cmp -s .env .env.candidate && smoke .env; then
        echo 'Wiki already matches the healthy immutable release.'
        exit 0
    fi
    rm -f .env.rollback
    if test -f .env; then cp -p .env .env.rollback; fi
fi

cp -p .env.candidate .env.published
mv -f .env.published .env
if compose .env up -d --wait --wait-timeout 90 --force-recreate wiki && smoke .env && test "$fail_smoke" != true; then
    if test -f .env.rollback; then mv -f .env.rollback .env.previous; fi
    echo 'Wiki release accepted; prior release retained.'
else
    restore || { echo 'Wiki rollback failed; inspect only the wiki project immediately.' >&2; exit 2; }
    echo 'Wiki candidate rejected; previous release restored. No other QNAP service was changed.' >&2
    exit 1
fi
