""".github/workflows/release.yml: a version tag on main publishes both packages to PyPI."""

import re
import tomllib

import yaml
from ops_builders import REPO

WORKFLOW = REPO / ".github" / "workflows" / "release.yml"
VERSION_FILES = ("apifacts/__init__.py", "plugins/pytest/apifacts_pytest/__init__.py")


def load() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # YAML 1.1 reads the key `on` as boolean True
    return doc


JOBS = {"apifacts": ("pypi", ""), "apifacts-pytest": ("pypi-pytest", " plugins/pytest")}
PINNED = ("actions/checkout", "astral-sh/setup-uv")


def runs(job: str) -> list[str]:
    return [step["run"] for step in load()["jobs"][job]["steps"] if "run" in step]


def test_runs_only_on_a_version_tag():
    assert load()["on"] == {"push": {"tags": ["v[0-9]+.[0-9]+.[0-9]+"]}}


def test_releases_never_overlap_or_cancel():
    assert load()["concurrency"] == {"group": "release", "cancel-in-progress": False}


def test_one_job_per_package_each_in_its_own_pypi_environment_no_token():
    doc = load()
    assert doc["permissions"] == {}
    assert list(doc["jobs"]) == list(JOBS)  # PyPI binds one pending publisher per environment
    for job, (environment, _) in JOBS.items():
        spec = doc["jobs"][job]
        assert spec["permissions"] == {"contents": "read", "id-token": "write"}
        assert spec["environment"]["name"] == environment
        assert spec["timeout-minutes"] <= 5
    assert doc["jobs"]["apifacts-pytest"]["needs"] == "apifacts"
    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8")


def test_each_job_two_sha_pinned_actions_then_build_check_publish():
    doc = load()
    for job, (_, source) in JOBS.items():
        uses = [step["uses"] for step in doc["jobs"][job]["steps"] if "uses" in step]
        assert [u.split("@")[0] for u in uses] == list(PINNED)
        assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", u) for u in uses)  # a moved tag cannot run
        script = runs(job)
        build = script.index(f"uv build --no-sources --out-dir dist{source}")
        check = script.index("uvx twine check --strict dist/*")
        publish = script.index("uv publish --trusted-publishing always dist/*")
        assert build < check < publish == len(script) - 1
    pins = {step["uses"] for job in JOBS for step in doc["jobs"][job]["steps"] if "uses" in step}
    assert len(pins) == 2  # both jobs run the same two commits


def test_guard_runs_first_in_the_core_job_and_checks_main_and_both_versions():
    guard = runs("apifacts")[0]
    assert "git merge-base --is-ancestor HEAD origin/main" in guard
    for path in VERSION_FILES:
        assert path in guard
    assert "${GITHUB_REF_NAME#v}" in guard
    assert load()["jobs"]["apifacts"]["steps"][0]["with"] == {"fetch-depth": 0}


def versions() -> list[str]:
    found = []
    for rel in VERSION_FILES:
        text = (REPO / rel).read_text(encoding="utf-8")
        found.append(re.search(r'^__version__ = "([^"]+)"$', text, re.M).group(1))
    return found


def test_both_packages_carry_the_same_release_version():
    core, plugin = versions()
    assert core == plugin
    assert re.fullmatch(r"\d+\.\d+\.\d+", core)


def test_one_console_script_no_transition_alias():
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"] == {"apifacts": "apifacts.cli:app"}


def test_wheel_ships_the_offline_snapshot_and_the_sdist_can_build_it():
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    build = pyproject["tool"]["hatch"]["build"]["targets"]
    force = build["wheel"]["force-include"]
    assert force["services"] == "apifacts/client/snapshot/services"
    assert force["facts"] == "apifacts/client/snapshot/facts"
    assert {"apifacts", "schema", "services", "facts"} <= set(build["sdist"]["only-include"])
    assert not {"pages", "probes", "docs", "tests"} & set(build["sdist"]["only-include"])
    assert "LICENSE-DATA" in pyproject["project"]["license-files"]
