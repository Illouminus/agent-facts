"""pytest hooks: a test failing on an HTTP error from a registered API gets a "Known facts" section.

Nothing happens on a pass. On a failure: extract the signal; if the host is in the registry's
services list, one `check()` (2 s timeout); render the facts into the report. Any error inside the
plugin is swallowed: it never changes an outcome or interrupts the run.
"""

import pytest
from agentfacts.client.render import TITLE, render_section
from agentfacts.client.transport import Client

from agentfacts_pytest.client import make_client
from agentfacts_pytest.extract import signal_from_exception
from agentfacts_pytest.render import attach

CLIENT = pytest.StashKey[Client]()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agentfacts", "agent-facts registry")
    group.addoption(
        "--agentfacts-offline",
        action="store_true",
        default=False,
        help="answer from the fact snapshot shipped with the package; no network",
    )


def pytest_configure(config: pytest.Config) -> None:
    try:
        client = make_client(config)
    except Exception:
        return
    if client is not None:
        config.stash[CLIENT] = client


def annotate(report: pytest.TestReport, exc: BaseException, client: Client) -> None:
    signal = signal_from_exception(exc)
    if signal is None:
        return
    host = client.registered_host(signal.host)
    if host is None:
        return  # not a registered API: nothing leaves the machine
    if host != signal.host:
        signal = signal.with_host(host)  # tenant subdomains are not sent
    body = render_section(client.check(signal.payload()), signal)
    if body:
        attach(report, TITLE, body)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    report = yield
    client = item.config.stash.get(CLIENT, None)
    if client is not None and report.failed and call.excinfo is not None:
        try:
            annotate(report, call.excinfo.value, client)
        except Exception:
            pass
    return report
