"""Markdown safety helpers: registry text never turns into markup on a page."""

import pytest

from apifacts.pages.templates import autolink, code_span, md_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("plain", "`plain`"),
        ("a `b` c", "``a `b` c``"),
        ("``x", "``` ``x ```"),
        ("ends with `", "`` ends with ` ``"),
        ("a\n  b\tc", "`a b c`"),
        ("$#.## | [x](y)", "`$#.## | [x](y)`"),
    ],
)
def test_code_span(text, expected):
    assert code_span(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("snake_case stays", "snake_case stays"),
        ("_lead and trail_", r"\_lead and trail\_"),
        ("see [x](y)", r"see \[x\](y)"),
        ("*bold* <b> a|b $1 ~s~ `c` \\", r"\*bold\* \<b\> a\|b \$1 \~s\~ \`c\` \\"),
        ("# not a heading", r"\# not a heading"),
        ("- not a list", r"\- not a list"),
        ("+ not a list", r"\+ not a list"),
        ("= not setext", r"\= not setext"),
        ("2026. not ordered", r"2026\. not ordered"),
        ("3) not ordered", r"3\) not ordered"),
        ("a\n b", "a b"),
        ("HTTP 400 idempotency_error ≤ 5 ×", "HTTP 400 idempotency_error ≤ 5 ×"),
    ],
)
def test_md_text(text, expected):
    assert md_text(text) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://docs.stripe.com/api/a_b", "<https://docs.stripe.com/api/a_b>"),
        ("https://x.dev/a<b>c", "<https://x.dev/a%3Cb%3Ec>"),
        ("https://x.dev/\x01", "<https://x.dev/%01>"),
    ],
)
def test_autolink(url, expected):
    assert autolink(url) == expected
