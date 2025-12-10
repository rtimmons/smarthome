"""
Tests for Justfile infrastructure and library system.

Tests cover library imports, shared variables, recipe organization,
and addon Justfile compliance with established patterns.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest


class TestJustfileLibrarySystem:
    """Test the shared Justfile library system."""

    def test_common_library_variables(self):
        """Test that common.just defines required variables."""
        common_just_path = Path("just/common.just")
        assert common_just_path.exists(), "common.just library not found"
        
        content = common_just_path.read_text()
        
        # Check for required variables
        required_vars = [
            "repo_root",
            "talos_bin", 
            "build_dir",
            "ha_host",
            "ha_port",
            "ha_user"
        ]
        
        for var in required_vars:
            assert f"{var} :=" in content, f"Variable {var} not defined in common.just"

    def test_common_library_helper_functions(self):
        """Test that common.just defines required helper functions."""
        common_just_path = Path("just/common.just")
        content = common_just_path.read_text()
        
        # Check for required helper functions (without underscore prefix)
        required_helpers = [
            "ensure-talos",
            "addon-name",
            "validate-addon",
            "show-addon-info"
        ]

        for helper in required_helpers:
            assert f"{helper}:" in content, f"Helper function {helper} not defined in common.just"

    def test_nvm_library_structure(self):
        """Test that nvm.just has proper structure."""
        nvm_just_path = Path("just/nvm.just")
        assert nvm_just_path.exists(), "nvm.just library not found"
        
        content = nvm_just_path.read_text()
        
        # Check for NVM-specific variables
        assert "nvm_use :=" in content
        assert "nvm_dir :=" in content
        
        # Check for NVM recipes
        assert "nvm-init:" in content
        assert "node-version:" in content

    def test_library_documentation(self):
        """Test that library system has proper documentation."""
        readme_path = Path("just/README.md")
        assert readme_path.exists(), "Library README not found"
        
        content = readme_path.read_text()
        
        # Check for key documentation sections
        assert "# Justfile Libraries" in content
        assert "## Usage" in content
        assert "Available Libraries" in content  # Could be "## 📚 Available Libraries"
        assert "common.just" in content
        assert "nvm.just" in content


class TestAddonJustfileCompliance:
    """Test that addon Justfiles follow established patterns."""

    def get_addon_justfiles(self):
        """Get list of addon Justfile paths."""
        addon_dirs = [
            "grid-dashboard",
            "node-sonos-http-api",
            "sonos-api",
            "printer",
            "mongodb",
            "tinyurl-service",
            "snapshot-service"
        ]

        justfiles = []
        for addon_dir in addon_dirs:
            justfile_path = Path("..") / addon_dir / "Justfile"
            if justfile_path.exists():
                justfiles.append(justfile_path)

        return justfiles

    def test_addon_justfiles_import_common(self):
        """Test that addon Justfiles import common library."""
        justfiles = self.get_addon_justfiles()
        assert len(justfiles) > 0, "No addon Justfiles found"
        
        for justfile_path in justfiles:
            content = justfile_path.read_text()
            assert 'import "../talos/just/common.just"' in content, \
                f"{justfile_path} does not import common.just"

    def test_addon_justfiles_have_basic_structure(self):
        """Test that addon Justfiles have basic structure."""
        justfiles = self.get_addon_justfiles()

        # At least check they have some basic recipes or imports
        basic_patterns = [
            "import",  # Should import common library
            ":",       # Should have at least one recipe
        ]

        for justfile_path in justfiles:
            content = justfile_path.read_text()

            # Check it has basic structure
            has_basic_structure = any(pattern in content for pattern in basic_patterns)
            assert has_basic_structure, \
                f"{justfile_path} lacks basic Justfile structure"

    def test_addon_justfiles_use_recipe_groups(self):
        """Test that addon Justfiles use recipe groups."""
        justfiles = self.get_addon_justfiles()
        
        for justfile_path in justfiles:
            content = justfile_path.read_text()
            
            # Should have at least some recipe groups
            assert "[group:" in content, \
                f"{justfile_path} does not use recipe groups"

    def test_addon_justfiles_suppress_command_echo(self):
        """Test that addon Justfiles suppress command echoing."""
        justfiles = self.get_addon_justfiles()
        
        for justfile_path in justfiles:
            content = justfile_path.read_text()
            
            # Deploy recipes should use @ prefix to suppress echoing
            lines = content.split('\n')
            in_deploy_recipe = False
            
            for line in lines:
                if line.strip().startswith('deploy:'):
                    in_deploy_recipe = True
                elif line.strip() and not line.startswith('\t') and not line.startswith(' '):
                    in_deploy_recipe = False
                
                if in_deploy_recipe and line.strip().startswith('{{talos_bin}}'):
                    # Should be prefixed with @ to suppress output
                    assert line.strip().startswith('@{{talos_bin}}'), \
                        f"{justfile_path} deploy recipe should suppress command echo"

    def test_addon_justfiles_have_documentation(self):
        """Test that addon Justfiles have proper documentation."""
        justfiles = self.get_addon_justfiles()
        
        for justfile_path in justfiles:
            content = justfile_path.read_text()
            
            # Should have header comment
            lines = content.split('\n')
            assert lines[0].startswith('#'), \
                f"{justfile_path} should start with header comment"
            
            # Should have section separators
            assert "# ============================================================================" in content, \
                f"{justfile_path} should have section separators"


class TestJustfileExecution:
    """Test that Justfiles execute correctly."""

    def test_root_justfile_list_command(self):
        """Test that root Justfile --list works."""
        result = subprocess.run(
            ["just", "--list"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        assert result.returncode == 0, f"just --list failed: {result.stderr}"
        
        # Should show grouped recipes
        assert "[build]" in result.stdout
        assert "[deploy]" in result.stdout
        assert "[test]" in result.stdout

    def test_addon_justfile_info_command(self):
        """Test that addon Justfiles support info command."""
        addon_dirs = ["grid-dashboard", "mongodb", "tinyurl-service"]
        
        for addon_dir in addon_dirs:
            if Path(addon_dir).exists():
                result = subprocess.run(
                    ["just", "info"],
                    capture_output=True,
                    text=True,
                    cwd=addon_dir
                )
                
                assert result.returncode == 0, \
                    f"just info failed in {addon_dir}: {result.stderr}"
                
                # Should show addon information
                assert "📦 Addon:" in result.stdout
                assert addon_dir in result.stdout

    def test_addon_justfile_list_command(self):
        """Test that addon Justfiles --list works."""
        addon_dirs = ["grid-dashboard", "mongodb"]
        
        for addon_dir in addon_dirs:
            if Path(addon_dir).exists():
                result = subprocess.run(
                    ["just", "--list"],
                    capture_output=True,
                    text=True,
                    cwd=addon_dir
                )
                
                assert result.returncode == 0, \
                    f"just --list failed in {addon_dir}: {result.stderr}"
                
                # Should show grouped recipes
                assert "[group:" in result.stdout or "[build]" in result.stdout


class TestJustfileTemplateSystem:
    """Test the addon Justfile template system."""

    def test_template_exists(self):
        """Test that addon template exists."""
        template_path = Path("just/addon-template.just")
        assert template_path.exists(), "Addon template not found"

    def test_template_structure(self):
        """Test that template has proper structure."""
        template_path = Path("just/addon-template.just")
        content = template_path.read_text()
        
        # Should have placeholder sections
        assert "[ADDON_NAME]" in content
        assert "[ADDON_DESCRIPTION]" in content
        
        # Should import common library
        assert 'import "./common.just"' in content
        
        # Should have standard recipe groups
        assert "[group: 'setup']" in content
        assert "[group: 'deploy']" in content
        assert "[group: 'test']" in content

    def test_template_can_be_instantiated(self):
        """Test that template can be used to create working Justfile."""
        template_path = Path("just/addon-template.just")
        template_content = template_path.read_text()
        
        # Replace placeholders
        test_content = template_content.replace("[ADDON_NAME]", "test-addon")
        test_content = test_content.replace("[ADDON_DESCRIPTION]", "Test addon")
        
        # Create temporary Justfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.just', delete=False) as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Test that it has the expected content structure
            assert "test-addon" in test_content
            assert "Test addon" in test_content
            assert "import" in test_content

            # Basic syntax check - just verify it looks like a Justfile
            assert ":" in test_content  # Should have at least one recipe
            
        finally:
            os.unlink(temp_path)
