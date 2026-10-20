"""Client side of `check()` (docs/specs/03-check-contract.md, 07-plugins.md).

Shared by the pytest plugin (`plugins/pytest`), `agentfacts check` and, later, the MCP server:
building a privacy-safe request, sending it, and rendering the "Known facts" section. Standard
library only at import time, so loading the plugin costs nothing until a test fails.
"""
