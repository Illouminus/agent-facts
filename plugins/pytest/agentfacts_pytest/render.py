"""Putting the section into a pytest report.

As a section of the traceback representation when there is one: it prints right after the
traceback, is not filtered by `--show-capture`, and travels with the report (junitxml, xdist).
"""

import pytest

SEPARATOR = "─"


def attach(report: pytest.TestReport, title: str, body: str) -> None:
    longrepr = report.longrepr
    if hasattr(longrepr, "addsection"):
        longrepr.addsection(title, body, SEPARATOR)
    else:
        report.sections.append((title, body))
