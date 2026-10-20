"""Prod JSON-RPC reads: a prod probe may POST one JSON-RPC 2.0 request to the endpoint the service
declares in `surfaces.http.jsonrpc`, with one of its read_methods (Solana RPC has no GET form);
everything else a prod POST could carry stays refused (`prod_probe_not_readonly`)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentfacts.schema.models import Probe, http_step_violations
from agentfacts.schema.registry import JsonRpcRead
from agentfacts.schema.validate import validate_paths

SERVICE = """\
key: rpcco
name: RPC Co
hosts: [rpc.example.com]
surfaces:
  http:
    base_url: https://rpc.example.com
    templates:
      - {method: POST, path: /}
      - {method: GET, path: /health}
    jsonrpc: {path: /, read_methods: [getHealth, getSlot]}
dimensions:
  env: {prod: https://rpc.example.com}
auth: {kind: none}
tos:
  automated_access: allowed
  publish_measurements: allowed
  source: https://rpc.example.com/terms
"""
PROBE = """\
id: af:rpcco:probe:health
service: rpcco
env: prod
steps:
  - {do: http, method: POST, path: /, json: %s}
assert:
  - {step: 1, status: 200}
"""
READ = '{jsonrpc: "2.0", id: 1, method: getHealth}'


def _codes(tmp_path: Path, service: str, body: str, extra: str = "") -> set[str]:
    (tmp_path / "s.yaml").write_text(service, encoding="utf-8")
    probe = PROBE % body
    if extra:
        probe = probe.replace("json: ", extra + "json: ", 1)
    (tmp_path / "p.yaml").write_text(probe, encoding="utf-8")
    report = validate_paths([tmp_path / "s.yaml", tmp_path / "p.yaml"], root=tmp_path / "none")
    return {p.code for p in report.problems}


def test_listed_jsonrpc_read_passes(tmp_path):
    assert _codes(tmp_path, SERVICE, READ) == set()


@pytest.mark.parametrize(
    ("body", "extra"),
    [
        ('{jsonrpc: "2.0", id: 1, method: sendTransaction}', ""),  # not on the list
        ('{jsonrpc: "2.0", id: 1, method: "{{run_uuid}}"}', ""),  # templated method
        ('[{jsonrpc: "2.0", id: 1, method: getHealth}]', ""),  # batch
        ("{id: 1, method: getHealth}", ""),  # not JSON-RPC 2.0
        ('{jsonrpc: "2.0", id: 1}', ""),  # no method
        (READ, "form: {a: b}, "),  # form beside the body
        (READ, "headers: {X-HTTP-Method-Override: PUT}, "),
        ('{jsonrpc: "2.0", id: 1, method: getHealth, Method: sendTransaction}', ""),  # extra key
        ('{jsonrpc: "2.0", id: 1, method: getHealth, data: x}', ""),
        ('{jsonrpc: "2.0", id: 1, method: getHealth, params: x}', ""),  # params not array/object
    ],
)
def test_anything_else_in_a_prod_post_is_refused(tmp_path, body, extra):
    assert _codes(tmp_path, SERVICE, body, extra) == {"prod_probe_not_readonly"}


def test_service_without_a_read_list_gets_no_prod_post(tmp_path):
    service = SERVICE.replace("    jsonrpc: {path: /, read_methods: [getHealth, getSlot]}\n", "")
    assert _codes(tmp_path, service, READ) == {"prod_probe_not_readonly"}


def test_listed_method_on_another_post_template_is_refused(tmp_path):
    service = SERVICE.replace(
        "      - {method: GET, path: /health}", "      - {method: POST, path: /admin}"
    )
    probe = PROBE.replace("path: /,", "path: /admin,") % READ
    (tmp_path / "s.yaml").write_text(service, encoding="utf-8")
    (tmp_path / "p.yaml").write_text(probe, encoding="utf-8")
    report = validate_paths([tmp_path / "s.yaml", tmp_path / "p.yaml"], root=tmp_path / "none")
    assert {p.code for p in report.problems} == {"prod_probe_not_readonly"}


def test_jsonrpc_endpoint_must_be_a_post_template(tmp_path):
    service = SERVICE.replace("jsonrpc: {path: /,", "jsonrpc: {path: /rpc,")
    (tmp_path / "s.yaml").write_text(service, encoding="utf-8")
    report = validate_paths([tmp_path / "s.yaml"], root=tmp_path / "none")
    assert {p.code for p in report.problems} == {"unregistered_template"}


def test_get_with_a_jsonrpc_body_is_still_refused(tmp_path):
    probe = PROBE.replace("method: POST, path: /,", "method: GET, path: /health,") % READ
    (tmp_path / "s.yaml").write_text(SERVICE, encoding="utf-8")
    (tmp_path / "p.yaml").write_text(probe, encoding="utf-8")
    report = validate_paths([tmp_path / "s.yaml", tmp_path / "p.yaml"], root=tmp_path / "none")
    assert {p.code for p in report.problems} == {"prod_probe_not_readonly"}


def test_sandbox_post_needs_no_list(tmp_path):
    service = SERVICE.replace(
        "  env: {prod: https://rpc.example.com}",
        "  env: {prod: https://rpc.example.com, sandbox: https://rpc.example.com}",
    )
    body = '{jsonrpc: "2.0", id: 1, method: sendTransaction}'
    probe = (PROBE % body).replace("env: prod", "env: sandbox")
    (tmp_path / "s.yaml").write_text(service, encoding="utf-8")
    (tmp_path / "p.yaml").write_text(probe, encoding="utf-8")
    report = validate_paths([tmp_path / "s.yaml", tmp_path / "p.yaml"], root=tmp_path / "none")
    assert report.ok, report.problems


def _probe(body):
    return {
        "id": "af:rpcco:probe:x",
        "service": "rpcco",
        "env": "prod",
        "steps": [{"do": "http", "method": "POST", "path": "/", "json": body}],
        "assert": [{"step": 1, "status": 200}],
    }


def test_model_checks_the_shape_without_the_service():
    # The model cannot see the service's list: shape only; validator and runner check the method.
    Probe.model_validate(_probe({"jsonrpc": "2.0", "id": 1, "method": "anything"}))
    with pytest.raises(ValidationError, match="prod_probe_not_readonly"):
        Probe.model_validate(_probe([{"jsonrpc": "2.0", "id": 1, "method": "getHealth"}]))
    with pytest.raises(ValidationError, match="prod_probe_not_readonly"):
        Probe.model_validate(_probe({"jsonrpc": "2.0", "method": "getHealth", "Method": "x"}))
    for bad in ({"id": True}, {"id": {"a": 1}}, {"params": "x"}):
        with pytest.raises(ValidationError, match="prod_probe_not_readonly"):
            Probe.model_validate(_probe({"jsonrpc": "2.0", "method": "getHealth", **bad}))


def test_violations_name_the_method():
    step = {"method": "POST", "path": "/", "json": {"jsonrpc": "2.0", "method": "sendTransaction"}}
    endpoint = JsonRpcRead("/", frozenset({"getHealth"}))
    [(field, code, message)] = http_step_violations(step, "prod", endpoint)
    assert (field, code) == ("json", "prod_probe_not_readonly")
    assert "sendTransaction" in message
