#!/usr/bin/env python3
"""Install only the dedicated VPN address and fail-closed host policy.

The UFW fragment survives UFW reloads. Direct INPUT/OUTPUT hooks additionally
protect the address when UFW is disabled. Changes never flush unrelated rules.
No command inspects XFRM state, which can disclose session encryption keys.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import tempfile

INTERFACE = "usenet-vpn0"
CHAINS = ("USENET_VPN_IN", "USENET_VPN_OUT", "USENET_VPN_FWD")
BEGIN = "# BEGIN USENET VPN POLICY"
END = "# END USENET VPN POLICY"
PRIVATE = tuple(ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


class PolicyError(Exception):
    pass


def validate_config(value):
    if not isinstance(value, dict) or set(value) != {"service_ip", "service_cidr", "lan_cidr", "peer_ip", "local_ip"}:
        raise PolicyError("VPN configuration fields do not match the reviewed schema")
    try:
        service = ipaddress.IPv4Address(value["service_ip"])
        subnet = ipaddress.IPv4Network(value["service_cidr"], strict=True)
        lan = ipaddress.IPv4Network(value["lan_cidr"], strict=True)
        peer = ipaddress.IPv4Address(value["peer_ip"])
        local = ipaddress.IPv4Address(value["local_ip"])
    except (ValueError, TypeError) as exc:
        raise PolicyError("VPN endpoints must be canonical IPv4 addresses and a network") from exc
    if not any(service in network for network in PRIVATE) or not any(lan.subnet_of(network) for network in PRIVATE):
        raise PolicyError("VPN service address and LAN must use RFC1918 space")
    if service not in subnet or not any(subnet.subnet_of(network) for network in PRIVATE) or subnet.overlaps(lan) or peer == local or not peer.is_global or not local.is_global:
        raise PolicyError("VPN selectors overlap or public endpoints are invalid")
    return dict(service_ip=str(service), service_cidr=str(subnet), lan_cidr=str(lan), peer_ip=str(peer), local_ip=str(local))


def policy_rules(config):
    c = validate_config(config)
    service, lan, peer, local = (c[key] for key in ("service_ip", "lan_cidr", "peer_ip", "local_ip"))
    inbound, outbound, forward = CHAINS
    subnet = c["service_cidr"]
    return [
        # Host-only anonymous proxy health probes. Both endpoint addresses and
        # the loopback interface are required; this is never a LAN bypass.
        f"-A {inbound} -i lo -s {service}/32 -d {service}/32 -p tcp -m multiport --dports 18080,19696 "
        "-m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT",
        f"-A {inbound} -i lo -s {service}/32 -d {service}/32 -p tcp -m multiport --sports 18080,19696 "
        "-m conntrack --ctstate ESTABLISHED -j ACCEPT",
        f"-A {outbound} -o lo -s {service}/32 -d {service}/32 -p tcp -m multiport --dports 18080,19696 "
        "-m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT",
        f"-A {outbound} -o lo -s {service}/32 -d {service}/32 -p tcp -m multiport --sports 18080,19696 "
        "-m conntrack --ctstate ESTABLISHED -j ACCEPT",
        f"-A {inbound} -d {service}/32 -s {lan} -p tcp -m multiport --dports 18080,19696 "
        f"-m conntrack --ctstate NEW,ESTABLISHED -m policy --dir in --pol ipsec --proto esp "
        f"--mode tunnel --tunnel-src {peer}/32 --tunnel-dst {local}/32 --strict -j ACCEPT",
        f"-A {inbound} -d {subnet} -j DROP",
        f"-A {outbound} -s {service}/32 -d {lan} -p tcp -m multiport --sports 18080,19696 "
        f"-m conntrack --ctstate ESTABLISHED -m policy --dir out --pol ipsec --proto esp "
        f"--mode tunnel --tunnel-src {local}/32 --tunnel-dst {peer}/32 --strict -j ACCEPT",
        f"-A {outbound} -s {subnet} -j DROP",
        f"-A {forward} -d {subnet} -j DROP",
        f"-A {forward} -s {subnet} -j DROP",
    ]


def render_ufw(before, config):
    """Insert ahead of UFW's established-connection acceptance, idempotently."""
    if before.count(BEGIN) != before.count(END) or before.count(BEGIN) > 1:
        raise PolicyError("Malformed managed UFW policy markers")
    if BEGIN in before:
        start, finish = before.index(BEGIN), before.index(END) + len(END)
        if finish < start:
            raise PolicyError("Reversed managed UFW policy markers")
        before = before[:start] + before[finish:].lstrip("\n")
    lines = before.splitlines(keepends=True)
    filters = [index for index, line in enumerate(lines) if line.strip() == "*filter"]
    if len(filters) != 1:
        raise PolicyError("Expected one existing UFW filter table")
    begin = filters[0]
    try:
        end = next(index for index in range(begin + 1, len(lines)) if lines[index].strip() == "COMMIT")
        insertion = next(index for index in range(begin + 1, end) if lines[index].startswith("-A "))
    except StopIteration as exc:
        raise PolicyError("Incomplete UFW filter table") from exc
    declarations = "".join(lines[begin:insertion])
    if any(f":ufw-before-{direction} " not in declarations for direction in ("input", "output", "forward")):
        raise PolicyError("Expected UFW input and output chain declarations")
    if any(chain in "".join(lines) for chain in CHAINS):
        raise PolicyError("Unmanaged rules already use a reserved VPN chain")
    fragment = [BEGIN, *(f":{chain} - [0:0]" for chain in CHAINS), *policy_rules(config),
                f"-A ufw-before-input -j {CHAINS[0]}", f"-A ufw-before-output -j {CHAINS[1]}",
                f"-A ufw-before-forward -j {CHAINS[2]}", END]
    lines.insert(insertion, "\n".join(fragment) + "\n")
    return "".join(lines)


