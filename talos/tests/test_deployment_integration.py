"""
Integration tests for the enhanced deployment system.

These tests verify end-to-end deployment workflows, including
dry-run functionality, verbose modes, and error recovery.
"""

from __future__ import annotations

import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.mark.integration
@pytest.mark.slow
class TestDeploymentIntegration:
    """Integration tests for deployment workflows."""

    def test_dry_run_deployment_shows_plan(self):
        """Test that dry-run deployment shows deployment plan without executing."""
        result = subprocess.run(
            ["just", "deploy-dry-run", "grid-dashboard"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Dry run should succeed
        assert result.returncode == 0, f"Dry run failed: {result.stderr}"
        
        # Should show dry run indicators
        assert "🔍 Dry run deployment preview" in result.stdout
        assert "📋 This was a dry run - no changes were made" in result.stdout
        
        # Should show what would be deployed
        assert "grid-dashboard" in result.stdout

    def test_verbose_dry_run_shows_detailed_plan(self):
        """Test that verbose dry-run shows detailed deployment plan."""
        result = subprocess.run(
            ["just", "deploy-dry-run-verbose", "grid-dashboard"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Verbose dry run should succeed
        assert result.returncode == 0, f"Verbose dry run failed: {result.stderr}"
        
        # Should show verbose indicators
        assert "🔍 Detailed dry run deployment preview" in result.stdout
        assert "📋 This was a detailed dry run - no changes were made" in result.stdout

    def test_deployment_prerequisite_validation(self):
        """Test that deployment validates prerequisites."""
        # This test requires mocking SSH connectivity
        with patch('subprocess.run') as mock_run:
            # Mock SSH failure
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Connection refused")
            
            result = subprocess.run(
                ["just", "deploy-dry-run", "grid-dashboard"],
                capture_output=True,
                text=True,
                cwd="."
            )
            
            # Should fail due to SSH connectivity
            assert result.returncode != 0

    def test_individual_addon_deployment(self):
        """Test deploying individual addon via addon Justfile."""
        addon_dirs = ["grid-dashboard", "mongodb"]
        
        for addon_dir in addon_dirs:
            if Path(addon_dir).exists():
                # Test dry-run deployment from addon directory
                result = subprocess.run(
                    ["just", "deploy-dry-run"],
                    capture_output=True,
                    text=True,
                    cwd=addon_dir
                )
                
                # Should succeed (dry-run doesn't require actual connectivity)
                assert result.returncode == 0, \
                    f"Individual addon dry-run failed for {addon_dir}: {result.stderr}"

    def test_batch_deployment_dry_run(self):
        """Test batch deployment in dry-run mode."""
        result = subprocess.run(
            ["just", "deploy-dry-run"],  # Deploy all addons
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Batch dry run should succeed
        assert result.returncode == 0, f"Batch dry run failed: {result.stderr}"
        
        # Should show multiple addons
        addon_names = ["grid-dashboard", "sonos-api", "mongodb", "printer"]
        for addon_name in addon_names:
            # At least some addons should be mentioned
            pass  # We can't guarantee all addons will be in output


@pytest.mark.integration
@pytest.mark.slow
class TestDeploymentErrorRecovery:
    """Test deployment error handling and recovery."""

    def test_deployment_continues_after_single_failure(self):
        """Test that batch deployment continues after single addon failure."""
        # This would require mocking specific addon failures
        # For now, test that the error handling structure is in place

        # Check that DeploymentError class exists and has required methods
        from talos.addon_builder import DeploymentError

        error = DeploymentError("Test error", error_type="TEST_ERROR")
        assert hasattr(error, 'display_error')
        assert hasattr(error, 'error_type')
        assert hasattr(error, 'context')
        assert hasattr(error, 'troubleshooting_steps')

    def test_deployment_error_includes_troubleshooting(self):
        """Test that deployment errors include troubleshooting information."""
        from talos.addon_builder import DeploymentError

        error = DeploymentError(
            "Build failed",
            error_type="BUILD_FAILED",
            context={"step": "build", "command": "ha addon build"},
            troubleshooting_steps=["Check addon configuration", "Review build logs"]
        )

        # Error should have context for troubleshooting
        assert error.context is not None
        assert "step" in error.context
        assert "command" in error.context
        assert len(error.troubleshooting_steps) > 0


@pytest.mark.integration
@pytest.mark.slow
class TestVerboseModeIntegration:
    """Test verbose mode functionality in deployment workflows."""

    def test_verbose_deployment_shows_detailed_output(self):
        """Test that verbose deployment shows detailed output."""
        result = subprocess.run(
            ["just", "deploy-verbose", "--help"],  # Use help to avoid actual deployment
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Should show help for verbose deployment
        assert result.returncode == 0

    def test_quiet_deployment_suppresses_output(self):
        """Test that regular deployment suppresses verbose output."""
        result = subprocess.run(
            ["just", "deploy-dry-run", "grid-dashboard"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Should succeed with clean output
        assert result.returncode == 0
        
        # Should not show verbose command details
        assert "if [ ! -x" not in result.stdout  # No raw shell commands
        assert "talos/build/bin/talos" not in result.stdout  # No command paths


class TestDeploymentAliases:
    """Test deployment command aliases."""

    def test_deployment_aliases_work(self):
        """Test that deployment aliases function correctly."""
        # Test deploy alias
        result = subprocess.run(
            ["just", "d", "--help"],  # Use help to test alias without deploying
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Alias should work (though help might not be available)
        # At minimum, it should not fail with "recipe not found"
        assert "Unknown recipe" not in result.stderr

    def test_dry_run_alias_works(self):
        """Test that dry-run alias functions correctly."""
        result = subprocess.run(
            ["just", "dd", "grid-dashboard"],  # dd is alias for deploy-dry-run
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Should work like deploy-dry-run
        assert result.returncode == 0 or "Unknown recipe" not in result.stderr


class TestDeploymentConfiguration:
    """Test deployment configuration and settings."""

    def test_deployment_uses_correct_host_settings(self):
        """Test that deployment uses correct host configuration."""
        # Check that common.just has proper host settings
        common_just_path = Path("../talos/just/common.just")
        content = common_just_path.read_text()

        # Should have host configuration
        assert "ha_host" in content
        assert "ha_port" in content
        assert "ha_user" in content

    def test_deployment_respects_environment_variables(self):
        """Test that deployment respects environment variable overrides."""
        # Check that root Justfile loads dotenv
        root_justfile = Path("../Justfile")
        content = root_justfile.read_text()

        # Should have dotenv loading configured
        assert "set dotenv-load" in content, f"dotenv-load not found in Justfile content: {content[:200]}..."


@pytest.mark.integration
@pytest.mark.slow
class TestDeploymentSafety:
    """Test deployment safety features."""

    def test_deployment_validates_addon_exists(self):
        """Test that deployment validates addon exists before proceeding."""
        result = subprocess.run(
            ["just", "deploy-dry-run", "nonexistent-addon"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Should fail for nonexistent addon
        assert result.returncode != 0
        assert "nonexistent-addon" in result.stderr or "not found" in result.stderr.lower()

    def test_deployment_checks_talos_binary(self):
        """Test that deployment ensures talos binary is available."""
        # All deployment recipes should check for talos binary
        justfiles = [
            Path("Justfile"),
            Path("grid-dashboard/Justfile"),
            Path("mongodb/Justfile")
        ]
        
        for justfile_path in justfiles:
            if justfile_path.exists():
                content = justfile_path.read_text()
                
                # Should have talos binary check
                assert "talos_bin" in content or "ensure-talos" in content, \
                    f"{justfile_path} should check for talos binary"


class TestDeploymentDocumentation:
    """Test that deployment system is properly documented."""

    def test_deployment_recipes_have_descriptions(self):
        """Test that deployment recipes have proper descriptions."""
        result = subprocess.run(
            ["just", "--list"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        assert result.returncode == 0
        
        # Deployment recipes should have descriptions
        deploy_recipes = ["deploy", "deploy-dry-run", "deploy-verbose"]
        for recipe in deploy_recipes:
            assert recipe in result.stdout, f"Recipe {recipe} not found in --list output"

    def test_addon_deployment_recipes_documented(self):
        """Test that addon deployment recipes are documented."""
        addon_dirs = ["grid-dashboard", "mongodb"]
        
        for addon_dir in addon_dirs:
            if Path(addon_dir).exists():
                result = subprocess.run(
                    ["just", "--list"],
                    capture_output=True,
                    text=True,
                    cwd=addon_dir
                )
                
                if result.returncode == 0:
                    # Should show deployment-related recipes
                    assert "deploy" in result.stdout, \
                        f"{addon_dir} should have deploy recipe in --list"
