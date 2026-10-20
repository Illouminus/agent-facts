"""`agentfacts pages build [--root] [--out] [--check] [--registry-version]`.

Exit codes: 0 ok / up to date, 1 out of date or unreadable registry, 2 usage error.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentfacts.cli import app
from agentfacts.pages.templates import FOOTER

GOLDEN = Path(__file__).parent / "golden"
REPO = Path(__file__).parents[2]

runner = CliRunner()


def _pages(*args: str):
    return runner.invoke(app, ["pages", "build", *args])


def test_build_then_check_is_clean(fixture_root, tmp_path):
    out = tmp_path / "out"
    result = _pages("--root", str(fixture_root), "--out", str(out))
    assert result.exit_code == 0, result.output
    assert (out / "stripe" / "idempotency-key-reuse-different-params.md").is_file()
    assert "11 pages" in result.stderr
    result = _pages("--root", str(fixture_root), "--out", str(out), "--check")
    assert result.exit_code == 0, result.output
    assert "up to date" in result.stderr


def test_golden_tree_passes_check_through_the_cli(fixture_root):
    result = _pages("--root", str(fixture_root), "--out", str(GOLDEN), "--check")
    assert result.exit_code == 0, result.output


def test_repository_pages_are_up_to_date():
    """The same check CI runs: pages/ matches services/ + facts/ of this checkout."""
    result = _pages("--root", str(REPO), "--check")
    assert result.exit_code == 0, result.output


def test_check_writes_nothing(fixture_root, tmp_path):
    out = tmp_path / "out"
    result = _pages("--root", str(fixture_root), "--out", str(out), "--check")
    assert result.exit_code == 1
    assert "missing: index.md" in result.stdout
    assert "out of date" in result.stderr
    assert not out.exists()


def test_check_reports_changed_missing_and_extra(fixture_root, tmp_path):
    out = tmp_path / "out"
    assert _pages("--root", str(fixture_root), "--out", str(out)).exit_code == 0
    (out / "stripe" / "index.md").write_text("# edited by hand\n", encoding="utf-8")
    (out / "example" / "sdk-v2-legacy-endpoint.md").unlink()
    (out / "stripe" / "gone.md").write_text(f"# old\n\n{FOOTER}\n", encoding="utf-8")
    result = _pages("--root", str(fixture_root), "--out", str(out), "--check")
    assert result.exit_code == 1
    assert result.stdout.splitlines() == [
        "changed: stripe/index.md",
        "missing: example/sdk-v2-legacy-endpoint.md",
        "extra: stripe/gone.md",
    ]


def test_hand_written_files_are_neither_reported_nor_removed(fixture_root, tmp_path):
    out = tmp_path / "out"
    assert _pages("--root", str(fixture_root), "--out", str(out)).exit_code == 0
    readme = out / "README.md"
    readme.write_text("# About these pages\n", encoding="utf-8")
    assert _pages("--root", str(fixture_root), "--out", str(out), "--check").exit_code == 0
    assert _pages("--root", str(fixture_root), "--out", str(out)).exit_code == 0
    assert readme.is_file()


def test_build_removes_stale_generated_pages(fixture_root, tmp_path):
    out = tmp_path / "out"
    stale = out / "retired" / "old.md"
    stale.parent.mkdir(parents=True)
    stale.write_text(f"# old\n\n{FOOTER}\n", encoding="utf-8")
    result = _pages("--root", str(fixture_root), "--out", str(out))
    assert result.exit_code == 0, result.output
    assert "1 removed" in result.stderr
    assert not stale.exists()
    assert not stale.parent.exists()


def test_empty_registry_defaults_out_to_root_pages(tmp_path):
    result = _pages("--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in (tmp_path / "pages").rglob("*")) == ["index.md"]
    assert _pages("--root", str(tmp_path), "--check").exit_code == 0


def test_registry_version_option(fixture_root, tmp_path):
    out = tmp_path / "out"
    version = ("--registry-version", "2026-11-01")
    result = _pages("--root", str(fixture_root), "--out", str(out), *version)
    assert result.exit_code == 0, result.output
    assert "Registry version 2026-11-01" in (out / "index.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("value", ["yesterday", "2026-13-45", "2026-02-30", "20261020"])
def test_bad_registry_version_is_a_usage_error(tmp_path, value):
    result = _pages("--root", str(tmp_path), "--registry-version", value)
    assert result.exit_code == 2, result.output


def test_footer_quoted_in_a_document_is_not_ours(fixture_root, tmp_path):
    """Spec 06 itself quotes the footer phrase: only an exact final footer line marks a page."""
    out = tmp_path / "out"
    doc = out / "notes" / "spec.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("Template ends with: This page is generated; edit the YAML, not the page.\n")
    assert _pages("--root", str(fixture_root), "--out", str(out)).exit_code == 0
    assert doc.is_file()


def test_out_that_is_a_file_is_an_error_not_a_traceback(fixture_root, tmp_path):
    out = tmp_path / "out.md"
    out.write_text("x\n", encoding="utf-8")
    result = _pages("--root", str(fixture_root), "--out", str(out))
    assert result.exit_code == 1
    assert "not a directory" in result.stderr
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_invalid_registry_exits_1_with_a_validate_hint(fixture_root, tmp_path):
    (fixture_root / "facts" / "stripe" / "broken.yaml").write_text("kind: nope\n", encoding="utf-8")
    result = _pages("--root", str(fixture_root), "--out", str(tmp_path / "out"))
    assert result.exit_code == 1
    assert "broken.yaml" in result.stderr
    assert "agentfacts validate" in result.stderr
