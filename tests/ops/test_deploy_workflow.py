""".github/workflows/deploy.yml: short, after green CI on main only, one ssh with the sha."""

import yaml
from ops_builders import REPO

WORKFLOW = REPO / ".github" / "workflows" / "deploy.yml"


def load() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # YAML 1.1 reads the key `on` as boolean True
    return doc


def test_runs_after_ci_on_main_or_by_hand():
    on = load()["on"]
    assert on["workflow_run"] == {"workflows": ["CI"], "types": ["completed"], "branches": ["main"]}
    assert "workflow_dispatch" in on
    assert "push" not in on and "pull_request" not in on  # CI is not run a second time


def test_job_only_on_a_successful_push_run_and_short():
    job = load()["jobs"]["deploy"]
    assert "github.event.workflow_run.conclusion == 'success'" in job["if"]
    assert "github.event.workflow_run.event == 'push'" in job["if"]
    assert job["timeout-minutes"] <= 3


def test_no_permissions_no_checkout_one_pinned_ssh():
    doc = load()
    assert doc["permissions"] == {}
    steps = doc["jobs"]["deploy"]["steps"]
    assert not any("uses" in step for step in steps)  # no checkout, no third-party action
    script = "\n".join(step.get("run", "") for step in steps)
    assert script.count("ssh ") == 1
    for option in ("-F /dev/null", "IdentitiesOnly=yes", "StrictHostKeyChecking=yes",
                   "BatchMode=yes"):
        assert option in script
    env = steps[-1]["env"]
    assert "github.event.workflow_run.head_sha" in env["SHA"]
    assert env["SSH_KEY"] == "${{ secrets.VPS_SSH_KEY }}"


def test_deploys_never_overlap():
    assert load()["concurrency"] == {"group": "deploy", "cancel-in-progress": False}
