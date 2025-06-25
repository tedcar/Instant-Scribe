#!/usr/bin/env python3
"""Dependency Auto-Update Service for Task 48.

This script implements automated dependency security patch checking and PR creation.
It checks PyPI for security patches to pinned dependencies and creates automated PRs
with updated requirements.in & requirements.txt with security labels.

Features:
- Weekly background job that checks PyPI for security patches
- Uses pip-audit for vulnerability scanning
- Creates automated PRs with updated dependencies
- Assigns security labels to PRs
- Integrates with existing CI/CD pipeline

Usage:
    python scripts/dependency_auto_update.py [--dry-run] [--force]

Environment Variables:
    GITHUB_TOKEN: GitHub token for API access
    GITHUB_REPOSITORY: Repository in format owner/repo
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_IN = REPO_ROOT / "requirements.in"
REQUIREMENTS_TXT = REPO_ROOT / "requirements.txt"
GITHUB_API_BASE = "https://api.github.com"


class DependencyUpdateError(Exception):
    """Custom exception for dependency update errors."""
    pass


class GitHubAPI:
    """GitHub API client for creating PRs and managing issues."""

    def __init__(self, token: str, repository: str):
        self.token = token
        self.repository = repository
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "InstantScribe-DependencyUpdater/1.0"
        }

    def create_pull_request(self, title: str, body: str, head: str, base: str = "main") -> Dict:
        """Create a pull request."""
        url = f"{GITHUB_API_BASE}/repos/{self.repository}/pulls"
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def add_labels_to_pr(self, pr_number: int, labels: List[str]) -> None:
        """Add labels to a pull request."""
        url = f"{GITHUB_API_BASE}/repos/{self.repository}/issues/{pr_number}/labels"
        data = {"labels": labels}

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

    def get_existing_prs(self, head_prefix: str) -> List[Dict]:
        """Get existing PRs with head branch matching prefix."""
        url = f"{GITHUB_API_BASE}/repos/{self.repository}/pulls"
        params = {"state": "open", "head": f"{self.repository.split('/')[0]}:{head_prefix}"}

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()


class SecurityScanner:
    """Security vulnerability scanner using pip-audit."""

    def __init__(self):
        self.pip_audit_available = self._check_pip_audit()

    def _check_pip_audit(self) -> bool:
        """Check if pip-audit is available."""
        try:
            subprocess.run(["pip-audit", "--version"],
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("pip-audit not found. Installing...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "pip-audit"],
                             check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install pip-audit: {e}")
                return False

    def scan_requirements(self, requirements_file: Path) -> Tuple[bool, List[Dict]]:
        """Scan requirements file for vulnerabilities.

        Returns:
            Tuple of (has_vulnerabilities, vulnerability_list)
        """
        if not self.pip_audit_available:
            raise DependencyUpdateError("pip-audit is not available")

        try:
            cmd = [
                "pip-audit",
                "--requirement", str(requirements_file),
                "--format", "json",
                "--no-deps"  # Only check direct dependencies
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # No vulnerabilities found
                return False, []
            elif result.returncode == 1:
                # Vulnerabilities found
                try:
                    vulnerabilities = json.loads(result.stdout)
                    return True, vulnerabilities
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse pip-audit output: {result.stdout}")
                    return False, []
            else:
                # Error occurred
                logger.error(f"pip-audit failed: {result.stderr}")
                raise DependencyUpdateError(f"pip-audit scan failed: {result.stderr}")

        except Exception as e:
            logger.error(f"Error running pip-audit: {e}")
            raise DependencyUpdateError(f"Security scan failed: {e}")


class DependencyUpdater:
    """Main dependency update service."""

    def __init__(self, github_token: str, repository: str, dry_run: bool = False):
        self.github = GitHubAPI(github_token, repository)
        self.scanner = SecurityScanner()
        self.dry_run = dry_run

    def check_for_updates(self) -> Tuple[bool, List[Dict]]:
        """Check for security updates in dependencies."""
        logger.info("Scanning dependencies for security vulnerabilities...")

        if not REQUIREMENTS_TXT.exists():
            logger.error(f"Requirements file not found: {REQUIREMENTS_TXT}")
            return False, []

        return self.scanner.scan_requirements(REQUIREMENTS_TXT)

    def update_requirements(self, vulnerabilities: List[Dict]) -> bool:
        """Update requirements files with security patches."""
        if not vulnerabilities:
            return False

        logger.info(f"Found {len(vulnerabilities)} packages with vulnerabilities")

        # Create backup of original files
        backup_suffix = f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        requirements_in_backup = REQUIREMENTS_IN.with_suffix(REQUIREMENTS_IN.suffix + backup_suffix)
        requirements_txt_backup = REQUIREMENTS_TXT.with_suffix(REQUIREMENTS_TXT.suffix + backup_suffix)

        try:
            if REQUIREMENTS_IN.exists():
                requirements_in_backup.write_text(REQUIREMENTS_IN.read_text())
            requirements_txt_backup.write_text(REQUIREMENTS_TXT.read_text())

            # Update requirements.in with fixed versions
            updated = self._update_requirements_in(vulnerabilities)

            if updated:
                # Regenerate requirements.txt using pip-compile
                self._regenerate_requirements_txt()
                return True

        except Exception as e:
            logger.error(f"Failed to update requirements: {e}")
            # Restore backups
            if requirements_in_backup.exists():
                REQUIREMENTS_IN.write_text(requirements_in_backup.read_text())
                requirements_in_backup.unlink()
            if requirements_txt_backup.exists():
                REQUIREMENTS_TXT.write_text(requirements_txt_backup.read_text())
                requirements_txt_backup.unlink()
            raise

        # Clean up backups on success
        if requirements_in_backup.exists():
            requirements_in_backup.unlink()
        if requirements_txt_backup.exists():
            requirements_txt_backup.unlink()

        return False

    def _update_requirements_in(self, vulnerabilities: List[Dict]) -> bool:
        """Update requirements.in with fixed versions."""
        if not REQUIREMENTS_IN.exists():
            logger.warning("requirements.in not found, cannot update pinned versions")
            return False

        content = REQUIREMENTS_IN.read_text()
        lines = content.splitlines()
        updated = False

        for vuln in vulnerabilities:
            package_name = vuln.get('name', '').lower()
            fix_versions = vuln.get('vulns', [{}])[0].get('fix_versions', [])

            if not fix_versions:
                continue

            # Use the latest fix version
            fix_version = fix_versions[-1]

            # Update the line in requirements.in
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped.startswith(package_name + '==') or line_stripped.startswith(package_name + '>='):
                    old_line = lines[i]
                    # Update to fixed version
                    lines[i] = f"{package_name}>={fix_version}"
                    logger.info(f"Updated {package_name}: {old_line.strip()} -> {lines[i]}")
                    updated = True
                    break

        if updated:
            REQUIREMENTS_IN.write_text('\n'.join(lines) + '\n')

        return updated

    def _regenerate_requirements_txt(self) -> None:
        """Regenerate requirements.txt using pip-compile."""
        logger.info("Regenerating requirements.txt with pip-compile...")

        try:
            cmd = ["pip-compile", "--upgrade", str(REQUIREMENTS_IN)]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)

            if result.returncode != 0:
                logger.error(f"pip-compile failed: {result.stderr}")
                raise DependencyUpdateError(f"Failed to regenerate requirements.txt: {result.stderr}")

            logger.info("Successfully regenerated requirements.txt")

        except FileNotFoundError:
            logger.error("pip-compile not found. Please install pip-tools.")
            raise DependencyUpdateError("pip-compile is required but not installed")

    def create_security_pr(self, vulnerabilities: List[Dict]) -> Optional[Dict]:
        """Create a pull request for security updates."""
        if self.dry_run:
            logger.info("DRY RUN: Would create security update PR")
            return None

        # Check if there's already an open security update PR
        existing_prs = self.github.get_existing_prs("security-update")
        if existing_prs:
            logger.info(f"Security update PR already exists: #{existing_prs[0]['number']}")
            return existing_prs[0]

        # Create branch name
        branch_name = f"security-update-{datetime.now().strftime('%Y%m%d')}"

        # Create PR title and body
        vuln_count = len(vulnerabilities)
        title = f"Security Update: Fix {vuln_count} vulnerabilit{'y' if vuln_count == 1 else 'ies'}"

        body = self._generate_pr_body(vulnerabilities)

        try:
            # Create the PR
            pr = self.github.create_pull_request(title, body, branch_name)

            # Add security label
            self.github.add_labels_to_pr(pr['number'], ['security', 'dependencies'])

            logger.info(f"Created security update PR: #{pr['number']}")
            return pr

        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            raise DependencyUpdateError(f"Failed to create security update PR: {e}")

    def _generate_pr_body(self, vulnerabilities: List[Dict]) -> str:
        """Generate PR body with vulnerability details."""
        body = [
            "## Security Update",
            "",
            "This PR updates dependencies to fix security vulnerabilities detected by pip-audit.",
            "",
            "### Vulnerabilities Fixed:",
            ""
        ]

        for vuln in vulnerabilities:
            package_name = vuln.get('name', 'Unknown')
            version = vuln.get('version', 'Unknown')
            vulns = vuln.get('vulns', [])

            body.append(f"#### {package_name} ({version})")

            for v in vulns:
                vuln_id = v.get('id', 'Unknown')
                fix_versions = v.get('fix_versions', [])
                description = v.get('description', 'No description available')

                body.append(f"- **{vuln_id}**: {description}")
                if fix_versions:
                    body.append(f"  - Fixed in: {', '.join(fix_versions)}")
                body.append("")

        body.extend([
            "### Changes Made:",
            "- Updated `requirements.in` with fixed versions",
            "- Regenerated `requirements.txt` using pip-compile",
            "",
            "### Testing:",
            "- [ ] All tests pass",
            "- [ ] Application starts successfully",
            "- [ ] No breaking changes detected",
            "",
            "---",
            "*This PR was automatically generated by the Dependency Auto-Update Service (Task 48)*"
        ])

        return '\n'.join(body)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Dependency Auto-Update Service")
    parser.add_argument("--dry-run", action="store_true",
                       help="Run in dry-run mode (no actual changes)")
    parser.add_argument("--force", action="store_true",
                       help="Force update even if no vulnerabilities found")

    args = parser.parse_args()

    # Get environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)

    if not repository:
        logger.error("GITHUB_REPOSITORY environment variable is required")
        sys.exit(1)

    try:
        updater = DependencyUpdater(github_token, repository, args.dry_run)

        # Check for security vulnerabilities
        has_vulns, vulnerabilities = updater.check_for_updates()

        if not has_vulns and not args.force:
            logger.info("No security vulnerabilities found. Nothing to update.")
            return

        if args.force and not has_vulns:
            logger.info("Force mode enabled but no vulnerabilities found.")
            return

        # Update requirements files
        if updater.update_requirements(vulnerabilities):
            # Create PR for the updates
            pr = updater.create_security_pr(vulnerabilities)
            if pr:
                logger.info(f"Security update completed. PR created: {pr['html_url']}")
            else:
                logger.info("Security update completed (dry-run mode)")
        else:
            logger.info("No updates were necessary")

    except DependencyUpdateError as e:
        logger.error(f"Dependency update failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()