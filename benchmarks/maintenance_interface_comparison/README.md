# MIC-01: exploratory Text / Native maintenance comparison

**Disposition: INCONCLUSIVE_PROVIDER_LIMIT. No superiority claim.**
The original controller exhausted the scheduled request list, but this does
not mean the scientific comparison completed validly. Read REPORT.md first.

This new study extends the existing case-study evidence with fresh comparative
sessions on six **known** tasks. It does not reopen or rescore old experiments.
Original task bundles, assertions, Core, AEP/MCP, Skill and paper stay unchanged.

## Artifacts

- PROTOCOL.md / REGISTRATION.json: pre-generation selection, exact tasks,
  two repetitions per arm, docs, limits and decision rule.
- FREEZE.json / PREFLIGHT.json: actual SDK, Python runtime, CLI start hash,
  successful no-model tests and host dispatch checks.
- RESULTS.json: descriptive outcomes, quota exclusions, all pairs and usage.
- VALIDATION.json: raw-record/commit/fresh-authority/test-receipt consistency;
  explicitly NOT a certificate of full scientific validity or oracle independence.
- ATTEMPTS.md: preparation failures, corrected startup adapters, quota incident,
  two excess post-fault requests and CLI identity uncertainty.
- ARCHIVES.json: controlled raw/runtime/preparation archive hashes; not public
  raw-transcript access. No authentication context or SSH credential is archived.
- provider_gate.py / safe_run.py: post-run prospective controls, not retroactive
  changes to the frozen actor. The safe entry refuses this original freeze.

## Read-only checks

```sh
python -m unittest benchmarks.maintenance_interface_comparison.test_pilot benchmarks.maintenance_interface_comparison.test_provider_gate -v
python benchmarks/maintenance_interface_comparison/analyze.py PATH_TO_CONTROLLED_WAVE --output LOCAL_ANALYSIS.json
python benchmarks/maintenance_interface_comparison/validate.py PATH_TO_CONTROLLED_WAVE
```

The CI runs only unit/protocol controls on Linux and Windows. It does not start
models or repeat candidates/history. New live model execution is stopped. Do
not rerun pilot.py to fill the missing comparisons: the original exclusive
ledger intentionally prevents slot replacement. Repair, quota readiness and
a separately authorized new design/freeze are required before future runs.

## Exact runtime transport

The executed source commit is `9f1b2c06aec8540a004927f0333dc85c94e4e4c0`.
145 Python files were pinned from the actual Windows controller worktree and
uploaded byte-for-byte to the separate Linux study tree. 77 match Git blobs
directly; 68 match their CRLF checkout form. The exact runtime ZIP is retained.
To export those Python bytes into a fresh, separate directory:

```sh
python benchmarks/maintenance_interface_comparison/restore_runtime.py \
  --commit 9f1b2c06aec8540a004927f0333dc85c94e4e4c0 --output NEW_RUNTIME_EXPORT
```

Only fixed-hash matches are accepted. Overlay that export onto a separate copy
of the source artifact if required; never rewrite a historical checkout.
ALVA source/bundle/assertion inputs are not normalized. Re-executing with new
SDK/CLI bytes is a new configuration, not reproduction of an identical freeze.
The original CLI executable is no longer available at its initial resolved path.

Candidate code runs only in the supplied Linux OS namespaces. Existing local
authenticated Codex launches model turns; authentication is never transferred
to the candidate host. The new owner adapter repairs nested procfs/IPC setup;
the prospective resource profile uses per-UID nproc=512 because unrelated host
threads already exceeded the original 128 bound. This is not a dedicated-host
latency benchmark or a hostile-host security proof.

Current host API schema was checked through actual no-model AppServer RPC and
the [official AppServer documentation](https://learn.chatgpt.com/docs/app-server).
Model/provider request accounting and plan quotas are not inferred from a
logical count of turn/start submissions. Cached input remains in reported total.
