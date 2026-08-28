# E4 interface-architecture harness

This directory is isolated from the frozen E3 runner. No file under
`tests/e3/` is modified.

Implemented development surface:

- four generated arm schemas: TEXT (5), TEXT_VERIFY (18), HYBRID (23),
  FULL_ALVA (42, byte-derived from the E3 HIGH schema);
- fail-closed `src/**/*.alva` allowlist with atomic write/patch and rollback;
- text/AIR synchronization and transaction state machine;
- internal E3 AEP adapter for the semantic control plane;
- FULL_ALVA adapter preserving the 42-tool model-facing surface;
- one arm-blind hidden-verifier bridge;
- OpenAI Responses API function relay pinned to `gpt-5.6-luna`;
- deterministic scripted relay and 12 x 4 no-model dry rehearsal.

Current evidence:

```text
unit tests:             30 PASS, 1 SKIP (Windows symlink unavailable)
dry rehearsal:          12 tasks x 4 arms = 48/48 PASS
provider/model calls:   0
```

The dry rehearsal proves schema, fixture-byte, relay, allowlist, lifecycle,
termination, and arm-blind verifier-routing alignment. It does **not** prove
real compiler/AEP integration. That gate remains open because this Windows
host lacks `link.exe` and Docker Desktop's Linux engine did not start. Do not
freeze execution or call Luna until the binary-backed rehearsal passes.

Run locally:

```text
cd tests/e4/runner
python -m unittest -v test_formal_runner.py test_full_runtime.py \
  test_luna_relay.py test_arm_runtime.py test_semantic_session.py \
  test_tool_schemas.py test_text_workspace.py

python rehearsal_runner.py --tasks <private-authoring-task-root> \
  --output rehearsal/E4-REHEARSAL-12x4.json
```

Credentials are environment-only. `luna_relay.py` reads `OPENAI_API_KEY`;
no key file path is accepted by the formal harness.
