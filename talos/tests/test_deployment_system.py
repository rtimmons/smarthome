"""
Minimal deployment system tests that focus on what actually exists.

These tests verify the core deployment functionality without mocking
functions that don't exist.
"""

import subprocess

import pytest
from unittest.mock import Mock, patch
from talos import addon_builder
from talos.addon_builder import DeploymentError


class TestDeploymentError:
    """Test DeploymentError functionality."""
    
    def test_deployment_error_creation(self):
        """Test DeploymentError creation with context."""
        error = DeploymentError(
            "Deployment failed",
            error_type="DEPLOYMENT_FAILED",
            context={"step": "build", "command": "ha addon build"},
            troubleshooting_steps=["Check addon configuration", "Review build logs"]
        )
        
        assert str(error) == "Deployment failed"
        assert error.error_type == "DEPLOYMENT_FAILED"
        assert error.context["step"] == "build"
        assert len(error.troubleshooting_steps) == 2

    def test_deployment_error_display(self, capsys):
        """Test error display formatting."""
        error = DeploymentError(
            "Test error",
            error_type="TEST_ERROR",
            context={"addon": "test-addon"},
            troubleshooting_steps=["Step 1", "Step 2"]
        )
        
        error.display_error()
        captured = capsys.readouterr()
        
        assert "❌ Deployment Error" in captured.out
        assert "TEST_ERROR" in captured.out
        assert "Test error" in captured.out


