"""Redaction filter: every string passes it before results.jsonl, logs or facts (spec 04)."""

import json

from agentfacts.probe.redact import REDACTED, Redactor


def test_exact_secret_and_patterns_are_redacted():
    r = Redactor({"s3cr3t-value-123"})
    text = "k=s3cr3t-value-123 sk_test_abcdefgh123 Bearer abcdefghijklmnop1234 " + "a1" * 16
    out = r.text(text)
    for leaked in ("s3cr3t-value-123", "sk_test_abcdefgh123", "abcdefghijklmnop1234", "a1" * 16):
        assert leaked not in out
    assert REDACTED in out


def test_hex_run_of_32_is_redacted_even_without_letters():
    assert "1" * 32 not in Redactor(set()).text("id " + "1" * 32)


def test_short_hex_and_base64_runs_survive():
    r = Redactor(set())
    assert r.text("req_ABC123 deadbeef") == "req_ABC123 deadbeef"
    assert r.text("x" * 30 + "1") == "x" * 30 + "1"  # 31 chars
    assert r.text("x" * 31 + "1") == REDACTED  # 32 chars


def test_words_and_urls_survive():
    r = Redactor(set())
    msg = "see https://docs.stripe.com/error-codes/idempotency-error for details"
    assert r.text(msg) == msg


def test_longest_secret_first():
    r = Redactor({"abcdefgh", "abcdefgh-extended"})
    assert r.text("abcdefgh-extended") == REDACTED


def test_empty_secrets_are_ignored():
    assert Redactor({"", "  "}).text("plain text") == "plain text"


def test_record_redacts_nested_strings_and_keys():
    r = Redactor({"FAKEKEY12345678"})
    rec = {"steps": [{"headers": {"x-echo": "FAKEKEY12345678"}, "FAKEKEY12345678": 1}]}
    assert "FAKEKEY12345678" not in json.dumps(r.record(rec))


def test_record_exempts_identifiers_but_not_exact_secrets():
    r = Redactor({"FAKEKEY12345678"})
    rec = {
        "probe_id": "af:x:probe:values-batch-get-v4-range-limit-exceeded",
        "body_fingerprint": "ab" * 32,
        "steps": [{"error_string": "token FAKEKEY12345678 " + "0f" * 20}],
        "facts": [{"id": "af:x:values-batch-get-v4-range-limit-exceeded", "change": "confirmed"}],
    }
    out = r.record(rec)
    assert out["probe_id"] == rec["probe_id"]
    assert out["body_fingerprint"] == "ab" * 32
    assert out["facts"] == rec["facts"]
    dumped = json.dumps(out)
    assert "FAKEKEY12345678" not in dumped
    assert "0f" * 20 not in dumped


def test_exempt_fields_still_lose_exact_secrets():
    r = Redactor({"FAKEKEY12345678"})
    assert r.record({"probe_id": "FAKEKEY12345678"}) == {"probe_id": REDACTED}


def test_line_scan_catches_strict_patterns_only():
    r = Redactor({"FAKEKEY12345678"})
    line = '{"a":"FAKEKEY12345678","b":"sk_live_abcdefgh1","fp":"' + "ab" * 32 + '"}'
    out = r.line(line)
    assert "FAKEKEY12345678" not in out and "sk_live_abcdefgh1" not in out
    assert "ab" * 32 in out


def test_non_strings_pass_through():
    data = {"n": 3, "ok": True, "x": None}
    assert Redactor(set()).record(data) == data
