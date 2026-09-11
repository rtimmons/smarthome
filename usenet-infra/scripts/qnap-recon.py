#!/usr/bin/env python3
"""Read-only QNAP reconnaissance through the dedicated, already-pinned SSH identity.

Requires QNAP_SSH_TARGET, QNAP_SSH_KEY and QNAP_SSH_KNOWN_HOSTS. No selected
application/share path or NAS Python installation is needed. Never scans host
keys, prompts for passwords, retries another identity, or changes the NAS.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import stat
import subprocess


PAYLOAD = r'''#!/bin/sh
# Every command below reads metadata; raw Docker/configuration output is never
# forwarded. Base64 framing prevents names from being interpreted as records.
emit() {
    printf '%s\t' "$1"
    printf '%s' "$2" | base64 | tr -d '\r\n'
    printf '\n'
}
emit kernel "$(uname -srm 2>/dev/null)"
emit page_size "$(getconf PAGESIZE 2>/dev/null)"
emit uid "$(id -u 2>/dev/null)"
emit gid "$(id -g 2>/dev/null)"
emit group_ids "$(id -G 2>/dev/null)"
emit groups "$(id -Gn 2>/dev/null)"
if test -x /sbin/getcfg; then
    emit model "$(/sbin/getcfg System Model -f /etc/config/uLinux.conf 2>/dev/null)"
    emit firmware "$(/sbin/getcfg System Version -f /etc/config/uLinux.conf 2>/dev/null)"
    emit firmware_build "$(/sbin/getcfg System 'Build Number' -f /etc/config/uLinux.conf 2>/dev/null)"
    emit platform "$(/sbin/getcfg System 'Platform Name' -f /etc/config/uLinux.conf 2>/dev/null)"
    emit container_station "$(/sbin/getcfg container-station Version -f /etc/config/qpkg.conf 2>/dev/null)"
    emit hybridmount_versions "$(sed -n 's/^\[\(.*\)\][[:space:]]*$/\1/p' /etc/config/qpkg.conf |
      while IFS= read -r package; do
        display=$(/sbin/getcfg "$package" Display_Name -f /etc/config/qpkg.conf 2>/dev/null)
        if test "$display" = HybridMount || test "$package" = HybridMount; then
          printf '%s\t' "$package"
          /sbin/getcfg "$package" Version -f /etc/config/qpkg.conf 2>/dev/null
        fi
      done)"
    # QNAP does not add Container Station tools to noninteractive SSH PATH.
    # Use only its configured installation root, without printing package config.
    container_install=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf 2>/dev/null)
    case "$container_install" in
        /share/*) emit container_install_path "$container_install"; PATH="$container_install/bin:$container_install/usr/bin:$PATH"; export PATH ;;
    esac
fi
if test -r /etc/os-release; then
    emit os_identity "$(sed -n '/^PRETTY_NAME=/p; /^ID=/p; /^VERSION_ID=/p' /etc/os-release 2>/dev/null)"
fi
emit memory "$(awk '/^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree):/ {print $1, $2}' /proc/meminfo 2>/dev/null)"
emit load "$(awk '{print $1, $2, $3}' /proc/loadavg 2>/dev/null)"
emit mounts "$(awk '($2 == "/" || (index($2,"/share/") == 1 && split($2,p,"/") == 3)) {print $2 "\t" $3}' /proc/mounts 2>/dev/null)"
if command -v ip >/dev/null 2>&1; then
    emit network_ipv4 "$(ip -o -4 address show 2>/dev/null | awk '{print $2 "\t" $4}')"
    emit default_routes "$(ip -4 route show default 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i == "dev" || $i == "src") print $i "\t" $(i+1)}')"
    emit global_ipv6_address_count "$(ip -o -6 address show scope global 2>/dev/null | awk 'END {print NR}')"
fi
if command -v ss >/dev/null 2>&1; then
    emit dashboard_port_listeners "$(ss -ltn 2>/dev/null | awk '$4 ~ /:1337$/ {print $4}')"
    emit dashboard_port_checked yes
elif command -v netstat >/dev/null 2>&1; then
    emit dashboard_port_listeners "$(netstat -ltn 2>/dev/null | awk '$4 ~ /:1337$/ {print $4}')"
    emit dashboard_port_checked yes
fi
if command -v docker >/dev/null 2>&1; then
    emit docker_executable "$(command -v docker)"
    emit docker_client "$(docker --version 2>/dev/null)"
    emit docker_info "$(docker info --format '{"server_version":{{json .ServerVersion}},"architecture":{{json .Architecture}},"operating_system":{{json .OperatingSystem}},"kernel_version":{{json .KernelVersion}},"cpus":{{json .NCPU}},"memory_bytes":{{json .MemTotal}},"storage_driver":{{json .Driver}},"root_directory":{{json .DockerRootDir}},"containers":{{json .Containers}},"running_containers":{{json .ContainersRunning}},"memory_limit_supported":{{json .MemoryLimit}},"swap_limit_supported":{{json .SwapLimit}}}' 2>/dev/null)"
    emit docker_compose "$(docker compose version 2>/dev/null)"
    emit containers "$(docker ps -a --format '{"name":{{json .Names}},"status":{{json .Status}}}' 2>/dev/null)"
    if stats=$(docker stats --no-stream --format '{"name":{{json .Name}},"cpu_percent":{{json .CPUPerc}},"memory":{{json .MemUsage}},"memory_percent":{{json .MemPerc}},"pids":{{json .PIDs}},"network_io":{{json .NetIO}},"block_io":{{json .BlockIO}}}' 2>/dev/null); then
        emit container_stats_available yes
        emit container_stats "$stats"
    else
        emit container_stats_available no
    fi
    # Inspect only our named Compose project, selecting fields before output.
    # Never return Config.Env, command lines, healthcheck output or credentials.
    emit deployed_containers "$(for container_id in $(docker ps -aq --filter label=com.docker.compose.project=usenet-cache 2>/dev/null); do
      docker inspect --format '{"name":{{json .Name}},"user":{{json .Config.User}},"running":{{json .State.Running}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},"read_only_root":{{json .HostConfig.ReadonlyRootfs}},"privileged":{{json .HostConfig.Privileged}},"network_mode":{{json .HostConfig.NetworkMode}},"group_add":{{json .HostConfig.GroupAdd}},"cap_drop":{{json .HostConfig.CapDrop}},"security_options":{{json .HostConfig.SecurityOpt}},"port_bindings":{{json .HostConfig.PortBindings}},"memory_limit_bytes":{{json .HostConfig.Memory}},"mounts":[{{range $i,$mount := .Mounts}}{{if $i}},{{end}}{"source":{{json $mount.Source}},"target":{{json $mount.Destination}},"writable":{{json $mount.RW}}}{{end}}]}' "$container_id" 2>/dev/null
    done)"
    if test "$(docker inspect --format '{{.State.Running}}' usenet-cache-dashboard-1 2>/dev/null)" = true; then
      emit dashboard_runtime "$(docker exec usenet-cache-dashboard-1 python3 -c 'import json,os; print(json.dumps({"uid":os.getuid(),"gid":os.getgid(),"groups":os.getgroups(),"page_size":os.sysconf("SC_PAGE_SIZE")}))' 2>/dev/null)"
    fi
    emit iperf_baseline "$(docker inspect --format '{"name":{{json .Name}},"running":{{json .State.Running}},"started_at":{{json .State.StartedAt}},"restart_count":{{json .RestartCount}}}' iperf3-1 2>/dev/null)"
fi
if command -v docker-compose >/dev/null 2>&1; then
    emit legacy_compose "$(docker-compose version --short 2>/dev/null)"
fi
if test -x /sbin/getcfg && test -r /etc/config/smb.conf; then
    # Inspect only configured share roots, never files beneath them. The raw
    # SMB configuration, mount sources/options and Docker environment are not read out.
    sed -n 's/^\[\(.*\)\][[:space:]]*$/\1/p' /etc/config/smb.conf |
    head -n 128 |
    while IFS= read -r share; do
        test "$share" = global && continue
        share_path=$(/sbin/getcfg "$share" path -f /etc/config/smb.conf 2>/dev/null)
        case "$share_path" in /share/*) ;; *) continue ;; esac
        ownership=$(stat -L -c '%u %g %a' "$share_path" 2>/dev/null)
        capacity=$(df -Pk "$share_path" 2>/dev/null | awk 'NR == 2 && $2 ~ /^[0-9]+$/ && $4 ~ /^[0-9]+$/ {print $2, $3, $4}')
        filesystem=$(stat -f -c '%T' "$share_path" 2>/dev/null)
        emit share_name "$share"
        emit share_path "$share_path"
        emit share_ownership "$ownership"
        emit share_capacity "$capacity"
        emit share_filesystem "$filesystem"
    done
fi
emit complete yes
'''

TEXT_FIELDS = {'kernel', 'model', 'firmware', 'firmware_build', 'platform', 'container_station',
               'container_install_path', 'docker_executable', 'os_identity', 'docker_client',
               'docker_compose', 'legacy_compose', 'groups'}
INFO_FIELDS = {'server_version', 'architecture', 'operating_system', 'kernel_version', 'cpus',
               'memory_bytes', 'storage_driver', 'root_directory', 'containers', 'running_containers',
               'memory_limit_supported', 'swap_limit_supported'}
STAT_FIELDS = {'name', 'cpu_percent', 'memory', 'memory_percent', 'pids', 'network_io', 'block_io'}


class ReconError(RuntimeError):
    """Fixed messages only; connection stderr and arbitrary input stay private."""


def integer(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def memory_bytes(value: str) -> int:
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(B|kB|KB|KiB|MB|MiB|GB|GiB|TB|TiB)', value.strip())
    if not match:
        raise ValueError('unsupported size')
    scale = {'B': 1, 'kB': 1000, 'KB': 1000, 'KiB': 1024, 'MB': 1000**2, 'MiB': 1024**2,
             'GB': 1000**3, 'GiB': 1024**3, 'TB': 1000**4, 'TiB': 1024**4}[match[2]]
    return int(float(match[1]) * scale)


def parse_output(output: bytes) -> dict:
    if len(output) > 2 * 1024**2:
        raise ReconError('reconnaissance_output_exceeded_limit')
    rows = []
    allowed = TEXT_FIELDS | {'page_size', 'uid', 'gid', 'group_ids', 'memory', 'load', 'mounts',
                            'docker_info', 'containers', 'container_stats', 'container_stats_available', 'complete', 'share_name',
                            'network_ipv4', 'default_routes', 'dashboard_port_listeners', 'dashboard_port_checked',
                            'hybridmount_versions', 'global_ipv6_address_count', 'deployed_containers',
                            'dashboard_runtime', 'iperf_baseline',
                            'share_path', 'share_ownership', 'share_capacity', 'share_filesystem'}
    for line in output.decode().splitlines():
        key, separator, encoded = line.partition('\t')
        if not separator or key not in allowed:
            raise ReconError('unexpected_remote_output_not_displayed')
        rows.append((key, base64.b64decode(encoded, validate=True).decode()))
    if not rows or rows[-1] != ('complete', 'yes'):
        raise ReconError('reconnaissance_did_not_complete')
    single = {}
    shares = []
    current_share = None
    for key, value in rows:
        if key.startswith('share_'):
            if key == 'share_name':
                current_share = {'name': value}
                shares.append(current_share)
            elif current_share is None:
                raise ReconError('unexpected_share_metadata')
            else:
                current_share[key.removeprefix('share_')] = value
        elif key in single:
            raise ReconError('duplicate_reconnaissance_record')
        else:
            single[key] = value
    result = {key: single.get(key) or None for key in sorted(TEXT_FIELDS)}
    result.update({key: integer(single.get(key, '')) for key in ('uid', 'gid', 'page_size')})
    result['group_ids'] = [int(value) for value in single.get('group_ids', '').split() if value.isdigit()]
    memory = {}
    for line in single.get('memory', '').splitlines():
        key, value = line.split()
        if key in {'MemTotal:', 'MemFree:', 'MemAvailable:', 'Buffers:', 'Cached:', 'SwapTotal:', 'SwapFree:'}:
            memory[key.removesuffix(':') + '_bytes'] = int(value) * 1024
    result['memory'] = memory
    result['load_average'] = [float(value) for value in single.get('load', '').split()]
    result['mounts'] = [dict(zip(('mountpoint', 'filesystem'), line.split('\t', 1)))
                        for line in single.get('mounts', '').splitlines()]
    result['network_ipv4'] = [dict(zip(('interface', 'address'), line.split('\t', 1)))
                              for line in single.get('network_ipv4', '').splitlines()]
    result['default_routes'] = [dict(zip(('field', 'value'), line.split('\t', 1)))
                                for line in single.get('default_routes', '').splitlines()]
    result['dashboard_port_1337'] = {
        'checked': single.get('dashboard_port_checked') == 'yes',
        'listeners': single.get('dashboard_port_listeners', '').splitlines(),
    }
    result['global_ipv6_address_count'] = integer(single.get('global_ipv6_address_count', ''))
    result['hybridmount_versions'] = [dict(zip(('package', 'version'), line.split('\t', 1)))
                                     for line in single.get('hybridmount_versions', '').splitlines()]
    info = json.loads(single['docker_info']) if single.get('docker_info') else {}
    result['docker'] = {key: value for key, value in info.items() if key in INFO_FIELDS}
    result['containers'] = [{key: value for key, value in json.loads(line).items() if key in {'name', 'status'}}
                            for line in single.get('containers', '').splitlines()]
    stats = [{key: value for key, value in json.loads(line).items() if key in STAT_FIELDS}
             for line in single.get('container_stats', '').splitlines()]
    result['container_stats'] = stats
    deployed_fields = {'name', 'user', 'running', 'health', 'read_only_root', 'privileged', 'network_mode',
                       'group_add', 'cap_drop', 'security_options', 'port_bindings', 'memory_limit_bytes'}
    result['deployed_containers'] = []
    for line in single.get('deployed_containers', '').splitlines():
        container = json.loads(line)
        public = {key: value for key, value in container.items() if key in deployed_fields}
        public['docker_socket_mounted'] = any(
            mount.get(field, '').endswith('/docker.sock')
            for mount in container.get('mounts', []) for field in ('source', 'target'))
        public['mounts'] = [{key: value for key, value in mount.items() if key in {'target', 'writable'}}
                            for mount in container.get('mounts', [])]
        result['deployed_containers'].append(public)
    runtime = json.loads(single['dashboard_runtime']) if single.get('dashboard_runtime') else {}
    result['dashboard_runtime'] = {key: value for key, value in runtime.items()
                                   if key in {'uid', 'gid', 'groups', 'page_size'}}
    iperf = json.loads(single['iperf_baseline']) if single.get('iperf_baseline') else {}
    result['iperf_baseline'] = {key: value for key, value in iperf.items()
                              if key in {'name', 'running', 'started_at', 'restart_count'}}
    result['container_stats_available'] = single.get('container_stats_available') == 'yes'
    try:
        result['container_totals'] = {
            'sampled_containers': len(stats),
            'cpu_percent': round(sum(float(item['cpu_percent'].removesuffix('%')) for item in stats), 2),
            'memory_used_bytes': sum(memory_bytes(item['memory'].split('/', 1)[0]) for item in stats),
            'pids': sum(int(item['pids']) for item in stats),
        } if result['container_stats_available'] else None
    except (ValueError, KeyError):
        result['container_totals'] = None
    result['shares'] = []
    for share in shares:
        ownership = share.get('ownership', '').split()
        capacity = share.get('capacity', '').split()
        result['shares'].append({'name': share['name'], 'path': share.get('path'),
                                'filesystem': share.get('filesystem') or None,
                                'owner_uid': integer(ownership[0]) if len(ownership) == 3 else None,
                                'owner_gid': integer(ownership[1]) if len(ownership) == 3 else None,
                                'mode': ownership[2] if len(ownership) == 3 else None,
                                **{name: int(value) * 1024 for name, value in zip(
                                    ('total_bytes', 'used_bytes', 'free_bytes'), capacity) if value.isdigit()}})
    result['status'] = 'ok'
    result['read_only'] = True
    return result


def connection_command(environment: dict) -> list[str]:
    values = {name: environment.get(name, '') for name in ('QNAP_SSH_TARGET', 'QNAP_SSH_KEY', 'QNAP_SSH_KNOWN_HOSTS')}
    if not all(values.values()) or not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9][A-Za-z0-9.-]*', values['QNAP_SSH_TARGET']):
        raise ReconError('dedicated_qnap_connection_settings_missing_or_invalid')
    for name in ('QNAP_SSH_KEY', 'QNAP_SSH_KNOWN_HOSTS'):
        path = Path(values[name]).expanduser().resolve()
        if not path.is_file():
            raise ReconError('dedicated_key_or_pinned_known_hosts_file_missing')
        if name == 'QNAP_SSH_KEY' and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ReconError('dedicated_private_key_permissions_must_be_0600')
        values[name] = str(path)
    return ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'IdentityAgent=none', '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-i', values['QNAP_SSH_KEY'],
            '-o', 'UserKnownHostsFile=' + values['QNAP_SSH_KNOWN_HOSTS'], '--', values['QNAP_SSH_TARGET'], 'sh -s']


def main() -> int:
    try:
        result = subprocess.run(connection_command(os.environ), input=PAYLOAD.encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            diagnostic = result.stderr.decode(errors='replace').lower()
            if 'permission denied' in diagnostic:
                raise ReconError('dedicated_qnap_key_authentication_failed_no_fallback_attempted')
            if 'host key verification failed' in diagnostic or 'remote host identification has changed' in diagnostic:
                raise ReconError('qnap_host_key_verification_failed_no_update_attempted')
            if 'could not resolve hostname' in diagnostic:
                raise ReconError('qnap_hostname_resolution_failed')
            raise ReconError('qnap_read_only_connection_or_probe_failed')
        print(json.dumps(parse_output(result.stdout), indent=2, sort_keys=True))
        return 0
    except ReconError as error:
        print(json.dumps({'status': 'error', 'error': str(error)}))
        return 1
    except Exception:
        print(json.dumps({'status': 'error', 'error': 'reconnaissance_failed_no_raw_remote_output_displayed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
