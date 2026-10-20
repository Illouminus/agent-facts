Probe-runner fixture (W2): a fictional keyless prod service (`example`) and a fictional keyed sandbox
service (`examplepay`, key `af-fixture-examplepay`, never present). Used by `tests/probe/test_probe_cli.py`:

    uv run agentfacts probe run --all --dry-run --root tests/fixtures/probe-repo --state-dir <tmp>

The hosts are placeholders; nothing here is ever sent (dry run only).
