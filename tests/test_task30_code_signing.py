import os
import yaml

WORKFLOW_PATH = os.path.join('.github', 'workflows', 'ci.yml')
SIGN_SCRIPT_PATH = os.path.join('scripts', 'verify_signature.ps1')


def test_verify_signature_script_exists():
    """The PowerShell script required by Task 30 must exist."""
    assert os.path.isfile(SIGN_SCRIPT_PATH), f"Missing script: {SIGN_SCRIPT_PATH}"


def test_ci_includes_signtool_step():
    """The CI pipeline build job must contain a signtool signing step."""
    assert os.path.isfile(WORKFLOW_PATH), "CI workflow file is missing."
    with open(WORKFLOW_PATH, 'r', encoding='utf-8') as fh:
        workflow = yaml.safe_load(fh)
    build_steps = (
        workflow
        .get('jobs', {})
        .get('build', {})
        .get('steps', [])
    )
    # Flatten text from each step to search for signtool
    concatenated = '\n'.join(
        '\n'.join(str(v) for v in step.values()) for step in build_steps if isinstance(step, dict)
    ).lower()
    assert 'signtool sign' in concatenated, "signtool signing command not found in build job steps"


def test_ci_includes_signature_verification_step():
    """CI must verify the signature using the verify_signature.ps1 script."""
    with open(WORKFLOW_PATH, 'r', encoding='utf-8') as fh:
        workflow = yaml.safe_load(fh)
    build_steps = (
        workflow
        .get('jobs', {})
        .get('build', {})
        .get('steps', [])
    )
    found = any(
        isinstance(step, dict) and 'verify_signature.ps1' in '\n'.join(str(v) for v in step.values())
        for step in build_steps
    )
    assert found, "verify_signature.ps1 invocation missing from CI build job" 