import os
import yaml

WORKFLOW_PATH = os.path.join('.github', 'workflows', 'ci.yml')


def _load_workflow() -> dict:
    with open(WORKFLOW_PATH, 'r', encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def test_benchmark_job_present():
    """Ensure the consolidated CI pipeline includes a benchmark job chained after tests."""
    workflow = _load_workflow()
    jobs = workflow.get('jobs', {})
    assert 'benchmark' in jobs, "Missing 'benchmark' job in CI workflow"
    assert jobs['benchmark'].get('needs') == 'test', (
        "Benchmark job must depend on the 'test' job"
    )


def test_build_depends_on_benchmark():
    """Confirm build waits for benchmark completion."""
    workflow = _load_workflow()
    needs = workflow['jobs']['build'].get('needs', [])
    if isinstance(needs, str):
        needs = [needs]
    assert 'benchmark' in needs, "Build job must depend on benchmark job"


def test_release_notifications():
    """Release job should optionally notify Slack or Teams via webhook env vars."""
    workflow = _load_workflow()
    steps = workflow['jobs']['release']['steps']
    concatenated = '\n'.join(
        '\n'.join(str(v) for v in step.values()) for step in steps if isinstance(step, dict)
    )
    assert (
        'SLACK_WEBHOOK_URL' in concatenated or 'TEAMS_WEBHOOK_URL' in concatenated
    ), "Release job missing Slack/Teams notification step" 