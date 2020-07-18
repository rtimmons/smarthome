import os
from subprocess import STDOUT, check_output
from typing import List


def command_output(cmd):
    out = check_output(cmd, stderr=STDOUT).strip()
    return [x.strip() for x in str(out, "utf-8").split("\n")]

def list_dir(path):
    return os.listdir(path)


def is_dir(path):
    return os.path.isdir(path)


class OchoPackage:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(self.path)
        self._dependencies = None

    def __repr__(self):
        return f"8({self.name})"

    def _resolve_deps(self):
        build_sh = os.path.join(self.path, "build.sh")
        if not os.path.isfile(build_sh):
            return []
        return command_output([build_sh, "list-dependencies"])

    @property
    def dependencies(self) -> List[str]:
        if self._dependencies is None:
            self._dependencies = self._resolve_deps()
        return self._dependencies


def main():
    cwd = os.getcwd()
    src_dir = os.path.join(cwd, "src")

    packages = []
    for subdir in list_dir(src_dir):
        subdir = os.path.join(src_dir, subdir)
        if not os.path.isdir(subdir):
            continue
        packages.append(OchoPackage(subdir))

    print([f"{pkg} => {pkg.dependencies}" for pkg in packages])

