#!/usr/bin/env python3
"""Tests for Task 48: Dependency Auto-Update Service.

This test suite validates the automated dependency security patch checking
and PR creation functionality.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add the scripts directory to the path for importing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dependency_auto_update import (
    DependencyUpdater,
    SecurityScanner,
    GitHubAPI,
    DependencyUpdateError,
    REPO_ROOT
)


class TestSecurityScanner(unittest.TestCase):
    """Test the SecurityScanner class."""

    def setUp(self):
        self.scanner = SecurityScanner()

    @patch('subprocess.run')
    def test_check_pip_audit_available(self, mock_run):
        """Test pip-audit availability check."""
        # Test when pip-audit is available
        mock_run.return_value = Mock(returncode=0)
        scanner = SecurityScanner()
        self.assertTrue(scanner.pip_audit_available)

        # Test when pip-audit is not available but can be installed
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, 'pip-audit'),  # Not found
            Mock(returncode=0)  # Installation succeeds
        ]
        scanner = SecurityScanner()
        self.assertTrue(scanner.pip_audit_available)

    @patch('subprocess.run')
    def test_scan_requirements_no_vulnerabilities(self, mock_run):
        """Test scanning when no vulnerabilities are found."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("requests==2.28.0\n")
            f.flush()

            has_vulns, vulns = self.scanner.scan_requirements(Path(f.name))
            self.assertFalse(has_vulns)
            self.assertEqual(vulns, [])

        os.unlink(f.name)

    @patch('subprocess.run')
    def test_scan_requirements_with_vulnerabilities(self, mock_run):
        """Test scanning when vulnerabilities are found."""
        mock_vulnerabilities = [
            {
                "name": "flask",
                "version": "0.5",
                "vulns": [
                    {
                        "id": "PYSEC-2019-179",
                        "fix_versions": ["1.0"],
                        "description": "Security vulnerability in Flask"
                    }
                ]
            }
        ]

        mock_run.return_value = Mock(
            returncode=1,
            stdout=json.dumps(mock_vulnerabilities),
            stderr=""
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("flask==0.5\n")
            f.flush()

            has_vulns, vulns = self.scanner.scan_requirements(Path(f.name))
            self.assertTrue(has_vulns)
            self.assertEqual(len(vulns), 1)
            self.assertEqual(vulns[0]['name'], 'flask')

        os.unlink(f.name)

    @patch('subprocess.run')
    def test_scan_requirements_error(self, mock_run):
        """Test scanning when an error occurs."""
        mock_run.return_value = Mock(returncode=2, stdout="", stderr="Error occurred")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("requests==2.28.0\n")
            f.flush()

            with self.assertRaises(DependencyUpdateError):
                self.scanner.scan_requirements(Path(f.name))

        os.unlink(f.name)


class TestGitHubAPI(unittest.TestCase):
    """Test the GitHubAPI class."""

    def setUp(self):
        self.github = GitHubAPI("fake-token", "owner/repo")

    @patch('requests.post')
    def test_create_pull_request(self, mock_post):
        """Test creating a pull request."""
        mock_response = Mock()
        mock_response.json.return_value = {"number": 123, "html_url": "https://github.com/owner/repo/pull/123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        pr = self.github.create_pull_request("Test PR", "Test body", "test-branch")

        self.assertEqual(pr["number"], 123)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_add_labels_to_pr(self, mock_post):
        """Test adding labels to a PR."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        self.github.add_labels_to_pr(123, ["security", "dependencies"])

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("labels", call_args[1]["json"])

    @patch('requests.get')
    def test_get_existing_prs(self, mock_get):
        """Test getting existing PRs."""
        mock_response = Mock()
        mock_response.json.return_value = [{"number": 123, "title": "Security Update"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        prs = self.github.get_existing_prs("security-update")

        self.assertEqual(len(prs), 1)
        self.assertEqual(prs[0]["number"], 123)


class TestDependencyUpdater(unittest.TestCase):
    """Test the DependencyUpdater class."""

    def setUp(self):
        self.updater = DependencyUpdater("fake-token", "owner/repo", dry_run=True)

    @patch.object(SecurityScanner, 'scan_requirements')
    def test_check_for_updates_no_vulnerabilities(self, mock_scan):
        """Test checking for updates when no vulnerabilities exist."""
        mock_scan.return_value = (False, [])

        has_vulns, vulns = self.updater.check_for_updates()

        self.assertFalse(has_vulns)
        self.assertEqual(vulns, [])

    @patch.object(SecurityScanner, 'scan_requirements')
    def test_check_for_updates_with_vulnerabilities(self, mock_scan):
        """Test checking for updates when vulnerabilities exist."""
        mock_vulnerabilities = [
            {
                "name": "flask",
                "version": "0.5",
                "vulns": [{"id": "PYSEC-2019-179", "fix_versions": ["1.0"]}]
            }
        ]
        mock_scan.return_value = (True, mock_vulnerabilities)

        has_vulns, vulns = self.updater.check_for_updates()

        self.assertTrue(has_vulns)
        self.assertEqual(len(vulns), 1)

    def test_generate_pr_body(self):
        """Test PR body generation."""
        vulnerabilities = [
            {
                "name": "flask",
                "version": "0.5",
                "vulns": [
                    {
                        "id": "PYSEC-2019-179",
                        "fix_versions": ["1.0"],
                        "description": "Security vulnerability in Flask"
                    }
                ]
            }
        ]

        body = self.updater._generate_pr_body(vulnerabilities)

        self.assertIn("Security Update", body)
        self.assertIn("flask", body)
        self.assertIn("PYSEC-2019-179", body)
        self.assertIn("Task 48", body)

    @patch.object(GitHubAPI, 'get_existing_prs')
    def test_create_security_pr_dry_run(self, mock_get_prs):
        """Test creating security PR in dry-run mode."""
        mock_get_prs.return_value = []
        vulnerabilities = [{"name": "flask", "version": "0.5", "vulns": []}]

        pr = self.updater.create_security_pr(vulnerabilities)

        self.assertIsNone(pr)  # Should return None in dry-run mode

    @patch.object(GitHubAPI, 'get_existing_prs')
    def test_create_security_pr_existing_pr(self, mock_get_prs):
        """Test creating security PR when one already exists."""
        existing_pr = {"number": 123, "title": "Security Update"}
        mock_get_prs.return_value = [existing_pr]

        # Temporarily disable dry-run mode
        self.updater.dry_run = False
        vulnerabilities = [{"name": "flask", "version": "0.5", "vulns": []}]

        pr = self.updater.create_security_pr(vulnerabilities)

        self.assertEqual(pr, existing_pr)


class TestDependencyAutoUpdateIntegration(unittest.TestCase):
    """Integration tests for the dependency auto-update service."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.requirements_in = Path(self.test_dir) / "requirements.in"
        self.requirements_txt = Path(self.test_dir) / "requirements.txt"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def test_update_requirements_in(self):
        """Test updating requirements.in with fixed versions."""
        # Create test requirements.in
        self.requirements_in.write_text("flask==0.5\nrequests>=2.0.0\n")

        vulnerabilities = [
            {
                "name": "flask",
                "version": "0.5",
                "vulns": [{"fix_versions": ["1.0"]}]
            }
        ]

        updater = DependencyUpdater("fake-token", "owner/repo", dry_run=True)

        # Patch the constants to use our test directory
        with patch('dependency_auto_update.REQUIREMENTS_IN', self.requirements_in):
            updated = updater._update_requirements_in(vulnerabilities)

        self.assertTrue(updated)
        content = self.requirements_in.read_text()
        self.assertIn("flask>=1.0", content)
        self.assertIn("requests>=2.0.0", content)  # Should remain unchanged


class TestWorkflowIntegration(unittest.TestCase):
    """Test the GitHub Actions workflow integration."""

    def test_workflow_file_exists(self):
        """Test that the workflow file exists and is valid."""
        workflow_file = REPO_ROOT / ".github" / "workflows" / "dependency_auto_update.yml"
        self.assertTrue(workflow_file.exists(), "Workflow file should exist")

        content = workflow_file.read_text()
        self.assertIn("Dependency Auto-Update Service", content)
        self.assertIn("cron:", content)
        self.assertIn("pip-audit", content)

    def test_script_executable(self):
        """Test that the dependency update script is executable."""
        script_file = REPO_ROOT / "scripts" / "dependency_auto_update.py"
        self.assertTrue(script_file.exists(), "Script file should exist")

        # Test that the script can be imported without errors
        try:
            import dependency_auto_update
            self.assertTrue(hasattr(dependency_auto_update, 'main'))
        except ImportError as e:
            self.fail(f"Script should be importable: {e}")


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)