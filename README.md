# Merge findings: preserved pipeline example

This pure code Cog merges detector findings with provenance. It was built through
the Cog pipeline and is used by [op-builder-smoke](https://github.com/cogcloud-ai/op-builder-smoke)
for real execution and recovery checks. It is a candidate example, not an
automatically accepted replacement for the original reference implementation.

Read [COG.md](COG.md) for the contract, policies, and known comparison limits.
See the [suite setup](https://github.com/cogcloud-ai/cog-op-builder/blob/main/docs/getting-started.md)
for the complete sibling checkout layout.

```sh
pixi install
pixi run test
```

The original generated source and task logic are preserved. BUILD-HANDOFF.json
contains the accepted build contract and source handoff, not provider credentials
or a record of release acceptance. Tests use synthetic detector findings.

Copyright 2026 OpenTeams. Licensed under [Apache-2.0](LICENSE), matching the
candidate's original manifest declaration.
