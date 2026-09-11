#!/usr/bin/env python3
"""Load the private VPN and reject swanctl's successful empty-config result."""
from __future__ import annotations

import re
import subprocess
import sys

SWANCTL = "/usr/sbin/swanctl"
CONFIG = "/etc/usenet-vpn/swanctl.conf"


class LoadError(Exception):
    pass


def run(arguments):
    # Parser errors can contain private configuration. Never relay raw output.
    try:
        result = subprocess.run([SWANCTL, *arguments], capture_output=True,
                                text=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise LoadError("VPN configuration command could not complete") from None
    if result.returncode:
        raise LoadError("VPN configuration command failed")
    return result.stdout


def check():
    # Ubuntu 6.0.4 does not support --ike for --list-conns. Select the exact
    # stanza locally and never accept a matching child from another connection.
    lines = run(["--list-conns"]).splitlines()
    start = next((index for index, line in enumerate(lines)
                  if re.match(r"^usenet-ui: IKEv2(?:,|$)", line)), None)
    if start is None:
        raise LoadError("The required VPN connection is not loaded")
    section = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace():
            break
        section.append(line)
    if not any(re.match(r"^  usenet-ui: TUNNEL(?:,|$)", line) for line in section):
        raise LoadError("The required VPN child configuration is not loaded")


def load():
    output = run(["--load-all", "--noprompt", "--file", CONFIG])
    lines = output.splitlines()
    # An unreadable config may return zero and unload all connections. Require
    # acknowledgement from this load, so an old daemon connection cannot pass.
    if "loaded connection 'usenet-ui'" not in lines:
        raise LoadError("The required VPN connection was not loaded from its configuration")
    if "loaded ike secret 'ike-usenet-ui'" not in lines:
        raise LoadError("The required VPN credential was not loaded")
    check()


def main():
    try:
        if sys.argv[1:] == ["check"]:
            check()
        elif sys.argv[1:] == ["load"]:
            load()
        else:
            raise LoadError("Use load or check")
    except LoadError as error:
        print(str(error), file=sys.stderr)
        return 1
    print("VPN connection and child configuration verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
