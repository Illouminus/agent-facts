"""Redaction filter: every string passes it before results.jsonl, logs or facts (spec 04)."""

import base64
import json
from urllib.parse import quote

import pytest

from apifacts.probe.redact import REDACTED, Redactor, secret_forms


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
        "steps": [
            {"body_fingerprint": "ab" * 32, "error_string": "token FAKEKEY12345678 " + "0f" * 20}
        ],
        "facts": [{"id": "af:x:values-batch-get-v4-range-limit-exceeded", "change": "confirmed"}],
    }
    out = r.record(rec)
    assert out["probe_id"] == rec["probe_id"]
    assert out["steps"][0]["body_fingerprint"] == "ab" * 32
    assert out["facts"] == rec["facts"]
    dumped = json.dumps(out)
    assert "FAKEKEY12345678" not in dumped
    assert "0f" * 20 not in dumped


def test_exemption_is_by_full_path_not_by_key_name():
    r = Redactor(set())
    token = "ab12" * 10
    rec = {"steps": [{"headers": {"id": token, "kind": token}, "body_fingerprint": token}],
           "nested": {"probe_id": token}}
    out = r.record(rec)
    assert out["steps"][0]["headers"] == {"id": REDACTED, "kind": REDACTED}
    assert out["nested"]["probe_id"] == REDACTED
    assert out["steps"][0]["body_fingerprint"] == token


def test_secret_forms_cover_url_and_basic_encodings():
    key = "user:pa ss/word"
    forms = secret_forms(key)
    assert {key, quote(key, safe=""), base64.b64encode(key.encode()).decode()} <= forms
    assert base64.b64encode(b"tok123:").decode() in secret_forms("tok123")
    assert secret_forms("  ") == set()


def test_for_keys_redacts_every_form():
    r = Redactor.for_keys(["tok/12345678"])
    text = "q=tok%2F12345678 auth=" + base64.b64encode(b"tok/12345678:").decode()
    assert "12345678" not in r.text_strict(text)


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


def test_exact_secrets_match_case_insensitively():
    r = Redactor({"FakeKey-12345678"})
    assert r.text_strict("lower fakekey-12345678 UPPER FAKEKEY-12345678") == (
        f"lower {REDACTED} UPPER {REDACTED}")


def test_bearer_pattern_is_case_insensitive():
    assert "abcdefghijklmnop1234" not in Redactor(set()).text_strict("bearer abcdefghijklmnop1234")


PEM = (
    "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\n"
    "q1w2e3r4t5y6\n-----END PRIVATE KEY-----\n"
)


@pytest.mark.parametrize(
    "secret",
    [
        PEM,
        PEM.replace("\n", "\\n"),  # as it sits inside a JSON string
        PEM.replace("PRIVATE KEY", "RSA PRIVATE KEY"),
        "AIzaSyFAKEfakeFAKEfakeFAKEfakeFAKEfa_-1",  # Google API key shape
        "ya29.a0AfB_FAKEfakeFAKEfake-FAKE",  # Google OAuth access token
        "123456789:AAFakeFakeFakeFakeFakeFakeFakeFake_x",  # Telegram bot token
        "https://api.telegram.org/bot123456789:AAFakeFakeFakeFakeFakeFakeFakeFake_x/getMe",
        "force://PlatformCLI::5A" "ep861FAKErefreshFAKErefresh.FAKE@acme.my.salesforce.com",
        "00D" "FAKEfake000000!AQEAQFAKEaccessFAKEaccessFAKEaccess.FAKE_0123",  # split literal
        "5A" "ep861FAKErefreshFAKErefreshFAKErefresh.FAKE_refresh0123456789",  # split literal
    ],
)
def test_vendor_secret_shapes_are_strict(secret):
    out = Redactor(set()).line(f'{{"x": "{secret}"}}')
    assert secret.strip() not in out and REDACTED in out and "FakeFake" not in out
    assert "PRIVATE KEY" not in out and "MIIEvQ" not in out


def test_a_truncated_pem_block_still_loses_its_body():
    out = Redactor(set()).line("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEF")
    assert "MIIEvQ" not in out


def test_short_lookalikes_survive():
    text = "AIza is a prefix, ya29 too, 12:30 and 1234567:short"
    assert Redactor(set()).line(text) == text


def test_add_extends_the_exact_secrets():
    r = Redactor({"first-secret-value"})
    r.add({"minted-token-value", ""})
    assert r.text_strict("minted-token-value / first-secret-value") == f"{REDACTED} / {REDACTED}"
