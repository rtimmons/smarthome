#!/usr/bin/env python3
"""Operate the isolated NAS directory via the existing dedicated SSH identity."""
import argparse
import base64
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))/'tree/build/identity-private'
PRELUDE = '''set -eu
umask 077
pkg=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
docker="$pkg/bin/docker"; test -x "$docker" || docker="$pkg/usr/bin/docker"
export DOCKER_CONFIG=/share/Container/usenet/state/docker-client
root=/share/Container/home-identity
compose() { "$docker" compose -f "$root/compose.yaml" "$@"; }
'''

def connection():
    spec=importlib.util.spec_from_file_location('qnap',ROOT/'usenet-infra/scripts/qnap-recon.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.connection_command(os.environ)

def upload(path, data, mode='600'):
    encoded=base64.b64encode(data).decode()
    return f"printf '%s' '{encoded}' | base64 -d > \"$root/{path}.new\"\nchmod {mode} \"$root/{path}.new\"\nmv \"$root/{path}.new\" \"$root/{path}\"\n"

def payload(action):
    if action=='runtime':
        return r'''date -u
cat /proc/loadavg
awk '/MemTotal|MemAvailable|SwapTotal|SwapFree/ {print}' /proc/meminfo
if command -v vmstat >/dev/null 2>&1; then vmstat 1 3; fi
ps -eo pid,rss,stat,comm | sort -k2nr | head -16 || true
sample=$(mktemp -d /tmp/identity-runtime.XXXXXX)
trap 'rm -rf "$sample"' EXIT
process_ticks() {
 awk '{pid=$1; match($0,/\(.*\)/); name=substr($0,RSTART+1,RLENGTH-2); sub(/^.*\) /,""); split($0,fields," "); print pid,fields[12]+fields[13],name}' /proc/[0-9]*/stat 2>/dev/null || true
}
process_ticks > "$sample/before"
awk '/^cpu / {print}' /proc/stat
awk '/^pswpin |^pswpout |^pgmajfault / {print}' /proc/vmstat
sleep 2
process_ticks > "$sample/after"
awk 'NR==FNR {ticks[$1]=$2; next} $1 in ticks {delta=$2-ticks[$1]; if(delta>0) print delta,$1,$3}' "$sample/before" "$sample/after" | sort -nr | head -12
awk '/^cpu / {print}' /proc/stat
awk '/^pswpin |^pswpout |^pgmajfault / {print}' /proc/vmstat
'''+PRELUDE+'''
"$docker" ps --format '{{.Names}} {{.Status}}'
'''
    if action=='vm-check':
        return PRELUDE+'''test ! -e /dev/kvm || ls -l /dev/kvm
grep -m1 -oE 'vmx|svm' /proc/cpuinfo || true
for package in QKVM VirtualizationStation; do
 printf '%s: ' "$package"
 /sbin/getcfg "$package" Install_Path -f /etc/config/qpkg.conf || true
done
df -h /share/Container
awk '/MemTotal|MemAvailable|SwapTotal|SwapFree/ {print}' /proc/meminfo
for command in virsh qemu-img qemu-system-x86_64; do command -v "$command" || true; done
for directory in /share/CACHEDEV1_DATA/.qpkg/QKVM /share/Container/home-identity/vm; do
 test ! -d "$directory" || ls -ld "$directory"
done
test ! -d /share/Container/home-identity/vm || ls -lh /share/Container/home-identity/vm
qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf || true)
test -n "$qkvm" || qkvm=/share/CACHEDEV1_DATA/.qpkg/QKVM
if test -n "$qkvm" && test -d "$qkvm"; then
 find "$qkvm" -maxdepth 4 -type f \\( -name virsh -o -name qemu-img -o -name '*cli*' \\) -print | head -40
 LD_LIBRARY_PATH="$qkvm/usr/lib" "$qkvm/usr/bin/qemu-img" --version || true
 for disk in "$root/vm/ubuntu-base.img" "$root/vm/dc1.img.new"; do
  test ! -f "$disk" || LD_LIBRARY_PATH="$qkvm/usr/lib" "$qkvm/usr/bin/qemu-img" info --output=json "$disk" || true
 done
 "$qkvm/usr/bin/virsh" -c qemu:///system list --all || true
 find "$qkvm" -maxdepth 5 -name 'libgnutls.so*' -print
 ls -ld /QVS /QVS/var/run/libvirt 2>/dev/null || true
 find "$qkvm/var/log" -maxdepth 2 -type f -name '*.log' -print | head -25
 grep -RnE 'killall.*qemu|pkill.*qemu' "$qkvm" --include='*.sh' 2>/dev/null | head -15 || true
fi
ps -eo pid,ppid,stat,comm | grep -E 'qemu|qvs|virt|python|unzip|7z|tar|qpkg|install' | head -50 || true
dmesg | grep -E 'Out of memory|Killed process|oom-kill|qemu-img' | tail -15 || true
id
if command -v sudo >/dev/null 2>&1; then sudo -n true && echo 'Noninteractive administrator sudo available' || true; fi
'''
    if action=='build':
        result=PRELUDE+'mkdir -p "$root/source"\n'
        for name in ('Dockerfile','provision.py','run.sh'):
            result+=upload('source/'+name,(ROOT/'identity-infra'/name).read_bytes(),'700' if name=='run.sh' else '600')
        return result+'"$docker" build --memory 768m -t smarthome-samba-ad:20261024 "$root/source"\n'
    if action=='vm-disk':
        return PRELUDE+'''qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
export LD_LIBRARY_PATH="$qkvm/usr/lib"
image="$qkvm/usr/bin/qemu-img"
directory="$root/vm"
test -s "$directory/cidata.iso"
echo '5645d0318ad21f643ebb1ac4567514620e9893380b07b0201fda163baa5b7eb5  '"$directory/ubuntu-base.img" | sha256sum -c -
chmod 600 "$directory/ubuntu-base.img"
test ! -e "$directory/dc1.img"
test ! -e "$directory/dc1.img.new"
"$image" convert -f qcow2 -O qcow2 "$directory/ubuntu-base.img" "$directory/dc1.img.new"
"$image" resize -f qcow2 "$directory/dc1.img.new" 8G
"$image" check -f qcow2 "$directory/dc1.img.new"
chmod 600 "$directory/dc1.img.new"
mv "$directory/dc1.img.new" "$directory/dc1.img"
"$image" info --output=json "$directory/dc1.img"
'''
    if action=='vm-app-log':
        return PRELUDE+'''qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
for key in Enable Version WebUI Web_Port; do
 printf '%s: ' "$key"; /sbin/getcfg QKVM "$key" -f /etc/config/qpkg.conf || true
done
for file in "$qkvm/var/log/qvs-manage.log" "$qkvm/var/log/qvs_conf.log" "$qkvm/var/log/libvirt/libvirtd.log"; do
 test ! -r "$file" || tail -n 35 "$file"
done
'''
    if action=='vm-inspect':
        return PRELUDE+'''qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
virsh="$qkvm/usr/bin/virsh"
"$virsh" -c qemu:///system list --all
for domain in $("$virsh" -c qemu:///system list --all --uuid); do
 "$virsh" -c qemu:///system dominfo "$domain"
 "$virsh" -c qemu:///system domiflist "$domain"
 "$virsh" -c qemu:///system domblklist "$domain"
 "$virsh" -c qemu:///system domdisplay "$domain" --all || true
 "$virsh" -c qemu:///system ttyconsole "$domain" || true
 "$virsh" -c qemu:///system domblkstat "$domain" vda || true
 "$virsh" -c qemu:///system dommemstat "$domain" || true
 "$virsh" -c qemu:///system domifaddr "$domain" --source agent || true
done
'''
    if action=='vm-disk-check':
        instance = json.loads((PRIVATE/'vm/instance.json').read_text())
        identifier = str(uuid.UUID(instance['uuid']))
        return PRELUDE+'''qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
export LD_LIBRARY_PATH="$qkvm/usr/lib"
test "$("$qkvm/usr/bin/virsh" -c qemu:///system domstate '''+identifier+''')" = 'shut off'
ulimit -v 524288
"$qkvm/usr/bin/qemu-img" check -f qcow2 "$root/vm/dc1.img"
'''
    if action=='vm-start-preparation':
        instance = json.loads((PRIVATE/'vm/instance.json').read_text())
        if instance.get('directory_migrated') is not False:
            raise RuntimeError('Preparation commands cannot start a migrated directory')
        identifier = str(uuid.UUID(instance['uuid']))
        return PRELUDE+'''test ! -e "$root/vm-cutover.json"
qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
test "$("$qkvm/usr/bin/virsh" -c qemu:///system domstate '''+identifier+''')" = 'shut off'
"$qkvm/usr/bin/virsh" -c qemu:///system start '''+identifier+'''
'''
    if action=='vm-storage-access':
        return PRELUDE+'''test "$(stat -c %u "$root")" = 1004
test "$(stat -c %u "$root/vm")" = 1004
test -s "$root/vm/dc1.img"
test -s "$root/vm/cidata.iso"
# QVS's folder picker impersonates the signed-in local administrator. Only the
# existing NAS administrators gain traversal and VM-file access; private AD
# state and credential subdirectories retain their original restrictive modes.
chgrp administrators "$root" "$root/vm" "$root/vm/dc1.img" "$root/vm/cidata.iso"
chmod 750 "$root"
chmod 770 "$root/vm"
chmod 660 "$root/vm/dc1.img"
chmod 640 "$root/vm/cidata.iso"
ls -ld "$root" "$root/vm" "$root/dc-state" "$root/secrets"
'''
    if action=='vm-finish-disk':
        return PRELUDE+'''qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
export LD_LIBRARY_PATH="$qkvm/usr/lib"
image="$qkvm/usr/bin/qemu-img"
directory="$root/vm"
test ! -e "$directory/dc1.img"
test -f "$directory/dc1.img.new"
ulimit -v 524288
if "$image" check -f qcow2 "$directory/dc1.img.new"; then
 :
else
 status=$?
 test "$status" = 3
 # Only reclaim leaked, unreferenced clusters in this unstarted OS image.
 # Any structural corruption fails closed; the immutable source stays intact.
 "$image" check -r leaks -f qcow2 "$directory/dc1.img.new"
fi
"$image" compare -f qcow2 -F qcow2 "$directory/ubuntu-base.img" "$directory/dc1.img.new"
"$image" resize --preallocation=off -f qcow2 "$directory/dc1.img.new" 8G
"$image" check -f qcow2 "$directory/dc1.img.new"
chmod 600 "$directory/dc1.img.new"
mv "$directory/dc1.img.new" "$directory/dc1.img"
"$image" info --output=json "$directory/dc1.img"
'''
    if action=='address-check':
        return PRELUDE+'"$docker" run --rm --network host --entrypoint arping smarthome-samba-ad:20261024 -D -I eth0 -c 3 -w 5 192.168.1.10\n'
    if action=='provision-check':
        return PRELUDE+'''"$docker" run -i --rm --network none --hostname dc1 --memory 768m --cpus 1 --tmpfs /data:rw --tmpfs /run/secrets:rw --entrypoint /bin/sh smarthome-samba-ad:20261024 -es <<'CHECK'
python3 -c 'import secrets; from pathlib import Path; Path("/run/secrets/domain-admin").write_text(secrets.token_urlsafe(48))'
python3 /usr/local/libexec/provision.py
python3 /usr/local/libexec/provision.py
samba-tool dbcheck -s /data/etc/smb.conf
samba-tool ntacl sysvolcheck -s /data/etc/smb.conf
CHECK
'''
    if action=='deploy':
        result=PRELUDE+'''test ! -L "$root"
test ! -e "$root/vm-cutover.json" || { echo 'Directory VM cutover recorded; refusing to start the retired container'; exit 1; }
test ! -e "$root/ha-cutover.json" || { echo 'HA directory cutover recorded; refusing to start the retired container'; exit 1; }
test ! -d /share/Container/usenet/dns/.automatic-deploy-lock || { echo 'DNS deployment in progress; retry AD deployment after it finishes'; exit 1; }
mkdir -p "$root/dc-state" "$root/tls" "$root/secrets"
chmod 700 "$root" "$root/dc-state" "$root/tls" "$root/secrets"
cert_changed=0
'''
        # Reuse exact credentials on repeat; never replace an existing credential.
        for name in ('domain-admin','dc.key','dc.crt','dc-chain.crt','ca.crt'):
            source=PRIVATE/('secrets' if name=='domain-admin' else 'tls')/name
            target=('secrets/' if name=='domain-admin' else 'tls/')+name
            data=source.read_bytes()
            digest=hashlib.sha256(data).hexdigest()
            if name in ('dc.crt','dc-chain.crt'):
                result+=f'''test ! -L "$root/{target}"
if test ! -e "$root/{target}" || test "$(sha256sum "$root/{target}" | cut -d ' ' -f 1)" != '{digest}'; then
 if test -e "$root/{target}"; then cp "$root/{target}" "$root/{target}.previous"; cert_changed=1; fi
'''+upload(target,data)+'fi\n'
                continue
            result+=f'''if test -L "$root/{target}"; then echo 'Refusing symlinked credential'; exit 1; fi
if test -e "$root/{target}"; then
 test "$(sha256sum "$root/{target}" | cut -d ' ' -f 1)" = '{digest}' || {{ echo 'Existing credential differs; refusing replacement'; exit 1; }}
else
'''+upload(target,data)+'fi\n'
        result+=upload('compose.yaml',(ROOT/'identity-infra/compose.yaml').read_bytes())
        return result+'''compose config --quiet
compose up -d --wait --wait-timeout 600
if test "$cert_changed" = 1; then compose restart dc; compose up -d --wait --wait-timeout 120; fi
'''
    if action in ('principals', 'resume-principals'):
        bootstrap = {'ldap_bind': (PRIVATE/'secrets/ldap-bind').read_text().strip()}
        if action == 'resume-principals':
            bootstrap['resume_created_identity'] = True
        script = 'bootstrap = '+repr(bootstrap)+'\n'+(ROOT/'identity-infra/principals.py').read_text()
        return PRELUDE+'"$docker" exec -i home-identity-dc-1 python3 - <<\'PRINCIPALS\'\n'+script+'\nPRINCIPALS\n'
    if action=='verify':
        bootstrap = {name.replace('-','_'): (PRIVATE/'secrets'/source).read_text().strip()
                     for name, source in [('ldap-bind','ldap-bind'),('domain-admin','domain-admin')]}
        script = 'bootstrap = '+repr(bootstrap)+'\n'+(ROOT/'identity-infra/check_directory.py').read_text()
        return PRELUDE+'"$docker" exec -i home-identity-dc-1 python3 - <<\'VERIFY\'\n'+script+'\nVERIFY\n'
    if action=='verify-household':
        bootstrap = json.loads((PRIVATE/'human-logins.json').read_text())
        script = 'bootstrap = '+repr(bootstrap)+'\n'+(ROOT/'identity-infra/check_household.py').read_text()
        return PRELUDE+'"$docker" exec -i home-identity-dc-1 python3 - <<\'VERIFY\'\n'+script+'\nVERIFY\n'
    if action=='diagnose':
        return PRELUDE+'''"$docker" inspect --format '{{json .State}}' home-identity-dc-1
"$docker" inspect --format '{{json .NetworkSettings.Networks}}' home-identity-dc-1
"$docker" logs --tail 50 home-identity-dc-1
"$docker" stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' home-identity-dc-1
'''
    if action=='backup-help':
        return PRELUDE+'''"$docker" exec home-identity-dc-1 samba-tool domain backup offline --help
"$docker" exec home-identity-dc-1 samba-tool domain backup restore --help
'''
    if action=='backup-log':
        return PRELUDE+'"$docker" exec home-identity-dc-1 tail -n 55 /data/backups/verification.log\n'
    if action=='network-check':
        return PRELUDE+'''ip -o link show
brctl show
"$docker" network inspect home-identity_directory
"$docker" exec home-identity-dc-1 cat /sys/class/net/eth0/address
'''
    if action=='qnap-domain-status':
        return PRELUDE+'''for key in security realm workgroup; do
 printf '%s: ' "$key"
 /sbin/getcfg global "$key" -f /etc/config/smb.conf || true
done
if test -x /usr/local/samba/bin/wbinfo; then
 /usr/local/samba/bin/wbinfo --online-status
 /usr/local/samba/bin/wbinfo --check-secret
fi
'''
    if action=='qnap-join-log':
        return PRELUDE+'''for pattern in /tmp/*join* /tmp/*smb* /tmp/*domain* /var/log/*smb* /share/CACHEDEV1_DATA/.samba/var/log.winbind*; do
 test -f "$pattern" || continue
 ls -l "$pattern"
 case "$pattern" in */log.winbindd|*/setup_smb.debug|*/join_ad_progress.conf) tail -n 50 "$pattern";; esac
done
'''
    if action=='qnap-discovery':
        return PRELUDE+'''date -u
"$docker" inspect --format 'DC restarts={{.RestartCount}} started={{.State.StartedAt}} status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}' home-identity-dc-1
test ! -f /etc/init.d/smb.sh || grep -nE 'killall|pkill|kill_smb|stop_samba' /etc/init.d/smb.sh || true
for file in /etc/resolv* /etc/config/resolv* /etc/config/dnsmasq*; do
 test ! -f "$file" || { printf '%s\\n' "$file"; cat "$file"; }
done
for file in /etc/krb5.conf /etc/config/krb5.conf; do
 test ! -f "$file" || { printf '%s\\n' "$file"; cat "$file"; }
done
/usr/local/samba/bin/net ads info -S dc1.ad.home.arpa --realm=AD.HOME.ARPA || true
/usr/local/samba/bin/net lookup dc ad.home.arpa || true
/usr/local/samba/bin/net time -S 192.168.1.10 || true
"$docker" exec home-identity-dc-1 samba-tool computer list -s /data/etc/smb.conf
"$docker" exec home-identity-dc-1 date -u
'''
    if action=='acl-check':
        return PRELUDE+'''"$docker" exec -i home-identity-dc-1 python3 - <<'CHECK'
from pathlib import Path
import os, tempfile
print(Path('/data/etc/smb.conf').read_text())
print('SYSVOL xattrs:', os.listxattr('/data/state/sysvol'))
for directory in ('/tmp', '/data/backups'):
    with tempfile.NamedTemporaryFile(dir=directory) as sample:
        for attribute in ('user.identity-test', 'security.NTACL'):
            try:
                os.setxattr(sample.name, attribute, b'synthetic')
                print(directory, attribute, 'supported')
            except OSError as error:
                print(directory, attribute, 'error', error.errno)
CHECK
'''
    if action=='host-check':
        return PRELUDE+'''cat /etc/resolv.conf
ip route get 192.168.1.10
awk '$1 == "192.168.1.10" {print}' /proc/net/arp
"$docker" run --rm --network host --entrypoint /bin/sh smarthome-samba-ad:20261024 -ec '
dig @192.168.1.10 +time=3 +tries=1 +short SRV _ldap._tcp.ad.home.arpa
dig @127.0.1.1 +time=3 +tries=1 +short SRV _ldap._tcp.ad.home.arpa
dig @127.0.1.1 +time=3 +tries=1 +short A dc1.ad.home.arpa
ldapsearch -x -LLL -o nettimeout=5 -H ldap://192.168.1.10 -b "" -s base defaultNamingContext
dig @192.168.1.10 +time=3 +tries=1 +short example.com
'
'''
    if action=='repair-sysvol':
        script = (ROOT/'identity-infra/repair_sysvol.py').read_text()
        return PRELUDE+'"$docker" exec -i home-identity-dc-1 python3 - <<\'REPAIR\'\n'+script+'\nREPAIR\n'+'''compose restart dc
compose up -d --wait --wait-timeout 120
'''
    if action=='status':
        return PRELUDE+'''compose ps
"$docker" exec home-identity-dc-1 samba-tool domain level show -s /data/etc/smb.conf
"$docker" exec home-identity-dc-1 samba-tool dbcheck -s /data/etc/smb.conf
"$docker" exec home-identity-dc-1 dig @127.0.0.1 +short SRV _kerberos._tcp.ad.home.arpa
'''
    raise ValueError(action)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    local = {'pki':'pki.py', 'seal':'seal.py', 'render-authelia':'render_authelia.py',
             'stage-authelia':'stage_authelia.py', 'stage-web':'stage_web.py', 'backup':'backup_directory.py',
             'inventory':'inventory.py', 'dreamhost-key':'configure_dns_key.py', 'stage-acme':'stage_acme.py'}
    local['backup-ha'] = 'backup_ha.py'
    local['prepare-catalog'] = 'prepare_catalog.py'
    local['deploy-catalog'] = 'deploy_catalog.py'
    local['jellyfin-directory'] = 'jellyfin_directory.py'
    local['migrate-jellyfin'] = 'migrate_jellyfin.py'
    local['verify-jellyfin'] = 'verify_jellyfin.py'
    local['backup-jellyfin'] = 'backup_jellyfin.py'
    local['arr-gateway'] = 'arr_gateway.py'
    local['escrow-app-keys'] = 'capture_app_keys.py'
    local['migrate-arr'] = 'migrate_arr.py'
    local['verify-authelia-backup'] = 'verify_authelia_backup.py'
    local['gmail-smtp'] = 'configure_smtp.py'
    local['cleanup-ha-seeds'] = 'cleanup_ha_seeds.py'
    local['cleanup-directory-seed'] = 'cleanup_directory_seed.py'
    local['users'] = 'create_users.py'
    local['vm-prepare'] = 'vm_prepare.py'
    local['vm-repair-bootstrap'] = 'repair_vm_bootstrap.py'
    local['stage-ha-directory'] = 'stage_ha_directory.py'
    local['ha-directory-check'] = 'ha_directory.py'
    local['ha-restore-trial'] = 'ha_restore_trial.py'
    local['ha-native-restore-trial'] = 'ha_native_restore_trial.py'
    local['verify-smb'] = 'check_smb.py'
    local['migrate-to-ha'] = 'migrate_to_ha.py'
    local['vm-guest-status'] = 'vm_guest.py'
    parser.add_argument('action',choices=('build','address-check','provision-check','deploy','status','qnap-backup','runtime','vm-check','vm-disk','vm-app-log','vm-storage-access','vm-finish-disk','vm-inspect','vm-disk-check','vm-start-preparation','principals','resume-principals','diagnose','verify','verify-household','backup-help','backup-log','acl-check','network-check','qnap-domain-status','qnap-join-log','qnap-discovery','repair-sysvol','host-check',*local))
    parser.add_argument('--email', help='Approved email for first household-user creation')
    parser.add_argument('--host', help='Explicit temporary LAN address of the prepared VM')
    parser.add_argument('--post-ad', action='store_true', help='Keep a separate post-migration Jellyfin snapshot')
    parser.add_argument('--apply', action='store_true', help='Apply the prepared Catalog update after its idle check')
    args=parser.parse_args()
    if (PRIVATE/'ha-cutover.json').exists() and args.action in (
            'vm-prepare', 'vm-repair-bootstrap', 'vm-disk', 'vm-storage-access',
            'vm-finish-disk', 'vm-start-preparation'):
        raise RuntimeError('NAS VM trial retired after HA cutover; do not recreate or start it')
    if args.action == 'users' and not args.email:
        parser.error('users requires --email')
    if args.email and args.action != 'users':
        parser.error('--email applies only to users')
    if bool(args.host) != (args.action == 'vm-guest-status'):
        parser.error('--host is required only for vm-guest-status')
    if args.post_ad and args.action != 'backup-jellyfin':
        parser.error('--post-ad applies only to backup-jellyfin')
    if args.apply and args.action != 'deploy-catalog':
        parser.error('--apply applies only to deploy-catalog')
    if args.action in local:
        extra = ['--email', args.email] if args.action == 'users' else []
        if args.action == 'vm-guest-status':
            extra = ['--host', args.host]
        if args.action == 'deploy-catalog' and args.apply:
            extra = ['--apply']
        if args.action == 'backup-jellyfin' and args.post_ad:
            extra = ['--post-ad']
        return subprocess.run([sys.executable, str(ROOT/'identity-infra'/local[args.action]), *extra]).returncode
    if args.action == 'qnap-backup':
        from qnap_backup import main as backup
        backup()
        return 0
    target = PRIVATE/'ha-cutover.json'
    on_ha = target.exists() and json.loads(target.read_text()).get('phase') in ('activated', 'verified')
    if target.exists() and args.action in ('deploy', 'repair-sysvol', 'principals', 'resume-principals'):
        raise RuntimeError('Directory migration recorded; use the HA app workflow, never restart or reprovision the NAS copy')
    if on_ha and args.action in ('status', 'verify', 'verify-household'):
        from ha_directory import execute
        if args.action == 'status':
            script = '''set -eu
samba-tool domain level show -s /data/etc/smb.conf
samba-tool dbcheck -s /data/etc/smb.conf
dig @127.0.0.1 +short SRV _kerberos._tcp.ad.home.arpa
'''
        else:
            original = payload(args.action)
            prefix = PRELUDE+'"$docker" exec -i home-identity-dc-1 '
            if not original.startswith(prefix):
                raise RuntimeError('Unexpected directory verification wrapper')
            script = 'set -eu\n'+original.removeprefix(prefix)
        result = execute(script.encode(), timeout=180)
        log = PRIVATE/(args.action+'.log')
        log.write_bytes(result.stdout+result.stderr)
        print(f'{args.action} on HA: exit {result.returncode}; private log: {log}')
        return result.returncode
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    log=PRIVATE/(args.action+'.log')
    fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as out:
        result=subprocess.run(connection(),input=payload(args.action).encode(),stdout=out,stderr=subprocess.STDOUT,timeout=1800)
    print(f'{args.action}: exit {result.returncode}; private log: {log}')
    return result.returncode

if __name__=='__main__':raise SystemExit(main())
