"""Budget state: per (probe, vantage) and per (service, method, template, vantage) — invariant 6."""

from apifacts.probe.budget import BudgetState

T = 1_800_000_000.0
ITEMS = [("acme", "GET", "/v1/items")]
ONE = [("acme", "GET", "/v1/items/{id}")]


def test_never_run_probe_is_due(tmp_path):
    with BudgetState(tmp_path / "s.sqlite") as state:
        assert state.wait_seconds("p1", ITEMS, "illouminus", 300, T) == 0
        assert state.last_run("p1", "illouminus") is None


def test_probe_waits_for_its_budget(tmp_path):
    with BudgetState(tmp_path / "s.sqlite") as state:
        state.record("p1", ITEMS, "illouminus", T, "pass")
        assert state.wait_seconds("p1", ITEMS, "illouminus", 300, T + 299) == 1
        assert state.wait_seconds("p1", ITEMS, "illouminus", 300, T + 300) == 0
        assert state.last_run("p1", "illouminus") == (T, "pass")


def test_a_shared_template_delays_another_probe(tmp_path):
    with BudgetState(tmp_path / "s.sqlite") as state:
        state.record("p1", ITEMS, "illouminus", T, "pass")
        assert state.wait_seconds("p2", ITEMS + ONE, "illouminus", 300, T + 10) == 290
        assert state.wait_seconds("p3", ONE, "illouminus", 300, T + 10) == 0


def test_vantages_are_independent(tmp_path):
    with BudgetState(tmp_path / "s.sqlite") as state:
        state.record("p1", ITEMS, "illouminus", T, "pass")
        assert state.wait_seconds("p1", ITEMS, "freebox", 300, T + 1) == 0


def test_state_survives_reopening(tmp_path):
    path = tmp_path / "deep" / "s.sqlite"
    with BudgetState(path) as state:
        state.record("p1", ITEMS, "illouminus", T, "fail")
    with BudgetState(path) as state:
        assert state.last_run("p1", "illouminus") == (T, "fail")
        assert state.template_last("acme", "GET", "/v1/items", "illouminus") == T


def test_read_only_never_creates_or_writes(tmp_path):
    path = tmp_path / "s.sqlite"
    with BudgetState(path, read_only=True) as state:
        assert state.wait_seconds("p1", ITEMS, "illouminus", 300, T) == 0
        state.record("p1", ITEMS, "illouminus", T, "pass")  # ignored
    assert not path.exists()
    with BudgetState(path) as state:
        state.record("p1", ITEMS, "illouminus", T, "pass")
    with BudgetState(path, read_only=True) as state:
        assert state.wait_seconds("p1", ITEMS, "illouminus", 300, T + 1) == 299
        state.record("p1", ITEMS, "illouminus", T + 1000, "pass")
    with BudgetState(path) as state:
        assert state.last_run("p1", "illouminus") == (T, "pass")
