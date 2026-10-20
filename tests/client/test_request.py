import pytest

from agentfacts.client.request import (
    EXCERPT_BYTES,
    Signal,
    excerpt,
    make_signal,
    redact,
    scrub_url,
)

STRIPE_MESSAGE = (
    "Keys for idempotent requests can only be used with the same parameters "
    "they were first used with."
)


@pytest.mark.parametrize(
    "secret",
    [
        "sk_live_51HxAbCdEfGhIjKlMn",
        "rk_test_4eC39HqLyjWDarjtT1zdp7dc",
        "whsec_abcdefgh12345678",
        "pi_3NabcDEF_secret_xyzXYZ123abc",
        "ghp_" + "a1B2" * 9,
        "github_pat_11ABCDEFG0123456789_abcdefghijk",
        "xoxb-123456789012-123456789012-abcdefABCDEF",
        "sk-proj-abcdefghij0123456789ABCD",
        "sk-ant-api03-abcdefghij0123456789",
        "AIzaSyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUv",
        "AKIAIOSFODNN7EXAMPLE",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
        "SG.abcdefghijklmnop1234.qrstuvwxyzABCDEF5678",
        "glpat-abcdefghij0123456789",
        "hf_abcdefghijklmnopqrstuvwxyz0123",
        "npm_abcdefghijklmnopqrstuvwxyz0123456789",
    ],
)
def test_known_secret_shapes_are_redacted(secret):
    out = redact(f"error: bad credential {secret} (see docs)")
    assert secret not in out
    assert "<redacted>" in out
    assert out.startswith("error: bad credential ")


def test_auth_scheme_values_are_redacted_scheme_kept():
    out = redact("got header Authorization: Bearer abc.def-ghi_jkl123 and Basic dXNlcjpwYXNz")
    assert "abc.def-ghi_jkl123" not in out and "dXNlcjpwYXNz" not in out
    assert "Bearer <redacted>" in out and "Basic <redacted>" in out


@pytest.mark.parametrize(
    "text, name",
    [
        ('{"api_key": "abc123secret"}', "api_key"),
        ("password=hunter2!", "password"),
        ("client_secret: s3cr3t-value", "client_secret"),
        ("access-token = 'tok_value_1'", "access-token"),
    ],
)
def test_secret_named_values_are_redacted_name_kept(text, name):
    out = redact(text)
    assert name in out
    assert "<redacted>" in out
    for value in ("abc123secret", "hunter2", "s3cr3t-value", "tok_value_1"):
        assert value not in out


def test_pem_private_key_block_is_redacted():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nIBAAKC\n-----END RSA PRIVATE KEY-----"
    out = redact(f"loaded {pem} ok")
    assert "MIIEow" not in out and out == "loaded <redacted> ok"


def test_emails_become_placeholder():
    assert redact("No such user: jane.doe+test@example.co.uk.") == "No such user: <email>."


def test_hex_and_uuid_runs_become_id():
    hex40, uuid = "0123456789abcdef0123456789abcdef01234567", "123e4567-e89b-12d3-a456-426614174000"
    out = redact(f"request {hex40} / {uuid}")
    assert out == "request <id> / <id>"


def test_long_mixed_run_is_redacted_but_words_survive():
    out = redact(
        "token value Zx9vQ2mL7pR4sT1uW8yA3bC6dE0fG5hJ and resource_missing_for_customer_object_here"
    )
    assert "Zx9vQ2mL7pR4sT1uW8yA3bC6dE0fG5hJ" not in out
    assert "resource_missing_for_customer_object_here" in out


def test_urls_in_text_become_the_server_placeholder():
    url = "https://api.stripe.com/v1/charges"
    out = redact(f"400 Client Error for url: {url}?api_key=abc&x=1#frag done")
    assert out == "400 Client Error for url: <url> done"


def test_vendor_error_message_is_unchanged():
    body = (
        '{"error": {"code": "idempotency_error", "message": "%s", "type": "invalid_request_error"}}'
    )
    assert redact(body % STRIPE_MESSAGE) == body % STRIPE_MESSAGE


def test_excerpt_is_capped_in_utf8_bytes_without_splitting_a_character():
    text = "é" * 3000  # 2 bytes each
    out = excerpt(text)
    assert len(out.encode()) <= EXCERPT_BYTES
    assert out == "é" * (EXCERPT_BYTES // 2)


def test_excerpt_never_leaks_a_prefix_of_a_secret_at_the_cut():
    secret = "sk_live_" + "A1b2C3d4" * 4
    text = "x" * (EXCERPT_BYTES - 10) + " " + secret + " tail"
    out = excerpt(text)
    assert "sk_live" not in out
    assert len(out.encode()) <= EXCERPT_BYTES


def test_excerpt_of_huge_input_is_fast_and_bounded():
    out = excerpt("a" * 5_000_000)
    assert len(out.encode()) == EXCERPT_BYTES


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://api.stripe.com/v1/payment_intents", "https://api.stripe.com/v1/payment_intents"),
        (
            "https://user:pw@API.Stripe.com:443/v1/charges?key=abc#x",
            "https://api.stripe.com/v1/charges",
        ),
        ("http://example.org", "http://example.org/"),
        (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=AIzaX",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
        ),
        (
            "https://api.telegram.org/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/sendMessage",
            "https://api.telegram.org/<redacted>/sendMessage",
        ),
        (
            "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX1a",
            "https://hooks.slack.com/services/T00000000/B00000000/<redacted>",
        ),
        (
            "https://example.solana-mainnet.quiknode.pro/0123456789abcdef0123456789abcdef01234567/",
            "https://example.solana-mainnet.quiknode.pro/<redacted>/",
        ),
    ],
)
def test_scrub_url(url, expected):
    assert scrub_url(url) == expected


