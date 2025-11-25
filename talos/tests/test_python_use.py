from __future__ import annotations

import subprocess
from pathlib import Path


def _env_with_stubbed_path(tmp_path: Path) -> dict[str, str]:
    env = {key: value for key, value in subprocess.os.environ.items()}
    env["PATH"] = f"{tmp_path}/bin:/usr/bin:/bin"
    env["HOME"] = str(tmp_path / "home")
    env["TALOS_PYENV_SKIP_INSTALL"] = "1"
    return env


def test_python_use_prefers_local_python_version(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "python_use.sh"
    env = _env_with_stubbed_path(tmp_path)

    (tmp_path / "bin").mkdir(parents=True, exist_ok=True)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)

    pyenv_log = tmp_path / "pyenv.log"
    shim_python = tmp_path / "shims" / "python"
    shim_python.parent.mkdir(parents=True, exist_ok=True)

    required_version = "9.9.9"

    pyenv = tmp_path / "bin" / "pyenv"
    pyenv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'echo "$@" >> "{pyenv_log}"',
                'case "$1" in',
                "  versions)",
                f'    echo "{required_version}"',
                "    ;;",
                "  install)",
                "    exit 0",
                "    ;;",
                "  which)",
                f'    echo "{shim_python}"',
                "    ;;",
                "  root)",
                f'    echo "{tmp_path}/pyenv"',
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

    assert proc.stdout.strip() == str(shim_python)
    log_lines = pyenv_log.read_text(encoding="utf-8").strip().splitlines()
    assert "versions --bare" in log_lines[0]
    assert "which python" in log_lines[-1]


def test_python_use_errors_on_mismatch_without_pyenv(tmp_path: Path):
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
    assert "Python version mismatch" in proc.stderr


def test_python_use_prefers_pyenv_even_if_system_mismatch(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "python_use.sh"
    env = _env_with_stubbed_path(tmp_path)

    # System python reports 3.13
    system_python = tmp_path / "bin" / "python3"
    system_python.write_text(
        '#!/usr/bin/env bash\necho "Python 3.13.0"\n', encoding="utf-8"
    )
    system_python.chmod(0o755)

    pyenv_log = tmp_path / "pyenv.log"
    shim_python = tmp_path / "shims" / "python"
    shim_python.parent.mkdir(parents=True, exist_ok=True)

    pyenv = tmp_path / "bin" / "pyenv"
    pyenv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'echo "$@" >> "{pyenv_log}"',
                'case "$1" in',
                "  install)",
                "    exit 0",
                "    ;;",
                "  which)",
                f'    echo "{shim_python}"',
                "    ;;",
                "  root)",
                f'    echo "{tmp_path}/pyenv"',
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
        ["bash", "-c", f'source "{script}" && echo \"$TALOS_PYTHON_BIN\""],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    # Should use pyenv shim, not system python3
    assert proc.stdout.strip() == str(shim_python)
