import copy

from apifacts.client.render import TITLE, render_section, title_line
from apifacts.client.request import make_signal

CLAIM = (
    "Reusing an Idempotency-Key with a different request body returns HTTP 400 idempotency_error "
    "for 24 hours after the first request."
)
FACT = {
    "id": "af:stripe:idempotency-key-reuse-different-params",
    "service": "stripe",
    "kind": "error_meaning",
    "status": "verified:server:prod",
    "claim": CLAIM + "\n",
    "signal": {"status": 400, "error_code": "idempotency_error"},
    "fixes": [
        {
            "action": "set_header",
            "name": "Idempotency-Key",
            "value_source": "new_uuid_per_distinct_request",
        }
    ],
    "fixes_rendered": ["(server sentence, not used for a known action)"],
}
RESULT = {
    "service": "stripe",
    "matched_template": {"method": "POST", "path": "/v1/payment_intents"},
    "facts": [FACT],
    "registry": {"version": "2026-10-20", "license": "CC-BY-4.0"},
}
SIGNAL = make_signal(
    "https://api.stripe.com/v1/payment_intents?x=1", method="POST", status=400, body="{}"
)
PAGE = (
    "https://github.com/Illouminus/apifacts/blob/main/pages/stripe/"
    "idempotency-key-reuse-different-params.md"
)


def fact(**changes):
    out = copy.deepcopy(FACT)
    out.update(changes)
    return out


def test_title():
    assert TITLE == "Known facts (apifacts, CC BY 4.0)"


def test_spec_07_example_golden():
    assert render_section(RESULT, SIGNAL) == "\n".join(
        [
            "POST api.stripe.com/v1/payment_intents → 400 idempotency_error",
            f"✅ verified:server:prod · {CLAIM}",
            "   fix: Send header Idempotency-Key = new UUID per distinct request",
            f"   {PAGE}",
        ]
    )


def test_template_path_replaces_the_concrete_path():
    signal = make_signal("https://api.stripe.com/v1/customers/cus_1", method="GET", status=404)
    result = {**RESULT, "matched_template": {"method": "GET", "path": "/v1/customers/{id}"}}
    first = render_section(result, signal).splitlines()[0]
    assert first == "GET api.stripe.com/v1/customers/{id} → 404"


def test_server_sentence_only_for_an_unknown_action():
    unknown = fact(
        fixes=[{"action": "teleport", "to": "mars"}, FACT["fixes"][0]],
        fixes_rendered=["Teleport to Mars", "ignored"],
    )
    lines = render_section({**RESULT, "facts": [unknown]}, SIGNAL).splitlines()
    assert lines[2:4] == [
        "   fix: Teleport to Mars",
        "   fix: Send header Idempotency-Key = new UUID per distinct request",
    ]


def test_server_strings_are_one_clean_line():
    evil = fact(
        claim="ok\x1b[31m red\x1b[0m\nsecond line ‮evil",
        status="verified:server:prod\r\n",
        fixes=[{"action": "teleport"}],
        fixes_rendered=["do \x07this\nnow"],
    )
    text = render_section({**RESULT, "facts": [evil]}, SIGNAL)
    assert "\x1b" not in text and "\x07" not in text and "‮" not in text and "\r" not in text
    lines = text.splitlines()
    assert lines[1] == "✅ verified:server:prod · ok [31m red [0m second line evil"
    assert lines[2] == "   fix: do this now"


def test_badges():
    statuses = {
        "verified:server:sandbox": "✅",
        "verified:client": "✅",
        "official": "🔵",
        "reported": "🟡",
        "stale": "⚪",
        "something-new": "•",
    }
    for status, badge in statuses.items():
        line = render_section({**RESULT, "facts": [fact(status=status)]}, SIGNAL).splitlines()[1]
        assert line.startswith(f"{badge} {status} · ")


def test_retracted_facts_are_not_shown():
    assert render_section({**RESULT, "facts": [fact(status="retracted")]}, SIGNAL) is None


def test_more_than_five_facts_are_summarized():
    facts = [fact(id=f"af:stripe:fact-{i}") for i in range(7)]
    lines = render_section({**RESULT, "facts": facts}, SIGNAL).splitlines()
    assert sum(line.startswith("✅") for line in lines) == 5
    assert lines[-1] == (
        "… 2 more facts: https://github.com/Illouminus/apifacts/blob/main/pages/stripe/index.md"
    )


def test_bad_id_gives_no_page_line():
    lines = render_section({**RESULT, "facts": [fact(id="../../evil")]}, SIGNAL).splitlines()
    assert len(lines) == 3 and not lines[-1].strip().startswith("http")


def test_garbage_facts_are_skipped():
    result = {**RESULT, "facts": ["x", None, 3, {"claim": 5}, fact()]}
    assert render_section(result, SIGNAL).count("✅") == 1
    assert render_section({**RESULT, "facts": "nope"}, SIGNAL) is None
    assert render_section("nope", SIGNAL) is None


def test_no_facts_is_silent_unless_asked():
    empty = {"facts": [], "unknown": {"reason": "unregistered_target"}}
    signal = make_signal("https://api.github.com/user", method="GET", status=401)
    assert render_section(empty, signal) is None
    assert render_section(empty, signal, show_empty=True) == (
        "GET api.github.com/user → 401\nno known facts (unregistered_target)"
    )


def test_locator_target_line():
    signal = make_signal("pypi:stripe@12.1.0")
    text = render_section({"facts": []}, signal, show_empty=True)
    assert text == "pypi:stripe@12.1.0\nno known facts (no_fact_for_signal)"


def test_title_line_width_like_pytest_sep():
    # Fill derived from the title's length (the title changed with the apifacts rename, 25.10.2026):
    # an odd remainder goes to the right, like pytest's separator.
    fill = (64 - len(TITLE) - 2) // 2
    pad = "─" if 2 * fill + len(TITLE) + 2 < 64 else ""
    assert title_line(64) == f"{'─' * fill} {TITLE} {'─' * fill}{pad}"
    fill65 = (65 - len(TITLE) - 2) // 2
    pad65 = "─" if 2 * fill65 + len(TITLE) + 2 < 65 else ""
    assert title_line(65) == f"{'─' * fill65} {TITLE} {'─' * fill65}{pad65}"
    assert len(title_line(64)) == 64 and len(title_line(65)) == 65
    assert title_line(10) == f"─ {TITLE} ─"


def test_no_fix_lines_without_typed_fixes():
    lines = render_section({**RESULT, "facts": [fact(fixes=None)]}, SIGNAL).splitlines()
    assert not any("fix:" in line for line in lines)


def test_typed_fix_parameters_are_cleaned_too():
    sneaky = fact(
        fixes=[{"action": "use_endpoint", "method": "GET", "path_template": "/v1/\x1b[2Jx"}]
    )
    lines = render_section({**RESULT, "facts": [sneaky]}, SIGNAL).splitlines()
    assert lines[2] == "   fix: Call GET /v1/ [2Jx instead"


def test_error_code_only_from_a_shown_fact():
    hidden = fact(status="retracted", signal={"status": 400, "error_code": "ghost_code"})
    plain = fact(signal={"status": 400})
    first = render_section({**RESULT, "facts": [hidden, plain]}, SIGNAL).splitlines()[0]
    assert first == "POST api.stripe.com/v1/payment_intents → 400"
