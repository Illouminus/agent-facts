# Packaged offline snapshot

Used by `pytest --apifacts-offline` and `apifacts check --offline` when `APIFACTS_SNAPSHOT` is
not set. Same layout as the registry: `services/*.yaml`, `facts/<service>/*.yaml`. Empty in git; the
wheel build copies the registry's `services/` and `facts/` here (`pyproject.toml` → `force-include`;
data: CC BY 4.0, see `LICENSE-DATA`).
