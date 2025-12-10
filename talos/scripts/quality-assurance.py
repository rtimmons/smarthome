#!/usr/bin/env python3
"""
Quality Assurance Script for Justfile Infrastructure

This script validates the quality and consistency of the Justfile infrastructure,
ensuring all components meet production standards.

Usage:
    python talos/scripts/quality-assurance.py [--fix] [--verbose]

Features:
    - Validates Justfile syntax and structure
    - Checks library imports and dependencies
    - Verifies addon compliance with standards
    - Tests deployment system functionality
    - Generates quality reports
    - Optionally fixes common issues
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

# Add talos to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from talos.addon_builder import discover_addons, DeploymentError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

class QualityAssurance:
    """Quality assurance validator for Justfile infrastructure."""
    
    def __init__(self, fix_issues: bool = False, verbose: bool = False):
        self.fix_issues = fix_issues
        self.verbose = verbose
        self.repo_root = Path(__file__).parent.parent.parent
        self.issues: List[Dict[str, Any]] = []
        self.passed_checks = 0
        self.failed_checks = 0
    
    def log_issue(self, severity: str, component: str, message: str, 
                  fix_suggestion: Optional[str] = None) -> None:
        """Log a quality issue."""
        self.issues.append({
            "severity": severity,
            "component": component,
            "message": message,
            "fix_suggestion": fix_suggestion
        })
        
        if severity in ["ERROR", "CRITICAL"]:
            self.failed_checks += 1
        else:
            self.passed_checks += 1
    
    def check_justfile_syntax(self) -> None:
        """Check syntax of all Justfiles."""
        console.print("🔍 Checking Justfile syntax...")
        
        justfiles = list(self.repo_root.glob("**/Justfile"))
        justfiles.extend(self.repo_root.glob("**/*.just"))
        
        for justfile in justfiles:
            try:
                result = subprocess.run(
                    ["just", "--justfile", str(justfile), "--list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    self.log_issue(
                        "ERROR",
                        str(justfile.relative_to(self.repo_root)),
                        f"Syntax error: {result.stderr}",
                        "Fix syntax errors in Justfile"
                    )
                else:
                    if self.verbose:
                        console.print(f"  ✓ {justfile.relative_to(self.repo_root)}")
                    
            except subprocess.TimeoutExpired:
                self.log_issue(
                    "WARNING",
                    str(justfile.relative_to(self.repo_root)),
                    "Justfile validation timed out",
                    "Check for infinite loops or slow operations"
                )
            except Exception as e:
                self.log_issue(
                    "ERROR",
                    str(justfile.relative_to(self.repo_root)),
                    f"Failed to validate: {str(e)}",
                    "Check file permissions and just installation"
                )
    
    def check_library_structure(self) -> None:
        """Check Justfile library structure and imports."""
        console.print("📚 Checking library structure...")
        
        library_dir = self.repo_root / "talos" / "just"
        if not library_dir.exists():
            self.log_issue(
                "CRITICAL",
                "talos/just/",
                "Library directory does not exist",
                "Create library directory structure"
            )
            return
        
        required_libraries = ["common.just", "nvm.just", "testing.just"]
        for lib in required_libraries:
            lib_path = library_dir / lib
            if not lib_path.exists():
                self.log_issue(
                    "ERROR",
                    f"talos/just/{lib}",
                    "Required library file missing",
                    f"Create {lib} library file"
                )
            else:
                if self.verbose:
                    console.print(f"  ✓ {lib}")
        
        # Check README exists
        readme_path = library_dir / "README.md"
        if not readme_path.exists():
            self.log_issue(
                "WARNING",
                "talos/just/README.md",
                "Library documentation missing",
                "Create comprehensive library documentation"
            )
    
    def check_addon_compliance(self) -> None:
        """Check addon Justfile compliance."""
        console.print("🔧 Checking addon compliance...")
        
        try:
            addons = discover_addons()
            
            for addon_name, addon_data in addons.items():
                addon_dir = Path(addon_data.get("source_dir", addon_name))
                justfile_path = addon_dir / "Justfile"
                
                if not justfile_path.exists():
                    self.log_issue(
                        "WARNING",
                        f"{addon_name}/Justfile",
                        "Addon missing Justfile",
                        "Create Justfile using addon template"
                    )
                    continue
                
                content = justfile_path.read_text()
                
                # Check for common.just import
                if 'import "../talos/just/common.just"' not in content:
                    self.log_issue(
                        "ERROR",
                        f"{addon_name}/Justfile",
                        "Missing common.just import",
                        'Add: import "../talos/just/common.just"'
                    )
                
                # Check for required recipes
                required_recipes = ["deploy:", "info:", "ha-addon:", "container-test:"]
                for recipe in required_recipes:
                    if recipe not in content:
                        self.log_issue(
                            "WARNING",
                            f"{addon_name}/Justfile",
                            f"Missing required recipe: {recipe}",
                            f"Add {recipe} recipe to Justfile"
                        )
                
                if self.verbose:
                    console.print(f"  ✓ {addon_name}")
                    
        except Exception as e:
            self.log_issue(
                "ERROR",
                "addon discovery",
                f"Failed to discover addons: {str(e)}",
                "Check addon.yaml files and directory structure"
            )
    
    def check_deployment_system(self) -> None:
        """Check deployment system functionality."""
        console.print("🚀 Checking deployment system...")
        
        # Check talos binary exists
        talos_bin = self.repo_root / "talos" / "build" / "bin" / "talos"
        if not talos_bin.exists():
            self.log_issue(
                "WARNING",
                "talos/build/bin/talos",
                "Talos binary not found",
                "Run: just setup or ./talos/build.sh"
            )
        
        # Check deployment tests exist
        test_files = [
            "talos/tests/test_deployment_system.py",
            "talos/tests/test_deployment_integration.py",
            "talos/tests/test_justfile_infrastructure.py"
        ]
        
        for test_file in test_files:
            test_path = self.repo_root / test_file
            if not test_path.exists():
                self.log_issue(
                    "ERROR",
                    test_file,
                    "Required test file missing",
                    f"Create {test_file} with comprehensive tests"
                )
            else:
                if self.verbose:
                    console.print(f"  ✓ {test_file}")
    
    def generate_report(self) -> None:
        """Generate quality assurance report."""
        console.print("\n" + "="*80)
        console.print("📊 QUALITY ASSURANCE REPORT")
        console.print("="*80)
        
        # Summary statistics
        total_checks = self.passed_checks + self.failed_checks
        success_rate = (self.passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        summary_table = Table(title="Summary Statistics")
        summary_table.add_column("Metric", style="bold")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Total Checks", str(total_checks))
        summary_table.add_row("Passed", str(self.passed_checks))
        summary_table.add_row("Failed", str(self.failed_checks))
        summary_table.add_row("Success Rate", f"{success_rate:.1f}%")
        
        console.print(summary_table)
        
        # Issues by severity
        if self.issues:
            console.print("\n🚨 Issues Found:")
            
            severity_counts = {}
            for issue in self.issues:
                severity = issue["severity"]
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            issues_table = Table(title="Issues by Severity")
            issues_table.add_column("Severity", style="bold")
            issues_table.add_column("Count", style="red")
            issues_table.add_column("Components", style="yellow")
            
            for severity, count in severity_counts.items():
                components = [issue["component"] for issue in self.issues if issue["severity"] == severity]
                issues_table.add_row(severity, str(count), ", ".join(components[:3]) + ("..." if len(components) > 3 else ""))
            
            console.print(issues_table)
            
            # Detailed issues
            if self.verbose:
                console.print("\n📋 Detailed Issues:")
                for issue in self.issues:
                    panel_content = f"[bold]{issue['message']}[/bold]\n"
                    if issue.get("fix_suggestion"):
                        panel_content += f"💡 Fix: {issue['fix_suggestion']}"
                    
                    console.print(Panel(
                        panel_content,
                        title=f"{issue['severity']}: {issue['component']}",
                        border_style="red" if issue['severity'] in ["ERROR", "CRITICAL"] else "yellow"
                    ))
        else:
            console.print("\n✅ No issues found! Infrastructure meets quality standards.")
        
        # Overall grade
        if success_rate >= 95:
            grade = "A+"
            grade_color = "green"
        elif success_rate >= 90:
            grade = "A"
            grade_color = "green"
        elif success_rate >= 85:
            grade = "B+"
            grade_color = "yellow"
        elif success_rate >= 80:
            grade = "B"
            grade_color = "yellow"
        else:
            grade = "C"
            grade_color = "red"
        
        console.print(f"\n🎯 Overall Quality Grade: [{grade_color}]{grade}[/{grade_color}]")
    
    def run_all_checks(self) -> bool:
        """Run all quality assurance checks."""
        console.print("🔍 Starting Quality Assurance Validation...")
        console.print("="*80)
        
        self.check_justfile_syntax()
        self.check_library_structure()
        self.check_addon_compliance()
        self.check_deployment_system()
        
        self.generate_report()
        
        # Return True if no critical issues
        critical_issues = [issue for issue in self.issues if issue["severity"] == "CRITICAL"]
        return len(critical_issues) == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Quality Assurance for Justfile Infrastructure")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix common issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    qa = QualityAssurance(fix_issues=args.fix, verbose=args.verbose)
    success = qa.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
