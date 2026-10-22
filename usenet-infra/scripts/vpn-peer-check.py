#!/usr/bin/env python3
"""Read-only WAN-change preflight across private inputs, Hetzner and the cloud.

Supply the WAN IPv4 observed on the Max, not an address from an IP echo site.
Only selected booleans are printed; credentials and raw replies stay in memory.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from urllib.request import Request, urlopen

import yaml

INFRA = Path(__file__).resolve().parents[1]
REMOTE = r'''
import ipaddress,json,os,re,subprocess,sys
peer=sys.argv[1]
def read(args):
    r=subprocess.run(args,capture_output=True,text=True,timeout=20)
    if r.returncode: raise RuntimeError('read failed')
    return r.stdout
policy=json.loads(read(['sudo','-n','cat','/etc/usenet-vpn/network.json']))
ufw=read(['sudo','-n','/usr/sbin/ufw','status'])
sas=read(['sudo','-n','/usr/sbin/swanctl','--list-sas','--ike','usenet-ui'])
def allowed(port,proto):
    sources=re.findall(r'(?m)^'+port+'/'+proto+r'\s+ALLOW(?:\s+IN)?\s+(\S+)',ufw)
    return bool(sources) and all(s not in ('Anywhere','Any') and ipaddress.ip_network(s,strict=False)==ipaddress.ip_network(peer+'/32') for s in sources)
ssh_sources=re.findall(r'(?m)^22/tcp\s+ALLOW(?:\s+IN)?\s+(\S+)',ufw)
source=os.environ.get('SSH_CONNECTION','').split()
print(json.dumps({
 'fresh_ssh_from_expected_wan':bool(source) and source[0]==peer,
 'installed_peer_matches':policy.get('peer_ip')==peer,
 'installed_selectors_match':policy.get('lan_cidr')=='192.168.1.0/24' and policy.get('service_cidr')=='10.77.0.0/30',
 'ufw_ssh_source_present':any(s not in ('Anywhere','Any') and ipaddress.ip_network(s,strict=False)==ipaddress.ip_network(peer+'/32') for s in ssh_sources),
 'ufw_ssh_not_unrestricted':bool(ssh_sources) and all(s not in ('Anywhere','Any') and ipaddress.ip_network(s,strict=False).prefixlen>0 for s in ssh_sources),
 'ufw_ike_sources_exact':allowed('500','udp') and allowed('4500','udp'),
 'ikev2_established':bool(re.search(r'^usenet-ui:.*ESTABLISHED.*IKEv2',sas,re.M)),
 'child_installed':bool(re.search(r'^  usenet-ui:.*INSTALLED',sas,re.M)),
 'sha256_negotiated':'HMAC_SHA2_256_128' in sas and 'PRF_HMAC_SHA2_256' in sas and 'HMAC_SHA1' not in sas
}))
'''


class CheckError(Exception):
    pass


def peer_address(value):
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError):
        raise CheckError('Supply one canonical public WAN IPv4 address.') from None
    if not address.is_global or str(address) != value:
        raise CheckError('Supply one canonical public WAN IPv4 address.')
    return str(address)


def hcl_literal(text, field):
    pattern = r'^\s*' + re.escape(field) + r'\s*=\s*("[^"\n]*"|\[[^\]]*\])\s*(?:#.*)?$'
    values = re.findall(pattern, text, re.MULTILINE)
    if len(values) != 1:
        raise CheckError('Expected one literal ' + field + ' in the private Terraform inputs.')
    try:
        return json.loads(values[0])
    except ValueError:
        raise CheckError('Unsupported literal in the private Terraform inputs.') from None


def local_checks(peer, inventory, tfvars):
    try:
        all_values = inventory['all']
        cloud = all_values['children']['cloud']
        hosts = list(cloud['hosts'].values())
        if len(hosts) != 1:
            raise CheckError('Expected exactly one cloud host in the private inventory.')
        values = {**all_values.get('vars', {}), **cloud.get('vars', {}), **hosts[0]}
        cidr = peer + '/32'
        return {
            'inventory_peer_matches': values.get('cloud_vpn_peer_ip') == peer,
            'inventory_ssh_source_present': cidr in values.get('cloud_ssh_allowed_cidrs', []),
            'terraform_peer_matches': hcl_literal(tfvars, 'vpn_peer_ipv4') == peer,
            'terraform_ssh_source_present': cidr in hcl_literal(tfvars, 'admin_ssh_cidrs'),
        }
    except (KeyError, TypeError, AttributeError):
        raise CheckError('Private inventory does not match the cloud host schema.') from None


def provider_checks(peer, firewall):
    """Require exact single-source IKE ingress and retain narrower SSH sources."""
    cidr = peer + '/32'
    rules = [r for r in firewall['rules'] if r.get('direction') == 'in']
    result = {}
    for port in ('500', '4500'):
        selected = [r for r in rules if r.get('protocol') == 'udp' and r.get('port') == port]
        result['hetzner_udp_' + port + '_source_exact'] = bool(selected) and all(
            r.get('source_ips') == [cidr] for r in selected)
    ssh = [r for r in rules if r.get('protocol') == 'tcp' and r.get('port') == '22']
    result['hetzner_ssh_source_present'] = any(cidr in r.get('source_ips', []) for r in ssh)
    result['hetzner_ssh_not_unrestricted'] = bool(ssh) and all(
        ipaddress.ip_network(source, strict=False).prefixlen > 0 for r in ssh for source in r.get('source_ips', []))
    # A broad rule could supersede an apparently narrow port rule.
    for port, protocol in (('22', 'tcp'), ('500', 'udp'), ('4500', 'udp')):
        competing = [r for r in rules if r.get('protocol') == protocol and r.get('port') != port]
        if any(port_matches(r.get('port'), port) for r in competing):
            result['hetzner_no_competing_' + port + '_rule'] = False
    return result


def port_matches(value, port):
    if value in (None, '', 'any'):
        return True
    try:
        if '-' in str(value):
            first, last = map(int, str(value).split('-', 1))
            return first <= int(port) <= last
        return int(value) == int(port)
    except (TypeError, ValueError):
        return True


def provider(peer):
    token_path = INFRA / 'secrets/hetzner.env'
    if token_path.is_symlink() or not token_path.is_file() or token_path.stat().st_mode & 0o077:
        raise CheckError('The existing Hetzner token file must be a private regular file.')
    tokens = []
    for line in token_path.read_text().splitlines():
        if line.startswith('HCLOUD_TOKEN='):
            fields = shlex.split(line.split('=', 1)[1], comments=True)
            if len(fields) == 1: tokens.append(fields[0])
    if len(tokens) != 1 or not tokens[0]:
        raise CheckError('The existing Hetzner token was not available.')
    state = json.loads((INFRA / 'terraform/cloud/terraform.tfstate').read_text())
    matches = [r for r in state['resources'] if r.get('mode') == 'managed'
               and r.get('type') == 'hcloud_firewall' and r.get('name') == 'server']
    if len(matches) != 1 or len(matches[0]['instances']) != 1:
        raise CheckError('Expected one recorded cloud firewall in Terraform state.')
    firewall_id = str(matches[0]['instances'][0]['attributes']['id'])
    if not firewall_id.isdecimal():
        raise CheckError('Invalid recorded cloud firewall identity.')
    request = Request('https://api.hetzner.cloud/v1/firewalls/' + firewall_id,
                      headers={'Authorization': 'Bearer ' + tokens[0]})
    with urlopen(request, timeout=10) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise CheckError('Provider response exceeded the expected size.')
    return provider_checks(peer, json.loads(raw)['firewall'])


def cloud(peer):
    result = subprocess.run([str(INFRA / 'scripts/cloud-command'), 'python3', '-', peer],
                            input=REMOTE, capture_output=True, text=True, timeout=55)
    if result.returncode == 255:
        raise CheckError('Fresh dedicated cloud SSH failed; use the documented provider-console recovery path.')
    if result.returncode:
        raise CheckError('The cloud read-only inspection failed; raw remote output withheld.')
    fields = json.loads(result.stdout)
    expected = {'fresh_ssh_from_expected_wan', 'installed_peer_matches', 'installed_selectors_match',
                'ufw_ssh_source_present', 'ufw_ssh_not_unrestricted', 'ufw_ike_sources_exact', 'ikev2_established', 'child_installed',
                'sha256_negotiated'}
    if set(fields) != expected or any(type(value) is not bool for value in fields.values()):
        raise CheckError('Cloud preflight returned an unexpected result.')
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('peer', help='Current WAN IPv4 verified in the Max')
    parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--require-sha256', action='store_true')
    args = parser.parse_args()
    if args.local_only and args.require_sha256:
        parser.error('--require-sha256 needs the live cloud check; omit --local-only')
    try:
        peer = peer_address(args.peer)
        inventory = yaml.safe_load((INFRA / 'ansible/inventory.yml').read_text())
        tfvars = (INFRA / 'terraform/cloud/terraform.tfvars').read_text()
        checks = local_checks(peer, inventory, tfvars)
        if not args.local_only:
            checks.update(provider(peer))
            checks.update(cloud(peer))
        required = {key: value for key, value in checks.items()
                    if args.require_sha256 or key != 'sha256_negotiated'}
        print(json.dumps({'scope': 'local-inputs' if args.local_only else 'inputs-provider-cloud',
                          'checks': checks, 'passed': all(required.values()),
                          'max_settings_verified': False, 'data_path_verified': False}, sort_keys=True))
        return 0 if all(required.values()) else 1
    except (CheckError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, CheckError) else 'Preflight could not complete; private configuration and raw responses withheld.'
        print(message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
