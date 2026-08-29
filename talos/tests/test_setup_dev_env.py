from pathlib import Path


def test_setup_ssh_uses_only_the_repository_home_assistant_identity() -> None:
    script = (Path(__file__).parents[1] / "setup_dev_env.sh").read_text()

    assert 'id_ed25519_codex_smarthome' in script
    assert '-i "$HA_IDENTITY"' in script
    assert '-o IdentitiesOnly=yes' in script
    assert "~/.ssh/id_rsa.pub" not in script
    assert "HA_IDENTITY=\"$REPO_ROOT/.ssh/id_ed25519_codex_smarthome\"" in script
    assert "git rev-parse --path-format=absolute --git-common-dir" in script
    assert 'HA_SSH_ERROR=$(ssh -i "$HA_IDENTITY"' in script
    assert "Could not resolve hostname" in script
    assert "mDNS/network failure" in script
    assert "Permission denied" in script
    assert "ha-ssh-key-copy" in script
    assert "do not try alternate credentials, hosts, or IP addresses" in script
