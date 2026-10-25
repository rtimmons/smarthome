#!/usr/bin/env python3
"""Read-only HTTP route acceptance. Discard bodies; never read media catalogs."""
import argparse
import json
import subprocess

CASES = [
    ('jellyfin', '/', 302, None),
    ('jellyfin', '/web/index.html', 200, None),
    ('jellyfin', '/Users/Me', 401, None),
    ('moonfin', '/', 302, '/Moonfin/Web/'),
    ('moonfin', '/Moonfin/Web/', 200, None),
    ('moonfin', '/Users/Me', 401, None),
    ('plex', '/', 302, '/web/'),
    ('plex', '/web/index.html', 200, None),
    ('seerr', '/', 307, '/login'),
    ('seerr', '/api/v1/auth/me', 401, None),
    ('printer', '/', 302, '/bb'),
    ('printer', '/bb', 200, None),
    ('tinyurl', '/', 200, None),
    ('grid-dashboard', '/', 200, None),
    ('ha', '/', 404, None),
    ('unknown-proxy-check', '/', 404, None),
]


ARR = ('radarr', 'sonarr', 'prowlarr', 'sabnzbd', 'catalog')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dns', action='store_true', help='Use normal DNS instead of forced proxy resolution')
    args = parser.parse_args()
    failed = []
    for name, path, expected, location in CASES:
        host = name + '.home.arpa'
        # Unknown and deferred names intentionally have no DNS records.
        force = not args.dns or name in ('ha', 'unknown-proxy-check')
        command = ['curl', '--noproxy', '*', '--silent', '--show-error', '--max-time', '30',
                   '--output', '/dev/null', '--write-out', '%{json}']
        if force:
            command += ['--resolve', host + ':80:192.168.1.163']
        result = subprocess.run(command + ['http://' + host + path], capture_output=True, text=True)
        info = json.loads(result.stdout or '{}')
        status = info.get('http_code', 0)
        target = info.get('redirect_url', '')
        ok = result.returncode == 0 and status == expected
        if location:
            ok = ok and target.split('?', 1)[0] == 'http://' + host + location
        print(f'{"PASS" if ok else "FAIL"} {host}{path} status={status} expected={expected}', flush=True)
        if not ok:
            failed.append(host + path)
    for name in (*ARR, 'grid-dashboard', 'printer', 'tinyurl', 'wiki'):
        old = name+'.home.arpa'
        host = name+'.home.rytim.com'
        for scheme, domain, path, expected in (('http',old,'/',308),
                ('https',host,'/',302),('https',host,'/api/v1/system/status?apikey=synthetic',302)):
            if name not in ARR and scheme == 'http':
                continue  # Legacy LAN/kiosk entrances intentionally remain unchanged.
            port = '443' if scheme=='https' else '80'
            command = ['curl','--noproxy','*','--silent','--show-error','--max-time','20',
                       '--output','/dev/null','--write-out','%{json}']
            if not args.dns:
                command += ['--resolve',domain+':'+port+':192.168.1.163']
            result = subprocess.run(command+[scheme+'://'+domain+path],capture_output=True,text=True)
            info = json.loads(result.stdout or '{}')
            prefix = 'https://'+host+'/' if scheme=='http' else 'https://auth.home.rytim.com/'
            ok = (result.returncode==0 and info.get('http_code')==expected
                  and info.get('redirect_url','').startswith(prefix)
                  and info.get('ssl_verify_result',0)==0)
            print(f'{"PASS" if ok else "FAIL"} {domain} {scheme} gate status={info.get("http_code")}')
            if not ok: failed.append(domain+path)
    for path, expected in (('/web/index.html', 200), ('/Users/Me', 401)):
        host = 'jellyfin.home.rytim.com'
        command = ['curl', '--noproxy', '*', '--silent', '--show-error', '--max-time', '20',
                   '--output', '/dev/null', '--write-out', '%{json}']
        if not args.dns:
            command += ['--resolve', host+':443:192.168.1.163']
        result = subprocess.run(command+['https://'+host+path], capture_output=True, text=True)
        info = json.loads(result.stdout or '{}')
        ok = result.returncode == 0 and info.get('http_code') == expected and info.get('ssl_verify_result') == 0
        print(f'{"PASS" if ok else "FAIL"} {host}{path} native authentication status={info.get("http_code")}')
        if not ok: failed.append(host+path)
    if failed:
        raise SystemExit('Failed routes: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
