"""`auth: invalid` (decision Edouard 31.10.2026): the runner sends the fixed fake constant in the
service's scheme, with no key file, in prod as in sandbox; a probe still never writes credentials.
"""

import base64
import json

import pytest
from probe_builders import FAKE_KEY, Repo, make_service
from pydantic import ValidationError
from werkzeug import Request, Response

from apifacts.probe.http import INVALID_KEY, Credentials, Refused, invalid_credentials
from apifacts.probe.runner import TickOptions, run_tick
from apifacts.schema.models import Service
from apifacts.schema.validate import validate_paths

BASIC = base64.b64encode(f"{INVALID_KEY}:{INVALID_KEY}".encode()).decode()
SCHEMES = [
    ({"kind": "bearer"}, ("header", "Authorization", f"Bearer {INVALID_KEY}")),
    ({"kind": "basic"}, ("header", "Authorization", f"Basic {BASIC}")),
    ({"kind": "header", "header_name": "x-api-key"}, ("header", "x-api-key", INVALID_KEY)),
    ({"kind": "query", "param_name": "key"}, ("query", "key", INVALID_KEY)),
]


def test_the_constant_is_obviously_fake_and_not_key_shaped():
    assert INVALID_KEY == "apifacts-invalid-key"
    assert not INVALID_KEY.startswith(("sk", "pk", "rk", "re_", "ghp_", "xox", "lin_", "AC"))


@pytest.mark.parametrize(("auth", "expect"), SCHEMES)
def test_scheme_only_service_carries_the_constant(auth, expect):
    service = make_service(auth=auth)
    assert not service.auth.keyed
    where, name, value = expect
    credentials = invalid_credentials(service)
    assert (credentials.headers if where == "header" else credentials.query) == {name: value}


def test_path_prefix_scheme_puts_the_constant_in_the_path():
    service = make_service(auth={"kind": "path_prefix", "path_prefix": "/bot{key}"})
    assert invalid_credentials(service) == Credentials({}, {}, f"/bot{INVALID_KEY}")


def test_keyed_service_also_gets_the_constant_never_its_key():
    service = make_service()  # bearer, key_name acme-test
    assert invalid_credentials(service).headers == {"Authorization": f"Bearer {INVALID_KEY}"}


def test_no_scheme_is_refused():
    with pytest.raises(Refused) as exc:
        invalid_credentials(make_service(auth={"kind": "none"}))
    assert exc.value.code == "no_auth_scheme"


@pytest.mark.parametrize("auth", [
    {"kind": "bearer", "key_name": "acme-test"},  # key_name without env
    {"kind": "bearer", "env": "prod"},  # env without key_name
    {"kind": "google_service_account", "scopes": ["https://www.googleapis.com/auth/datastore"]},
])
def test_scheme_only_rules(auth):
    with pytest.raises(ValidationError):
        make_service(auth=auth)


def tick(repo: Repo, httpserver):
    return run_tick(repo.root, repo.state, TickOptions(run_all=True, vantage="test"),
                    keys_dir=repo.keys, base_urls={"acme": httpserver.url_for("")},
                    sleep=lambda _s: None, environ={})


def outputs(repo: Repo) -> bytes:
    files = [*repo.state.rglob("*"), *(repo.root / "facts").rglob("*")]
    return b"\n".join(p.read_bytes() for p in files if p.is_file())


