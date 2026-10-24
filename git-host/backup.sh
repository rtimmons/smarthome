#!/bin/sh
# QNAP host-owned scheduler. No Docker socket or private identity is put in Forgejo.
set -eu
root=/share/Container/home-git
output=/share/Usenet/Backups/automatic/forgejo
pkg=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
docker="$pkg/bin/docker"
test -x "$docker" || docker="$pkg/usr/bin/docker"
export DOCKER_CONFIG=/share/Container/usenet/state/docker-client
image=usenet-catalog-tools:rclone-1.75.1-python-3.14.7
worker() {
  "$docker" run --rm --network none --user 1004:100 --read-only --cap-drop ALL \
    --security-opt no-new-privileges --memory 256m --cpus 0.5 \
    --mount "type=bind,src=$root,dst=/source,readonly" \
    --mount "type=bind,src=$output,dst=/backups/forgejo" \
    --mount type=bind,src=/share/Container/usenet/bin/age,dst=/age,readonly \
    --mount type=bind,src=/share/Container/usenet/config/backup/recipient.pub,dst=/recipient.pub,readonly \
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
    --entrypoint python3 "$image" /source/backup.py "$@"
}
if test "${1:-}" = check; then worker check; exit; fi
mkdir "$root/backup.lock" || { echo 'Backup lock exists; inspect before retrying.' >&2; exit 1; }
resume=false
cleanup() {
  result=$?
  trap - EXIT
  if test "$resume" = true; then
    if "$docker" start home-git-forgejo-1 >/dev/null; then
      rm -f "$root/backup-resume-required"
    else
      result=1
    fi
  fi
  rmdir "$root/backup.lock"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if test -e "$root/backup-resume-required"; then
  "$docker" start home-git-forgejo-1 >/dev/null
  rm "$root/backup-resume-required"
fi
# Load and validate the worker before stopping Forgejo, including forced runs.
result=0
worker due || result=$?
if test "$result" = 10; then
  if test "${1:-}" != force; then exit 0; fi
else
  test "$result" = 0
fi
# Retry an already captured archive before taking another snapshot.
if test ! -e "$output/pending.json"; then
  test "$("$docker" inspect --format '{{.State.Running}}' home-git-forgejo-1)" = true
  touch "$root/backup-resume-required"
  resume=true
  "$docker" stop --time 60 home-git-forgejo-1 >/dev/null
  test "$("$docker" inspect --format '{{.State.Running}}' home-git-forgejo-1)" = false
  worker capture
  "$docker" start home-git-forgejo-1 >/dev/null
  rm "$root/backup-resume-required"
  resume=false
fi
# Existing confined off-host credentials stay in the backup service's read-only mount.
"$docker" exec -i usenet-backups-backups-1 python3 - publish < "$root/backup.py"
worker check
