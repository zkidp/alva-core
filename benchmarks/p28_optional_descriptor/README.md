# P28 optional native descriptor discovery

Exactly two new HE41 developmental slots, C1 then C0. The sole model-facing
change is the verbatim P27 developer addendum. C0 retains P26's full native
Skill, references, schemas and public task/stub. Neither condition receives
old candidates, engineering witnesses or evaluator code. No model calls in CI.

`pilot.py` reuses P26's AppServer setup, controller and drive loop; its scoped
controller adds the C1 instruction and records the first interrupt boundary.
`service.py` uses P26's service and P23's existing isolated stdio client. A
shared `ObservedNative` wrapper serially reads `inspect_body` in each real
model transaction after begin and successful mutations, before returning the
original, unmodified tool reply. Observer calls are private and counted
separately. They do not check, repair, commit or advise the model.

Only an actual changed body, associated with a completed model tool event
before the first interrupt request, meets the primary endpoint. This
conservative event-order rule can miss a read whose completion notification
arrives late; it never credits post-interrupt observations. No comparison of
Windows and Linux clocks is used. Detached nodes and `ok:true` do not qualify.
Fresh-process authority reads and independent isolated compilation/behavior
remain secondary, separate from transaction check and staging.

Preparation runs zero-model controller, native host/Skill/schema, same-live-
transaction observer, real relay, isolated compiler/evaluator validations.
Observer purity uses a separate trivial string fixture, not an HE41 solution.
The development test initially attempted an integer `change_field`; that
operation writes a string field, so the test uses a string-to-string change.
No Core change was made. All preparation attempts made zero model calls.

Commands (trusted Windows orchestration, Ubuntu-26.04 WSL candidate backend):

```text
python -m unittest benchmarks.p28_optional_descriptor.test_pilot -v
python benchmarks/p28_optional_descriptor/pilot.py prepare --attempt <new-preflight-dir> --alva <approved-linux-binary> --toolchain <approved-sysroot> --registry <approved-registry>
# Review, commit and push FREEZE.json and PREFLIGHT.json; require clean HEAD==origin.
python benchmarks/p28_optional_descriptor/pilot.py run --attempt scientific-wave-1 --alva <same-binary> --toolchain <same-sysroot> --registry <same-registry>
```

`STARTED.json` is created exclusively: no retries, replacement or third slot.
Machine-local configs, transcripts, candidates, AIR, diagnostics and raw ZIP
remain in ignored `.local/p28-optional-descriptor/`; only bounded derived
summaries and archive hashes enter Git. Credentials are not read, hashed or
archived. Existing authenticated CLI configuration isolation is unchanged.

Linux is the only candidate execution backend. Windows orchestrates WSL, not
native candidate execution. macOS/Windows-native isolation is unsupported.
120000 tokens is an observation threshold with acknowledged interruption,
not a provider hard cap. Both actual excess usage and missing usage are kept;
cached/reasoning tokens are not subtracted from totals. Provider request counts
and monetary costs unavailable from this transport remain unknown.

This is one analysis-informed task and one observation per condition. Neither
an improved nor a failed pair establishes general causality or superiority.
P26/P27 and earlier frozen records remain unchanged. STOP after the two slots.

After execution, `REPORT.md`, `RESULTS.json`, `ANALYSIS.json` and `VALIDATION.json`
record the closed pair. `ci_exact_runtime.py` is a CI-only reader of the original
freeze's exact runtime bytes, not a modified scientific runner. Use it for
cross-platform frozen unit tests when Git checkout EOL differs from an inherited
dependency's approved execution bytes. No normalization/hash alternatives are
accepted, no repository files are overwritten and no model is called.
