# Compact DeepSeek diagnostic — completed; no further launches

Disposition: **NO_EXPLORATORY_FAVORABLE_SIGNAL**. Native correctly completes
7/8 versus Text 6/8, but median paired successful-token ratio is 1.50955,
failing the prespecified <=0.75 efficiency screen. Read REPORT.md for the
different all-outcome resource view and limitations.

Sixteen fresh conversations; 256 submitted chat-completion HTTP attempts;
no replacements or additional model wave. Upstream generation-request counts
and dollar costs are null. No input-token-count API calls.

- REGISTRATION.json / PROTOCOL.md: independent provider variant; old GPT
  registration remains untouched.
- FREEZE.json / PREFLIGHT.json: exact pre-generation configuration and eight
  actual isolated T/N deterministic qualifications.
- RESULTS.json: all slots, pairs, provider usage, commits and outcomes.
- DIAGNOSIS.json: post-run tool/schema diagnosis, not a new passing criterion.
- VALIDATION.json / validate_evidence.py: exact request reconstruction and
  independent record/authority/test-receipt checks over controlled local logs.
- ARCHIVES.json / ATTEMPTS.md: raw archive hashes and preparation disclosures.

CI runs synthetic provider-loop and committed-artifact controls without access
to an API key, private raw logs, SSH host, or model generation.

```sh
python -m unittest benchmarks.compact_deepseek.test_runtime benchmarks.compact_deepseek.test_postrun -v
python -m benchmarks.compact_deepseek.validate_evidence /controlled/path/to/wave01
```

The old runner is retained as executed research code, not a new-run entry point.
The post-run safe_entry rejects this consumed freeze before creating any provider
or model session. A further experiment needs a separately registered study and
new immutable runtime freeze; do not replay this cohort to improve its score.
