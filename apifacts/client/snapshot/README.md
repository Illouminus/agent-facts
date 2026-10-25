# Packaged offline snapshot

Used by `pytest --apifacts-offline` and `apifacts check --offline` when `APIFACTS_SNAPSHOT` is
not set. Same layout as the registry: `services/*.yaml`, `facts/<service>/*.yaml`. Empty in wave 1;
a release build copies the registry's `services/` and `facts/` here (data: CC BY 4.0).
