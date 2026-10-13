"""Transfer one bounded release archive using the inventory's pinned SSH identity."""
import shlex
import subprocess
import sys
from pathlib import Path

archive, destination, user, host, identity, common = sys.argv[1:]
payload = Path(archive).read_bytes()
if len(payload) > 32 * 1024 * 1024:
    raise SystemExit("Wiki archive exceeds 32 MiB")
args = ["ssh", "-T", *shlex.split(common), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-o", "ConnectTimeout=10",
        "-i", identity, f"{user}@{host}", "umask 077; cat > " + shlex.quote(destination)]
subprocess.run(args, input=payload, check=True)
