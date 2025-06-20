import os
import yaml

WORKFLOW_PATH = os.path.join('.github', 'workflows', 'ci.yml')


def test_ci_workflow_exists():
    """Ensure the primary CI/CD workflow file has been created."""
    assert os.path.isfile(WORKFLOW_PATH), f"Expected workflow file at {WORKFLOW_PATH}"


def _load_workflow() -> dict:
    with open(WORKFLOW_PATH, 'r', encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def test_ci_contains_required_jobs():
    workflow = _load_workflow()
    jobs = workflow.get('jobs', {})
    required = {'lint', 'test', 'build', 'release'}
    missing = required.difference(jobs)
    assert not missing, f"Missing expected job blocks in CI workflow: {', '.join(sorted(missing))}"


def test_release_job_condition():
    """The release job must only run for git tag refs (startsWith condition)."""
    workflow = _load_workflow()
    release_job = workflow['jobs']['release']
    condition = release_job.get('if', '')
    assert "startsWith(github.ref, 'refs/tags/')" in condition, "Release job does not guard on tag refs" 