# Dependency Management & Security Updates

This document describes the dependency management strategy and automated security update system for Instant Scribe.

## Overview

Instant Scribe uses a comprehensive dependency management system that includes:

1. **Pinned Dependencies** - All direct dependencies are pinned to specific versions in `requirements.in`
2. **Automated Security Scanning** - Weekly scans for security vulnerabilities using `pip-audit`
3. **Automated Updates** - Automatic PR creation for security patches
4. **CI/CD Integration** - Continuous validation of dependency health

## Dependency Files

### requirements.in

The `requirements.in` file contains all direct dependencies with minimum compatible versions:

- **PyTorch Stack**: CUDA-enabled PyTorch, torchaudio, torchvision for GPU acceleration
- **Audio Processing**: PyAudio, webrtcvad-wheels for audio capture and voice activity detection
- **NeMo Toolkit**: NVIDIA NeMo for ASR (Automatic Speech Recognition)
- **UI Components**: pystray, windows-toasts for system tray and notifications
- **Development Tools**: pytest, black, isort, flake8, mypy for code quality
- **Security Tools**: pip-audit for vulnerability scanning

### requirements.txt

Generated from `requirements.in` using `pip-compile`, this file contains all dependencies (direct and transitive) with exact version pins for reproducible builds.

## Automated Security Updates (Task 48)

### Weekly Security Scanning

Every Monday at 9:00 AM UTC, the Dependency Auto-Update Service runs:

1. **Vulnerability Scan**: Uses `pip-audit` to scan `requirements.txt` for known security vulnerabilities
2. **Version Analysis**: Identifies available security patches for vulnerable packages
3. **Update Generation**: Updates `requirements.in` with fixed versions
4. **Recompilation**: Regenerates `requirements.txt` using `pip-compile`
5. **PR Creation**: Opens automated pull requests with security updates

### Manual Execution

You can manually run the dependency update service:

```bash
# Dry run (no changes)
python scripts/dependency_auto_update.py --dry-run

# Force update even if no vulnerabilities found
python scripts/dependency_auto_update.py --force

# Normal execution
python scripts/dependency_auto_update.py
```

### Environment Variables

The service requires these environment variables:

- `GITHUB_TOKEN`: GitHub personal access token with repo permissions
- `GITHUB_REPOSITORY`: Repository in format `owner/repo`

### Security PR Format

Automated security PRs include:

- **Title**: "Security Update: Fix N vulnerabilities"
- **Labels**: `security`, `dependencies`
- **Body**: Detailed vulnerability information including:
  - CVE/PYSEC identifiers
  - Affected packages and versions
  - Fix versions
  - Vulnerability descriptions

## Manual Dependency Updates

### Adding New Dependencies

1. Add the dependency to `requirements.in` with minimum version:
   ```
   new-package>=1.0.0
   ```

2. Regenerate the lockfile:
   ```bash
   pip-compile requirements.in
   ```

3. Install and test:
   ```bash
   pip install -r requirements.txt
   ```

### Updating Existing Dependencies

1. Update the version constraint in `requirements.in`
2. Regenerate `requirements.txt`
3. Test thoroughly before committing

### Version Pinning Strategy

- **Exact pins** (`==`) for critical dependencies like PyTorch
- **Minimum versions** (`>=`) for most libraries to allow security updates
- **Version ranges** (`>=X,<Y`) when compatibility is a concern

## Security Considerations

### Vulnerability Sources

The system monitors vulnerabilities from:

- **PyPI Advisory Database**: Official Python package vulnerability database
- **OSV Database**: Open Source Vulnerabilities database
- **NVD/CVE**: National Vulnerability Database

### Update Policy

- **Security patches**: Applied automatically via PR
- **Minor updates**: Reviewed manually
- **Major updates**: Require thorough testing and approval

### CI/CD Integration

All dependency changes are validated through:

1. **Syntax checks**: Code compilation and linting
2. **Unit tests**: Full test suite execution
3. **Integration tests**: End-to-end functionality validation
4. **Security scans**: Vulnerability assessment
5. **Performance tests**: RTF benchmarks

## Troubleshooting

### Common Issues

1. **pip-audit not found**: The service automatically installs pip-audit if missing
2. **pip-compile failures**: Usually due to conflicting version constraints
3. **GitHub API rate limits**: Use authenticated requests with proper tokens

### Manual Intervention

If automated updates fail:

1. Check the workflow logs in GitHub Actions
2. Review the error messages in the created issue
3. Manually run the update script with `--dry-run` to diagnose
4. Update dependencies manually if needed

### Emergency Security Updates

For critical vulnerabilities:

1. Manually update `requirements.in` immediately
2. Run `pip-compile` to regenerate lockfile
3. Test and deploy as hotfix
4. Document the emergency update in commit message

## Monitoring

### Automated Notifications

- **Success**: No notification (silent success)
- **Failures**: Automatic issue creation with error details
- **Critical vulnerabilities**: Immediate PR creation

### Manual Monitoring

Check these regularly:

- GitHub Security tab for vulnerability alerts
- Dependabot alerts (if enabled)
- Weekly dependency update PR status

## Best Practices

1. **Review all PRs**: Even automated security updates should be reviewed
2. **Test thoroughly**: Run full test suite before merging
3. **Monitor logs**: Check application logs after dependency updates
4. **Keep current**: Don't let dependencies get too stale
5. **Document changes**: Note any breaking changes or required configuration updates

## Related Documentation

- [Task 27: Dependency Management & Automated Pinning](../progress/DEV_TASKS.md#27)
- [Task 48: Dependency Auto-Update Service](../progress/DEV_TASKS.md#48)
- [CI/CD Pipeline Documentation](.github/workflows/ci.yml)
- [Security Policy](PRIVACY.md)