class TestDeploymentValidation:
    """Test deployment validation functionality."""
    
    def test_validate_deployment_prerequisites_success(self, monkeypatch):
        """Test successful prerequisite validation."""
        # Mock successful SSH and HA core checks
        mock_run = Mock(side_effect=[
            Mock(returncode=0, stdout="", stderr=""),  # SSH test succeeds
            Mock(returncode=0, stdout='{"result": "ok", "data": {"version": "2025.12.1"}}', stderr=""),  # HA core check succeeds
            Mock(returncode=0, stdout="Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        100G   20G   77G  21% /", stderr="")  # Disk space check
        ])
        monkeypatch.setattr("subprocess.run", mock_run)
        
        # Should not raise an exception
        addon_builder.validate_deployment_prerequisites("homeassistant.local", 22, "root")

        first_command = mock_run.call_args_list[0].args[0]
        assert first_command[:2] == ["ssh", "-i"]
        assert str(addon_builder.DEFAULT_HA_SSH_IDENTITY) in first_command
        assert "IdentitiesOnly=yes" in first_command
    
    def test_validate_deployment_prerequisites_auth_failure_requires_key_copy(self, monkeypatch):
        """Authentication failures stop and point to the dedicated-key setup."""
        mock_run = Mock(
            side_effect=subprocess.CalledProcessError(
                255,
                ["ssh"],
                stderr="Permission denied (publickey)",
            )
        )
        monkeypatch.setattr("subprocess.run", mock_run)
        
        with pytest.raises(DeploymentError) as exc_info:
            addon_builder.validate_deployment_prerequisites("homeassistant.local", 22, "root")

        error = exc_info.value
        assert error.error_type == "SSH_AUTHENTICATION_FAILED"
        assert any("just ha-ssh-key-copy" in step for step in error.troubleshooting_steps)
        assert not any("unlock 1Password" in step for step in error.troubleshooting_steps)

    def test_validate_deployment_prerequisites_dns_failure_is_not_auth(self, monkeypatch):
        """mDNS failures preserve the hostname and do not blame 1Password."""
        mock_run = Mock(
            side_effect=subprocess.CalledProcessError(
                255,
                ["ssh"],
                stderr="ssh: Could not resolve hostname homeassistant.local",
            )
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        with pytest.raises(DeploymentError) as exc_info:
            addon_builder.validate_deployment_prerequisites("homeassistant.local", 22, "root")

        error = exc_info.value
        assert error.error_type == "SSH_HOSTNAME_RESOLUTION_FAILED"
        assert any("outside the Codex sandbox" in step for step in error.troubleshooting_steps)
        assert any("Do not substitute an IP" in step for step in error.troubleshooting_steps)
        assert any("id_ed25519_codex_smarthome" in step for step in error.troubleshooting_steps)
        assert not any("unlock 1Password" in step for step in error.troubleshooting_steps)

    def test_home_assistant_transport_supports_identity_override(self, monkeypatch):
        monkeypatch.setenv("HASS_SSH_IDENTITY", "/tmp/test-home-assistant-key")

        assert addon_builder.ssh_transport_args(2222) == [
            "-i", "/tmp/test-home-assistant-key",
            "-o", "IdentitiesOnly=yes",
            "-p", "2222",
        ]
        assert addon_builder.scp_transport_args(2222) == [
            "-i", "/tmp/test-home-assistant-key",
            "-o", "IdentitiesOnly=yes",
            "-P", "2222",
        ]

    @pytest.mark.parametrize(
        ("stderr", "expected"),
        [
            ("sign_and_send_pubkey: agent refused operation", "SSH_AUTHENTICATION_FAILED"),
            ("Warning: Identity file /missing not accessible", "SSH_AUTHENTICATION_FAILED"),
            ("connect to host homeassistant.local port 22: Connection refused", "SSH_CONNECTION_FAILED"),
            ("Temporary failure in name resolution", "SSH_HOSTNAME_RESOLUTION_FAILED"),
        ],
    )
    def test_classify_ssh_failure(self, stderr, expected):
        assert addon_builder.classify_ssh_failure(stderr) == expected


class TestAddonDiscovery:
    """Test addon discovery functionality."""
    
    def test_discover_addons_returns_dict(self):
        """Test that discover_addons returns a dictionary."""
        addons = addon_builder.discover_addons()
        
        assert isinstance(addons, dict)
        # Should have at least some addons
        assert len(addons) > 0
        
        # Each addon should have required keys
        for addon_name, addon_data in addons.items():
            assert isinstance(addon_name, str)
            assert isinstance(addon_data, dict)


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_deployment_error_has_required_attributes(self):
        """Test that DeploymentError has all required attributes."""
        error = DeploymentError("Test message")
        
        # Check required attributes exist
        assert hasattr(error, 'error_type')
        assert hasattr(error, 'context')
        assert hasattr(error, 'troubleshooting_steps')
        assert hasattr(error, 'timestamp')
        assert hasattr(error, 'display_error')
        
        # Check default values
        assert error.error_type == "DEPLOYMENT_ERROR"
        assert error.context == {}
        assert error.troubleshooting_steps == []
    
    def test_deployment_error_with_all_parameters(self):
        """Test DeploymentError with all parameters."""
        context = {"addon": "test", "step": "build"}
        steps = ["Step 1", "Step 2"]
        
        error = DeploymentError(
            "Test message",
            error_type="CUSTOM_ERROR",
            context=context,
            troubleshooting_steps=steps
        )
        
        assert str(error) == "Test message"
        assert error.error_type == "CUSTOM_ERROR"
        assert error.context == context
        assert error.troubleshooting_steps == steps


@pytest.mark.unit
class TestBasicFunctionality:
    """Test basic functionality that should always work."""
    
    def test_addon_builder_module_imports(self):
        """Test that addon_builder module imports correctly."""
        # These should not raise ImportError
        from talos.addon_builder import DeploymentError, discover_addons, validate_deployment_prerequisites
        
        # Check they are callable
        assert callable(discover_addons)
        assert callable(validate_deployment_prerequisites)
    
    def test_deployment_error_inheritance(self):
        """Test that DeploymentError inherits from Exception."""
        error = DeploymentError("Test")
        
        assert isinstance(error, Exception)
        assert isinstance(error, DeploymentError)
    
    def test_module_has_required_exports(self):
        """Test that module exports required functions."""
        import talos.addon_builder as ab
        
        required_functions = [
            'discover_addons',
            'validate_deployment_prerequisites'
        ]
        
        required_classes = [
            'DeploymentError'
        ]
        
        for func_name in required_functions:
            assert hasattr(ab, func_name), f"Missing function: {func_name}"
            assert callable(getattr(ab, func_name)), f"Not callable: {func_name}"
        
        for class_name in required_classes:
            assert hasattr(ab, class_name), f"Missing class: {class_name}"
            assert isinstance(getattr(ab, class_name), type), f"Not a class: {class_name}"