@pytest.mark.parametrize("env", ["prod", "sandbox"])
def test_keyless_tick_sends_the_constant_and_records_no_credential(repo, httpserver, env):
    repo.service(auth={"kind": "bearer"})  # no key_name, no key file
    repo.probe(env=env, steps=[
        {"do": "http", "method": "GET", "path": "/v1/items", "auth": "invalid"},
        {"do": "http", "method": "GET", "path": "/v1/items"},  # auth: service → nothing
    ], **{"assert": [{"step": 1, "status": 401}, {"step": 2, "status": 401}]})
    repo.fact(env=env)
    seen: list[Request] = []

    def handler(request: Request) -> Response:
        seen.append(request)
        body = {"error": {"code": "invalid_api_key", "message": "bad key"}}
        return Response(json.dumps(body), 401, {"WWW-Authenticate": "Bearer"},
                        content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(handler)
    report = tick(repo, httpserver)
    assert [line.outcome for line in report.lines] == ["pass"]
    assert seen[0].headers["Authorization"] == f"Bearer {INVALID_KEY}"
    assert "Authorization" not in seen[1].headers
    for step in repo.results()[0]["steps"]:
        assert "authorization" not in {k.lower() for k in step["headers"]}
    assert b"Bearer apifacts" not in outputs(repo)


def test_keyed_service_invalid_step_runs_without_its_key_file(repo, httpserver):
    repo.service()  # bearer with key_name acme-test, no key file written
    repo.probe(steps=[{"do": "http", "method": "GET", "path": "/v1/items", "auth": "invalid"}],
               **{"assert": [{"step": 1, "status": 401}]})
    repo.fact()
    seen: list[Request] = []

    def handler(request: Request) -> Response:
        seen.append(request)
        return Response("{}", 401, content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(handler)
    report = tick(repo, httpserver)
    assert [line.outcome for line in report.lines] == ["pass"]
    assert seen[0].headers["Authorization"] == f"Bearer {INVALID_KEY}"
    assert FAKE_KEY not in seen[0].headers["Authorization"]


SERVICE = """\
key: acme
name: Acme
hosts: [api.acme.example]
surfaces:
  http: {base_url: "https://api.acme.example", templates: [{method: GET, path: /v1/items}]}
dimensions: {env: {prod: "https://api.acme.example"}, account_state: [anonymous]}
auth: %s
tos: {automated_access: allowed, publish_measurements: allowed, source: "https://acme.example/tos"}
"""
PROBE = """\
id: af:acme:probe:invalid-key
service: acme
env: prod
steps:
  - {do: http, method: GET, path: /v1/items, auth: invalid%s}
assert:
  - {step: 1, status: 401}
"""


def _codes(tmp_path, auth: str, extra: str = "") -> set[str]:
    (tmp_path / "services").mkdir()
    (tmp_path / "probes" / "acme").mkdir(parents=True)
    (tmp_path / "services" / "acme.yaml").write_text(SERVICE % auth)
    (tmp_path / "probes" / "acme" / "invalid-key.yaml").write_text(PROBE % extra)
    report = validate_paths([tmp_path], root=tmp_path)
    return {p.code for p in report.problems}


def test_validator_allows_invalid_in_prod_on_a_scheme_only_service(tmp_path):
    assert _codes(tmp_path, "{kind: bearer}") == set()


def test_validator_allows_invalid_in_prod_with_a_sandbox_key(tmp_path):
    # The constant reaches no environment, so the key's env does not bind the step.
    assert _codes(tmp_path, "{kind: bearer, key_name: acme-test, env: sandbox}") == set()


def test_validator_needs_a_scheme(tmp_path):
    assert _codes(tmp_path, "{kind: none}") == {"no_auth_scheme"}


def test_validator_still_forbids_a_handwritten_authorization(tmp_path):
    codes = _codes(tmp_path, "{kind: bearer}", ", headers: {Authorization: Bearer x}")
    assert codes == {"forbidden_header"}


def test_service_model_accepts_scheme_only():
    doc = {"key": "acme", "name": "Acme", "hosts": ["api.acme.example"],
           "surfaces": {"http": {"base_url": "https://api.acme.example",
                                 "templates": [{"method": "GET", "path": "/v1/items"}]}},
           "dimensions": {"env": {"prod": "https://api.acme.example"}},
           "auth": {"kind": "header", "header_name": "x-api-key"},
           "tos": {"automated_access": "allowed", "publish_measurements": "allowed",
                   "source": "https://acme.example/tos"}}
    assert Service.model_validate(doc).auth.keyed is False
