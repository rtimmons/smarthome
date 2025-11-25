from __future__ import annotations

import subprocess
from pathlib import Path


def _env_with_stubbed_path(tmp_path: Path) -> dict[str, str]:
    env = {key: value for key, value in subprocess.os.environ.items()}
    env["PATH"] = f"{tmp_path}/bin:/usr/bin:/bin"
    env["HOME"] = str(tmp_path / "home")
    env.pop("PYENV_VERSION", None)
    return env


def test_python_use_prefers_local_python_version(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "python_use.sh"
    env = _env_with_stubbed_path(tmp_path)

    (tmp_path / "bin").mkdir(parents=True, exist_ok=True)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)

    pyenv_log = tmp_path / "pyenv.log"
    required_version = "9.9.9"

    pyenv_root = tmp_path / "pyenvroot"
    pyenv_root.mkdir()
    env["PYENV_ROOT"] = str(pyenv_root)

    python_bin = pyenv_root / "versions" / required_version / "bin" / "python"
    python_bin.parent.mkdir(parents=True, exist_ok=True)
    python_bin.write_text('#!/usr/bin/env bash\necho "Python 9.9.9"\n', encoding="utf-8")
    python_bin.chmod(0o755)

    pyenv = tmp_path / "bin" / "pyenv"
    pyenv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'echo "$@" >> "{pyenv_log}"',
                'case "$1" in',
                "  commands)",
                "    echo install",
                "    ;;",
                "  versions)",
                f'    echo \"{required_version}\"',
                "    ;;",
                "  install)",
                "    exit 0",
                "    ;;",
                "  which)",
                f'    echo \"{python_bin}\"',
                "    ;;",
                "  root)",
                f'    echo \"{pyenv_root}\"',
                "    ;;",
                "  init)",
                "    ;;",
            "esac",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pyenv.chmod(0o755)

    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / ".python-version").write_text(f"{required_version}\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", f'source "{script}" && echo "$TALOS_PYTHON_BIN"'],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert proc.stdout.strip() == str(python_bin)
    log_lines = pyenv_log.read_text(encoding="utf-8").strip().splitlines()
    # pyenv init is called first, then versions --bare, then which
    assert "init -" in log_lines[0]
    assert any("versions --bare" in line for line in log_lines)
    assert any("root" in line for line in log_lines)


def test_python_use_requires_pyenv_when_missing(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "python_use.sh"
    env = _env_with_stubbed_path(tmp_path)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)

    # Stub python3 that reports 3.13
    python_stub = bin_dir / "python3"
    python_stub.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [ "$1" = "--version" ] || [ "$1" = "-" ]; then',
                '  echo "Python 3.13.0"',
                "  exit 0",
                "fi",
                'echo "Python 3.13.0"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    python_stub.chmod(0o755)

    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / ".python-version").write_text("3.12.12\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", f'source "{script}"'],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "pyenv is required" in proc.stderr


def test_python_use_prefers_pyenv_even_if_system_mismatch(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "python_use.sh"
    env = _env_with_stubbed_path(tmp_path)

    (tmp_path / "bin").mkdir(parents=True, exist_ok=True)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)

    # System python reports 3.13
    system_python = tmp_path / "bin" / "python3"
    system_python.write_text(
        '#!/usr/bin/env bash\necho "Python 3.13.0"\n', encoding="utf-8"
    )
    system_python.chmod(0o755)

    pyenv_log = tmp_path / "pyenv.log"
    python_bin = pyenv_root = tmp_path / "pyenvroot" / "versions" / "3.12.12" / "bin" / "python"

    pyenv_root = tmp_path / "pyenvroot"
    pyenv_root.mkdir()
    env["PYENV_ROOT"] = str(pyenv_root)

    python_bin.parent.mkdir(parents=True, exist_ok=True)
    python_bin.write_text('#!/usr/bin/env bash\necho "Python 3.12.12"\n', encoding="utf-8")
    python_bin.chmod(0o755)

    pyenv = tmp_path / "bin" / "pyenv"
    pyenv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'echo "$@" >> "{pyenv_log}"',
                'case "$1" in',
                "  commands)",
                "    echo install",
                "    ;;",
                "  install)",
                "    exit 0",
                "    ;;",
                "  versions)",
                '    echo "3.12.12"',
                "    ;;",
                "  which)",
                f'    echo "{python_bin}"',
                "    ;;",
                "  root)",
                f'    echo \"{pyenv_root}\"',
                "    ;;",
                "  init)",
                "    ;;",
                "esac",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pyenv.chmod(0o755)

    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / ".python-version").write_text("3.12.12\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", f'source "{script}" && echo "$TALOS_PYTHON_BIN"'],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    # Should use pyenv python, not system python3
    assert proc.stdout.strip() == str(python_bin)


def test_python_use_installs_if_bin_missing(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "python_use.sh"
    env = _env_with_stubbed_path(tmp_path)

    (tmp_path / "bin").mkdir(parents=True, exist_ok=True)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)

    pyenv_log = tmp_path / "pyenv.log"
    required_version = "8.8.8"

    pyenv_root = tmp_path / "pyenvroot"
    pyenv_root.mkdir()
    env["PYENV_ROOT"] = str(pyenv_root)

    python_bin = pyenv_root / "versions" / required_version / "bin" / "python"
    # leave missing; install will create

    pyenv = tmp_path / "bin" / "pyenv"
    pyenv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'echo "$@" >> "{pyenv_log}"',
                'case "$1" in',
                "  commands)",
                "    echo install",
                "    ;;",
                "  versions)",
                f'    echo \"{required_version}\"',
                "    ;;",
                "  install)",
                f'    mkdir -p \"{python_bin.parent}\" && echo \"#!/usr/bin/env bash\" > \"{python_bin}\" && echo \"echo Python {required_version}\" >> \"{python_bin}\" && chmod +x \"{python_bin}\"',
                "    ;;",
                "  which)",
                f'    echo \"{python_bin}\"',
                "    ;;",
                "  root)",
                f'    echo \"{pyenv_root}\"',
                "    ;;",
                "  init)",
                "    ;;",
            "esac",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pyenv.chmod(0o755)

    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / ".python-version").write_text(f"{required_version}\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", f'source \"{script}\" && echo \"$TALOS_PYTHON_BIN\"'],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert proc.stdout.strip() == str(python_bin)
