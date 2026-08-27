# E3 run termination taxonomy (frozen 2026-08-27)

Frozen before the no-model rehearsal. The runner maps every run end to
exactly one category; only INFRA_FAILURE is rerunnable, and only under the
pre-registered rerun rule (no outcome-based reruns, no automatic reruns of
agent failures).

```text
VALID_OUTCOME (agent-produced; NEVER auto-rerun):
  TIMEOUT                 run exceeded the frozen time budget
  AGENT_GAVE_UP           agent terminated without a commit
  BAD_SOLUTION            committed but hidden verifier rejected it
  NO_COMMIT               no commit_transaction before run end
  VERIFIER_FAIL           verifier failed on the committed store
  NO_CHECK_PASS           no check_transaction PASS reached (Guardrail B)

INFRA_FAILURE (pre-registered rerun allowed, with recorded reason):
  CONTAINER_FAILED        container/image failed to start
  API_UNREACHABLE         model API request never reached the provider
  WORKSPACE_CORRUPT       frozen fixture hash mismatch / copy corruption
  RUNNER_CRASH            runner process error (crash/exception)
  HOST_FAILURE            disk/host failure
```

Rules:

- A run is recorded with exactly one termination reason.
- Agent failure/timeout/bad solution are VALID_OUTCOME; no replacement
  run, no imputation.
- INFRA_FAILURE reruns preserve the original slot identity and record
  `rerun_of` provenance; at most the pre-registered number of reruns
  (default 1) per slot.
- The taxonomy is part of the frozen analysis inputs.