def restore_script(config, present_hooks):
    rows = ["*filter", *(f":{chain} - [0:0]" for chain in CHAINS), *(f"-F {chain}" for chain in CHAINS)]
    rows += policy_rules(config)
    for builtin, chain in zip(("INPUT", "OUTPUT", "FORWARD"), CHAINS):
        if builtin not in present_hooks:
            rows.append(f"-I {builtin} 1 -j {chain}")
    return "\n".join([*rows, "COMMIT", ""])


def run(argv, *, data=None, check=True):
    result = subprocess.run(argv, input=data, text=True, capture_output=True, timeout=30)
    if check and result.returncode:
        # Deliberately do not include subprocess output or arbitrary file content.
        raise PolicyError(f"VPN network operation failed: {Path(argv[0]).name}")
    return result


def check_interface(config):
    result = run(["/usr/sbin/ip", "-j", "-d", "link", "show", "dev", INTERFACE], check=False)
    if result.returncode == 1:
        return False
    if result.returncode:
        raise PolicyError("Unable to inspect the dedicated VPN interface")
    rows = json.loads(result.stdout)
    if len(rows) != 1 or rows[0].get("linkinfo", {}).get("info_kind") != "dummy":
        raise PolicyError("Reserved VPN interface is not a dummy interface")
    addresses = json.loads(run(["/usr/sbin/ip", "-j", "address", "show", "dev", INTERFACE]).stdout)
    actual = {(entry["local"], entry["prefixlen"]) for row in addresses for entry in row.get("addr_info", [])}
    if actual - {(config["service_ip"], 32)}:
        raise PolicyError("Dedicated VPN interface has an unexpected address; review migration first")
    return True


def install_address(config):
    if not check_interface(config):
        run(["/usr/sbin/ip", "link", "add", "name", INTERFACE, "type", "dummy"])
    # Suppress an unwanted automatic IPv6 address on this IPv4-only interface.
    run(["/usr/sbin/ip", "link", "set", "dev", INTERFACE, "addrgenmode", "none"])
    run(["/usr/sbin/ip", "address", "replace", f"{config['service_ip']}/32", "dev", INTERFACE])
    run(["/usr/sbin/ip", "link", "set", "dev", INTERFACE, "up"])


def write_atomic(path, content):
    metadata = path.lstat()
    if not path.is_file() or path.is_symlink() or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise PolicyError("UFW rules must be a root-owned file without group/other write access")
    descriptor, temporary = tempfile.mkstemp(prefix=".usenet-vpn-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            os.fchmod(stream.fileno(), metadata.st_mode & 0o777)
            os.fchown(stream.fileno(), metadata.st_uid, metadata.st_gid)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install_firewall(config, ufw_path=Path("/etc/ufw/before.rules")):
    check_interface(config)  # Refuse an unsafe address migration before changing protection.
    before = ufw_path.read_text()
    after = render_ufw(before, config)
    present = set()
    # With iptables-nft, checking a jump to a nonexistent target can return 2
    # (extension parsing), not the documented 1 for an absent rule. Inspect
    # declared chains successfully first; never treat arbitrary errors as absence.
    declared = set(run(["/usr/sbin/iptables", "-w", "5", "-S"]).stdout.splitlines())
    for builtin, chain in zip(("INPUT", "OUTPUT", "FORWARD"), CHAINS):
        if f"-N {chain}" not in declared:
            continue
        result = run(["/usr/sbin/iptables", "-w", "5", "-C", builtin, "-j", chain], check=False)
        if result.returncode == 0:
            present.add(builtin)
        elif result.returncode != 1:
            raise PolicyError("Unable to inspect existing VPN firewall hooks")
    script = restore_script(config, present)
    run(["/usr/sbin/iptables-restore", "--wait", "5", "--test", "--noflush"], data=after)
    run(["/usr/sbin/iptables-restore", "--wait", "5", "--test", "--noflush"], data=script)
    run(["/usr/sbin/iptables-restore", "--wait", "5", "--noflush"], data=script)
    if after != before:
        write_atomic(ufw_path, after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "firewall", "address"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    try:
        config = validate_config(json.loads(args.config.read_text()))
        if args.operation == "firewall":
            install_firewall(config)
        elif args.operation == "address":
            install_address(config)
        print(json.dumps({"operation": args.operation, "ok": True}))
    except (PolicyError, ValueError, OSError, subprocess.SubprocessError):
        raise SystemExit("VPN network operation refused or failed; inspect the reviewed configuration and service status")


if __name__ == "__main__":
    main()
