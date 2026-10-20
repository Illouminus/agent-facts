from pathlib import Path

import pytest
from probe_builders import Repo


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "repo")
