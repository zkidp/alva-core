# Compact maintenance diagnosis and prospective protocol

Current status: **COST_ANALYSIS_COMPLETE; DESIGN_REGISTERED; RUNTIME_NOT_FROZEN**.
Model generation calls = 0. Input-token API calls = 0. No new model outcome,
cost improvement or superiority claim is delivered here.

- COST-REPORT.md / COST-PROFILE.json: authenticated, read-only diagnosis of
  MIC-01 traces; explicit byte/call versus token measurement boundaries.
- PROTOCOL.md / REGISTRATION.json: four known tasks, two repetitions, two arms,
  sixteen slots; equal outcome policy; fixed 25% paired token screening rule.
- contract.py: shared typed workbench schemas and validation, with source
  edits exposed only in T. Native uses the existing nine-tool body-edit profile.
- score.py: prospective screen with infrastructure/missing-usage handling.
- register.py: deterministic task/docs/schedule binding and drift checks.
- test_study.py: normalization, accounting, contract and scoring regressions.

```sh
python -m benchmarks.compact_maintenance.register --check
python -m unittest benchmarks.compact_maintenance.test_study -v
```

The next stage is new-runtime integration and actual zero-model T/N
qualification, followed by a separately committed runtime freeze. No runnable
model launcher is provided in this phase. Do not reuse MIC-01's obsolete freeze,
mount this directory in a model workspace, or claim that synthetic CI tests
constitute real session preflight. Historical artifacts, Core/AEP/MCP, official
Skill and paper bytes remain unchanged by this directory.
