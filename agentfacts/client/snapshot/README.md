# Packaged offline snapshot

Used by `pytest --agentfacts-offline` and `agentfacts check --offline` when `AGENTFACTS_SNAPSHOT` is
not set. Same layout as the registry: `services/*.yaml`, `facts/<service>/*.yaml`. Empty in wave 1;
a release build copies the registry's `services/` and `facts/` here (data: CC BY 4.0).
