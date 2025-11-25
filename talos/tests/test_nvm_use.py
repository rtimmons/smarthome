from __future__ import annotations

from pathlib import Path
import subprocess


def test_nvm_use_script_referenced_in_justfile():
    nvm_just = Path(__file__).resolve().parents[1] / "just" / "nvm.just"
    contents = nvm_just.read_text(encoding="utf-8")
    assert "talos/scripts/nvm_use.sh" in contents


def test_nvm_use_prefers_local_nvmrc(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "nvm_use.sh"

    env = {k: v for k, v in subprocess.os.environ.items()}
    env["PATH"] = "/usr/bin:/bin"
    env["HOME"] = str(tmp_path / "home")

    nvm_dir = tmp_path / "nvm"
    nvm_dir.mkdir()
    log_path = tmp_path / "log"
    env["NVM_DIR"] = str(nvm_dir)
    env["NVM_TEST_LOG"] = str(log_path)
    env["NVM_TEST_VERSION"] = "v9.9.9"

    nvm_sh = nvm_dir / "nvm.sh"
    nvm_sh.write_text(
        """
#!/usr/bin/env bash
nvm() {
  echo "$@" >> "$NVM_TEST_LOG"
  if [ "$1" = "version" ]; then
    echo "$NVM_TEST_VERSION"
  elif [ "$1" = "install" ]; then
    return 0
  elif [ "$1" = "use" ]; then
    return 0
  fi
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    nvm_sh.chmod(0o755)

    local_dir = tmp_path / "work"
    local_dir.mkdir()
    (local_dir / ".nvmrc").write_text("v9.9.9\n", encoding="utf-8")

    run_script = f"""
      set -euo pipefail
      source "{script}"
    """

    subprocess.run(
        ["bash", "-c", run_script],
        cwd=local_dir,
        env=env,
        check=True,
    )

    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert "version v9.9.9" in log_lines[0]
    assert "use --silent v9.9.9" in log_lines[1]