@pytest.mark.parametrize(
    "url", ["ftp://x.org/a", "not a url", "", "https:///nohost", "mailto:a@b.c"]
)
def test_scrub_url_rejects_non_http(url):
    assert scrub_url(url) is None


def test_make_signal_builds_spec_03_payload():
    signal = make_signal(
        "https://api.stripe.com/v1/payment_intents?amount=1",
        method="post",
        status=400,
        body='{"error": {"message": "Invalid API Key provided: sk_test_abcdefgh1234"}}',
    )
    assert signal is not None
    assert signal.host == "api.stripe.com"
    payload = signal.payload()
    assert set(payload) == {"target", "error"}
    assert payload["target"] == {
        "method": "POST",
        "url": "https://api.stripe.com/v1/payment_intents",
    }
    assert payload["error"]["status"] == 400
    assert "sk_test_abcdefgh1234" not in payload["error"]["body_excerpt"]


def test_payload_omits_unknown_parts_and_carries_sdk_context():
    sdk = {"package": "openai", "ecosystem": "pypi", "version": "2.3.0"}
    signal = make_signal("https://api.openai.com/v1/responses", sdk=sdk)
    assert signal.payload() == {
        "target": {"url": "https://api.openai.com/v1/responses"},
        "context": {"sdk": sdk},
    }


def test_make_signal_rejects_bad_inputs():
    assert make_signal("ftp://x.org/") is None
    assert make_signal("https://x.org/", method="BREW").method is None
    assert make_signal("https://x.org/", status=42).status is None
    assert make_signal("https://x.org/", status=True).status is None
    assert make_signal("https://x.org/", body="").body_excerpt is None


def test_with_host_replaces_only_the_host():
    signal = make_signal("https://acme.my.salesforce.com/services/data/v60.0/query", status=401)
    moved = signal.with_host("my.salesforce.com")
    assert moved.url == "https://my.salesforce.com/services/data/v60.0/query"
    assert moved.host == "my.salesforce.com" and moved.status == 401


def test_signal_is_frozen():
    signal = Signal(url="https://x.org/")
    with pytest.raises(AttributeError):
        signal.url = "https://evil.example/"


@pytest.mark.parametrize(
    "text, leaked",
    [
        ('{"password": "correct horse battery staple"}', "horse"),
        ("{'client_secret': 'two words'}", "words"),
        ("db error: postgres://admin:hunter2@db.internal:5432/app failed", "hunter2"),
        ("see https://bob:pw123@api.example.org/v1/x?token=abc", "pw123"),
        ("redis://:s3cret@cache:6379/0?x=1", "s3cret"),
        ("postgres://user:pa/ss@db/app", "pa"),
        ("amqp://user:p?w#d@mq/vhost", "p?w"),
        ("https://host/p?email=a@b.com&token=SECRET", "SECRET"),
        ("redis://user:pa ss@cache", "pa"),
        ("user jane.doe%40example.com not found", "jane.doe"),
    ],
)
def test_review_findings_do_not_leak(text, leaked):
    assert leaked not in redact(text)


def test_urls_of_any_scheme_go_whole():
    assert redact("connect postgres://admin:pw@db:5432/app?sslmode=x ok") == "connect <url> ok"
    assert redact("see https://host/p?email=a@b.com&token=SECRET end") == "see <url> end"
    out = redact("dsn mysql://root:pa ss@db")
    assert "pa" not in out and "ss" not in out
    assert redact("db at postgres://db:5432/app?x=1 down") == "db at <url> down"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.org/users/jane%40example.com",
        "https://api.example.org/bot123456789%3AAAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/send",
    ],
)
def test_percent_encoded_path_secrets_are_redacted(url):
    scrubbed = scrub_url(url)
    assert "<redacted>" in scrubbed
    assert "jane" not in scrubbed and "AAHdq" not in scrubbed


@pytest.mark.parametrize(
    "text, fragments",
    [
        ("dsn postgres://u:123 45@db/app failed", ("123", "45")),
        ("dsn redis://u:pa ss@cache", ("pa", "ss")),
        ("dsn redis://:a b c@cache:6379/0", (":a", " b ", "c@")),
    ],
)
def test_passwords_with_raw_spaces_leave_nothing(text, fragments):
    out = redact(text)
    assert out.startswith("dsn ") and "<redacted>" in out
    for fragment in fragments:
        assert fragment not in out, (fragment, out)


def test_ordinary_text_after_a_url_is_kept():
    text = "Visit https://docs.stripe.com/x or contact support for help"
    assert redact(text) == "Visit <url> or contact support for help"


def test_kept_path_segments_are_sent_as_encoded():
    url = "https://api.example.org/v1/files/a%2Fb/x%20y"
    assert scrub_url(url) == url


def test_complete_needs_a_method_only_for_a_path():
    assert not make_signal("https://api.stripe.com/v1/charges").complete
    assert make_signal("https://api.stripe.com/v1/charges", method="GET").complete
    assert make_signal("https://api.stripe.com").complete
    assert make_signal("pypi:stripe@12.1.0").complete
