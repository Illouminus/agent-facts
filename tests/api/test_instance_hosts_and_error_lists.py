"""D-090: check() matches a target on a service's `auth.instance_hosts` (an org's own domain, such
as `<org>.my.salesforce.com`) and reads errors that sit inside a list (`[{message, errorCode}]` at
Salesforce, `error.errors[0].reason` at Google) through the same paths as the probe runner."""

import json
import shutil
from pathlib import Path

import httpx
import pytest
from api_fixtures import write_repo
from fastapi.testclient import TestClient

from agentfacts.api.app import create_app
from agentfacts.api.facts_index import FactsIndex
from agentfacts.api.normalize import extract_signal, normalize
from agentfacts.probe.http import StepResponse
from agentfacts.probe.redact import Redactor
from agentfacts.probe.results import error_text
from agentfacts.schema.error_paths import CODE_PATHS, MESSAGE_PATHS

ROOT = Path(__file__).resolve().parents[2]
SALESFORCE_FIELDS = ("status", "errorCode", "message", "sforce-limit-info")
CALENDAR_FIELDS = ("status", "error.status", "error.message", "retry-after")
SALESFORCE_BODY = json.dumps(
    [{"message": "Session expired or invalid", "errorCode": "INVALID_SESSION_ID"}]
)
CALENDAR_BODY = json.dumps(
    {
        "error": {
            "code": 410,
            "message": "Sync token is no longer valid, a full sync is required.",
            "errors": [{"domain": "global", "reason": "fullSyncRequired", "message": "x"}],
        }
    }
)
ORG_QUERY = "https://acme.my.salesforce.com/services/data/v61.0/query"
LOOKALIKE_QUERY = "https://acme.my.salesforce.com.evil.io/services/data/v61.0/query"


@pytest.fixture
def repo(tmp_path) -> Path:
    root = write_repo(tmp_path / "repo")
    for key in ("salesforce", "google-calendar"):
        shutil.copy(ROOT / "services" / f"{key}.yaml", root / "services" / f"{key}.yaml")
    return root


@pytest.fixture
def client(repo, tmp_path):
    app = create_app(repo=repo, db_path=tmp_path / "observations.sqlite")
    with TestClient(app, client=("203.0.113.7", 50000)) as c:
        yield c


# ── step 1: host → service ─────────────────────────────────────────────────────────────────────


def test_org_host_resolves_to_salesforce(repo):
    index = FactsIndex.load(repo)
    assert [s.key for s in index.services_for_host("acme.my.salesforce.com")] == ["salesforce"]
    assert [s.key for s in index.services_for_host("login.salesforce.com")] == ["salesforce"]


@pytest.mark.parametrize(
    "host",
    [
        "my.salesforce.com.evil.io",
        "notmy.salesforce.com",
        "salesforce.com",
        "eu.login.salesforce.com",
    ],
)
def test_lookalike_hosts_stay_unregistered(repo, host):
    assert FactsIndex.load(repo).services_for_host(host) == []


def test_check_on_an_org_host_is_matched_and_stored(client):
    r = client.post(
        "/v0/check",
        json={
            "target": {"method": "GET", "url": ORG_QUERY},
            "error": {"status": 401, "body_excerpt": SALESFORCE_BODY},
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert body["service"] == "salesforce"
    assert body["matched_template"] == {"method": "GET", "path": "/services/data/{version}/query"}
    assert body["unknown"]["stored_as_observation"] is True


def test_check_on_a_lookalike_host_is_unregistered(client):
    r = client.post(
        "/v0/check",
        json={
            "target": {"method": "GET", "url": LOOKALIKE_QUERY},
            "error": {"status": 401, "body_excerpt": SALESFORCE_BODY},
        },
    )
    assert r.json()["unknown"] == {"reason": "unregistered_target", "stored_as_observation": False}


# ── step 2: errors inside a list ───────────────────────────────────────────────────────────────


def test_salesforce_array_body_gives_message_and_code():
    s = extract_signal(401, SALESFORCE_BODY, SALESFORCE_FIELDS)
    assert s.error_code == "INVALID_SESSION_ID"
    assert s.raw_string == "Session expired or invalid"
    assert s.normalized == "session expired or invalid"


def test_google_reason_inside_errors_list_is_the_code():
    s = extract_signal(410, CALENDAR_BODY, CALENDAR_FIELDS)
    assert s.error_code == "fullSyncRequired"
    assert s.raw_string == "Sync token is no longer valid, a full sync is required."


def test_whitelisted_field_wins_over_the_list_path():
    body = json.dumps({"error": {"status": "FAILED_PRECONDITION", "message": "m",
                                 "errors": [{"reason": "fullSyncRequired"}]}})
    assert extract_signal(410, body, CALENDAR_FIELDS).error_code == "FAILED_PRECONDITION"


def test_top_level_message_off_the_whitelist_still_yields_nothing():
    s = extract_signal(400, '{"message": "top"}', ("error.message",))
    assert s.raw_string is None  # Q4 unchanged: only list-shaped bodies get the shared paths


def test_secret_shaped_list_code_is_not_a_code():
    body = json.dumps([{"message": "m", "errorCode": "sk_live_" + "a1B2c3D4e5F6g7H8"}])
    assert extract_signal(400, body, SALESFORCE_FIELDS).error_code is None


@pytest.mark.parametrize(
    "body, fields", [(SALESFORCE_BODY, SALESFORCE_FIELDS), (CALENDAR_BODY, CALENDAR_FIELDS)]
)
def test_check_and_runner_read_the_same_string(body, fields):
    response = StepResponse(400, httpx.Headers(), body.encode(), json.loads(body), 1)
    runner = error_text(response, Redactor(()))
    assert normalize(runner) == extract_signal(400, body, fields).normalized


def test_list_paths_come_from_the_runners_list():
    assert "[0].message" in MESSAGE_PATHS
    assert set(CODE_PATHS) == {".error.errors[0].reason", "[0].errorCode"}
