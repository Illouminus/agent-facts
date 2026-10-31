"""Tier 2b (spec 03 step 3): a service's auth facts answer the same error on any of its templates.

Against the real registry: the OpenAI auth facts are probed on `GET /v1/models` (prod probes may
only GET), agents fail on `POST /v1/chat/completions`.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apifacts.api.app import create_app

REPO = Path(__file__).parents[2]
CHAT = "https://api.openai.com/v1/chat/completions"
INVALID_KEY_BODY = (
    '{"error": {"message": "Incorrect API key provided: sk-proj-abc. You can find your API key at'
    ' https://platform.openai.com/account/api-keys.", "type": "invalid_request_error",'
    ' "param": null, "code": "invalid_api_key"}}'
)
MISSING_KEY_BODY = (
    '{"error": {"message": "Missing bearer authentication in header", "type":'
    ' "invalid_request_error", "param": null, "code": null}}'
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "observations.sqlite"
    with TestClient(create_app(repo=REPO, db_path=db), client=("203.0.113.9", 1)) as c:
        yield c


def check(client, status, body, method="POST", url=CHAT):
    r = client.post(
        "/v0/check",
        json={
            "target": {"method": method, "url": url},
            "error": {"status": status, "body_excerpt": body},
        },
    )
    assert r.status_code == 200
    return r.json()


def ids(body) -> set[str]:
    return {f["id"] for f in body["facts"]}


def test_invalid_key_on_chat_completions_borrows_the_auth_fact(client):
    body = check(client, 401, INVALID_KEY_BODY)
    assert body["matched_template"] == {"method": "POST", "path": "/v1/chat/completions"}
    assert "af:openai:invalid-api-key-401" in ids(body)
    assert {f["kind"] for f in body["facts"]} == {"auth_quirk"}
    assert body["unknown"]["reason"] is None


def test_missing_key_matches_by_message(client):
    body = check(client, 401, MISSING_KEY_BODY)
    assert "af:openai:missing-api-key-401" in ids(body)
    assert "af:openai:invalid-api-key-401" not in ids(body)


def test_status_alone_borrows_nothing(client):
    other = '{"error": {"message": "You exceeded your current quota", "type": "x", "code": "insufficient_quota"}}'
    body = check(client, 401, other)
    assert not any(f["kind"] == "auth_quirk" for f in body["facts"])
    assert body["unknown"]["reason"] == "no_fact_for_signal"


def test_same_code_other_status_borrows_nothing(client):
    body = check(client, 400, INVALID_KEY_BODY.replace("Incorrect API key provided", "Bad thing"))
    assert not any(f["kind"] == "auth_quirk" for f in body["facts"])


def test_own_template_still_answers_first(client):
    body = check(
        client, 401, INVALID_KEY_BODY, method="GET", url="https://api.openai.com/v1/models"
    )
    assert body["matched_template"] == {"method": "GET", "path": "/v1/models"}
    assert "af:openai:invalid-api-key-401" in ids(body)
