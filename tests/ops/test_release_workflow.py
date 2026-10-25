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


def runs() -> list[str]:
    return [step["run"] for step in load()["jobs"]["publish"]["steps"] if "run" in step]


def test_runs_only_on_a_version_tag():
    assert load()["on"] == {"push": {"tags": ["v[0-9]+.[0-9]+.[0-9]+"]}}


def test_releases_never_overlap_or_cancel():
    assert load()["concurrency"] == {"group": "release", "cancel-in-progress": False}


def test_oidc_in_the_pypi_environment_and_no_token():
    doc = load()
    assert doc["permissions"] == {}
    job = doc["jobs"]["publish"]
    assert job["permissions"] == {"contents": "read", "id-token": "write"}
    assert job["environment"]["name"] == "pypi"
    assert job["timeout-minutes"] <= 5
    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8")


def test_two_sha_pinned_actions_then_build_check_publish_each_package():
    steps = load()["jobs"]["publish"]["steps"]
    uses = [step["uses"] for step in steps if "uses" in step]
    assert [u.split("@")[0] for u in uses] == ["actions/checkout", "astral-sh/setup-uv"]
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", u) for u in uses)  # a moved tag cannot run here
    script = runs()
    builds = [r for r in script if r.startswith("uv build --no-sources --out-dir dist")]
    assert len(builds) == 2 and builds[1].endswith(" plugins/pytest")
    check = next(i for i, r in enumerate(script) if r == "uvx twine check --strict dist/*")
    publish = [(i, r) for i, r in enumerate(script) if r.startswith("uv publish ")]
    assert [r for _, r in publish] == [
        "uv publish --trusted-publishing always dist/apifacts-*",
        "uv publish --trusted-publishing always dist/apifacts_pytest-*",
    ]
    assert check < publish[0][0]


def test_guard_runs_first_and_checks_main_and_both_versions():
    guard = runs()[0]
    assert "git merge-base --is-ancestor HEAD origin/main" in guard
    for path in VERSION_FILES:
        assert path in guard
    assert '${GITHUB_REF_NAME#v}' in guard


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
