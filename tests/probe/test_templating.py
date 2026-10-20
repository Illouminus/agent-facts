"""Templating: only `{{run_uuid}}`, `{{now_rfc3339}}` and `{{step[N].json.<path>}}` (spec 04)."""

import pytest

from agentfacts.probe.templating import (
    NOT_JSON,
    RunContext,
    TemplateError,
    lookup,
    render,
    render_path,
)


def ctx(step=2, responses=None):
    return RunContext(
        run_uuid="5f0c2b1e-0000-4000-8000-000000000001",
        now_rfc3339="2026-10-20T10:15:00Z",
        responses=responses if responses is not None else {1: {"id": "obj_1", "count": 3}},
        current_step=step,
    )


def test_run_uuid_and_now():
    assert render("{{run_uuid}}", ctx()) == "5f0c2b1e-0000-4000-8000-000000000001"
    assert render("at {{ now_rfc3339 }}", ctx()) == "at 2026-10-20T10:15:00Z"


def test_new_context_has_one_uuid_and_rfc3339_now():
    c = RunContext.start(current_step=1)
    assert len(c.run_uuid) == 36
    assert c.now_rfc3339.endswith("Z") and len(c.now_rfc3339) == 20


def test_step_json_reference():
    responses = {1: {"data": [{"id": "x1"}, {"id": "x2"}]}}
    assert render("{{step[1].json.data[1].id}}", ctx(responses=responses)) == "x2"


def test_non_string_values_render_as_json_text():
    responses = {1: {"ok": True, "n": 3, "none": None}}
    c = ctx(responses=responses)
    out = render("{{step[1].json.ok}}/{{step[1].json.n}}/{{step[1].json.none}}", c)
    assert out == "true/3/null"


def test_whole_placeholder_keeps_type_in_json_bodies():
    body = {"n": "{{step[1].json.count}}", "label": "id-{{step[1].json.id}}", "list": [1, "x"]}
    out = render(body, ctx(), keep_type=True)
    assert out == {"n": 3, "label": "id-obj_1", "list": [1, "x"]}


def test_dict_keys_are_not_rendered():
    assert render({"{{run_uuid}}": "v"}, ctx()) == {"{{run_uuid}}": "v"}


def test_non_strings_pass_through():
    assert render(5, ctx()) == 5 and render(True, ctx()) is True


@pytest.mark.parametrize(
    "template",
    [
        "{{env.HOME}}",
        "{{ run_uuid() }}",
        "{{step[2].json.id}}",  # the current step has not run
        "{{step[3].json.id}}",
        "{{step[0].json.id}}",
        "{{step[1].json.missing}}",
        "{{step[1].json.id[0]}}",
        "{{step[1].headers.x}}",
        "{{run_uuid}",
        "{run_uuid}}",
        "{{ a {b} }}",
        "x {{run_uuid}} {{",
    ],
)
def test_rejected_templates(template):
    with pytest.raises(TemplateError):
        render(template, ctx())


def test_reference_to_a_non_json_step():
    with pytest.raises(TemplateError, match="not JSON"):
        render("{{step[1].json.id}}", ctx(responses={1: NOT_JSON}))


def test_path_placeholders_are_percent_encoded_per_segment():
    c = ctx(responses={1: {"id": "a/b c"}})
    assert render_path("/v1/items/{{step[1].json.id}}", c) == "/v1/items/a%2Fb%20c"
    assert render_path("/v1/items/{{run_uuid}}", c) == "/v1/items/" + c.run_uuid


@pytest.mark.parametrize("value", ["", ".", ".."])
def test_path_placeholder_may_not_render_a_dot_or_empty_segment(value):
    with pytest.raises(TemplateError):
        render_path("/v1/items/{{step[1].json.id}}", ctx(responses={1: {"id": value}}))


def test_dots_inside_a_value_are_fine_in_paths():
    assert render_path("/v1/{{step[1].json.id}}", ctx(responses={1: {"id": "a..b"}})) == "/v1/a..b"


def test_lookup():
    doc = {"a": [{"b": 1}], "c-d": {"e": None}}
    assert lookup(doc, ".a[0].b") == 1
    assert lookup(doc, ".c-d.e") is None
    assert lookup(doc, "") is doc
    with pytest.raises(LookupError):
        lookup(doc, ".a[1]")
    with pytest.raises(LookupError):
        lookup(doc, ".x")
    with pytest.raises(LookupError):
        lookup([1], ".a")
    with pytest.raises(ValueError):
        lookup(doc, "a")
    with pytest.raises(ValueError):
        lookup(doc, "['a']")
