from __future__ import annotations

from pathlib import Path
import subprocess


def test_nvm_use_script_referenced_in_justfile():
    nvm_just = Path(__file__).resolve().parents[1] / "just" / "nvm.just"
    contents = nvm_just.read_text(encoding="utf-8")
    assert "talos/scripts/nvm_use.sh" in contents


def test_nvm_use_prefers_local_nvmrc(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "nvm_use.sh"

    # Create a fake git repo root
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / ".nvmrc").write_text("v9.9.9\n", encoding="utf-8")

    env = {k: v for k, v in subprocess.os.environ.items()}
    env["PATH"] = "/usr/bin:/bin"
    env["HOME"] = str(tmp_path / "home")
    env["REPO_ROOT"] = str(repo_root)  # Override REPO_ROOT for testing

    # Create self-contained nvm directory structure at expected location
    build_dir = repo_root / "build"
    nvm_dir = build_dir / "nvm"
    nvm_src_dir = nvm_dir / "nvm-src"
    nvm_src_dir.mkdir(parents=True)

    log_path = tmp_path / "log"
    env["NVM_TEST_LOG"] = str(log_path)
    env["NVM_TEST_VERSION"] = "v9.9.9"

    # Create fake nvm.sh in the expected location
    nvm_sh = nvm_src_dir / "nvm.sh"
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

    local_dir = repo_root / "work"
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
