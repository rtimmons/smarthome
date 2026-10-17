#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${CONFIG_DIR}/.." && pwd)"
SCRIPTS_PATH="new-hass-configs/scripts.yaml"

cd "$REPO_ROOT"

git check-ignore -q "$SCRIPTS_PATH"
if git ls-files --error-unmatch "$SCRIPTS_PATH" >/dev/null 2>&1; then
    echo "scripts.yaml must be generated and untracked" >&2
    exit 1
fi

grep -q 'generated/scripts.yaml' "${CONFIG_DIR}/Justfile"
grep -q '^script: !include scripts.yaml$' "${CONFIG_DIR}/configuration.yaml"

# Exercise both sync paths against synthetic remote-only recovery files.
python3 - "$CONFIG_DIR" <<'PY'
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

config = Path(sys.argv[1])
just_filters = shlex.split(subprocess.check_output(
    ["just", "--evaluate", "rsync_protect_filters"], cwd=config, text=True).strip())
deploy_source = (config / "sync-tools/deploy-config.sh").read_text()
deploy_filters = re.findall(r'"(--filter=protect [^"\n]+)"', deploy_source)
for filters in (just_filters, deploy_filters):
    with tempfile.TemporaryDirectory() as directory:
        source, target = Path(directory) / "source", Path(directory) / "target"
        source.mkdir()
        target.mkdir()
        protected = ["backups/wall/snapshot/packages/wall.yaml",
                     ".recovery-notify-synthetic/secrets.yaml",
                     "blueprints/template/homeassistant/synthetic.yaml"]
        for relative in protected:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("Synthetic recovery data\n")
        (target / "obsolete.yaml").write_text("obsolete\n")
        (target / "scripts.yaml").write_text("old scripts\n")
        (source / "scripts.yaml").write_text("updated generated scripts\n")
        subprocess.run(["rsync", "-a", "--delete", *filters,
                        str(source) + "/", str(target) + "/"], check=True)
        assert all((target / name).read_text() == "Synthetic recovery data\n" for name in protected)
        assert not (target / "obsolete.yaml").exists()
        assert (target / "scripts.yaml").read_text() == "updated generated scripts\n"

# The transition profile must reach staging and the final configuration, while
# unrelated CSV artifacts remain excluded by the real deployment filters.
filter_block = re.search(r"DEPLOY_FILTERS=\(\n(.*?)\n\)", deploy_source, re.S).group(1)
deployment_filters = shlex.split(filter_block)
with tempfile.TemporaryDirectory() as directory:
    source, target = Path(directory) / "source", Path(directory) / "target"
    source.mkdir()
    target.mkdir()
    profile = "id,x,y,brightness,transition\ngroup.all_lights.default,,,,0\n"
    (source / "light_profiles.csv").write_text(profile)
    (source / "unrelated.csv").write_text("private fixture\n")
    subprocess.run(["rsync", "-a", *deployment_filters,
                    str(source) + "/", str(target) + "/"], check=True)
    assert (target / "light_profiles.csv").read_text() == profile
    assert not (target / "unrelated.csv").exists()
PY

echo "generated configuration policy tests passed"
