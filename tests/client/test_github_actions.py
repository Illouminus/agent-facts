from apifacts.client.github_actions import (
    append_summary,
    escape_data,
    escape_property,
    fenced,
    safe_log_line,
    warning,
)


def test_escape_data_percent_first():
    assert escape_data("100%\r\nnext %0A") == "100%25%0D%0Anext %250A"


def test_escape_property_also_colon_and_comma():
    assert escape_property("a: b, c%\n") == "a%3A b%2C c%25%0A"


def test_warning_line():
    line = warning("line one\nline two: 50%", title="apifacts: GET api.github.com/x → 404")
    assert line == (
        "::warning title=apifacts%3A GET api.github.com/x → 404::line one%0Aline two: 50%25"
    )
    assert "\n" not in line
    assert warning("x") == "::warning::x"


def test_a_server_string_cannot_open_a_second_command():
    line = warning("claim\n::error::pwned")
    assert line.count("\n") == 0 and line.startswith("::warning::")


def test_safe_log_line():
    assert safe_log_line("::set-output name=x::y") == " ::set-output name=x::y"
    assert safe_log_line("GET api.github.com/x → 404") == "GET api.github.com/x → 404"


def test_fence_outlasts_backticks_in_the_text():
    text = "claim with ```` four"
    block = fenced(text)
    assert block.startswith("`````text\n") and block.endswith("\n`````")


def test_append_summary(tmp_path, monkeypatch):
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    assert append_summary("one") and append_summary("two\n")
    assert path.read_text() == "one\ntwo\n"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY")
    assert append_summary("three") is False
