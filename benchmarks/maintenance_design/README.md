# Maintenance candidates: design and engineering qualification only

See [evidence synthesis](../../docs/research/p20-p28-evidence-synthesis.md) and
[future study design](../../docs/research/semantic-maintenance-study-design.md).

Three candidates were declared before mechanical qualification, from exact
existing source blobs at P28. `TASK-CANDIDATES.json` includes public requirements,
source/adapter origins, byte hashes and exact input bundles. It contains no
patched program. The component-store manifest selects two unchanged modules;
the full storage server is not claimed qualified. All future model inputs must
be a strict allowlist of `public_inputs` plus separately approved generic docs.

`witnesses.py` contains **engineering-only answers and host assertions**. Do not
mount it, this folder, this report, FEASIBILITY output or repository history in
future model namespaces. It is not a new MCP/agent host. `feasibility.py` uses
the existing P22/P23 namespace, native stdio client and actual ALVA compiler.
It runs Text/Native actual artifacts, private-staging checks, fresh-process AIR
re-read and independent generated-Rust behavior tests. No provider API is used.

Actual local Linux/WSL result (`FEASIBILITY.json`):

| Candidate | Text | Native |
|---|---|---|
| MM01 negative-size update policy | PASS | SUPPORTED, goal/regressions PASS |
| MM02 first nonempty decoded prefix | PASS | FAILED_NON_TARGET_SCOPE; target PASS, regression FAIL |
| MM03 fallback accessor signature | PASS | UNSUPPORTED_NATIVE_MCP; required entry points absent |

MM02 reproduces a concrete ownership hazard without fixing it. The selected
anonymous parent revision is present under both parser functions. Replacing its
condition changes both bodies; the transaction checker accepts it and commit
succeeds, but parse_delimiter returns `/` where the independent last-match test
expects `!`. This is a failure of the tested local-maintenance sequence, not
proof that no alternative existing sequence can express the requirement.
MM03's exact Text API/caller edit passes. No CLI escape hatch or new operation
is added to Native. Neither limitation blocks the independent MM01 design.

The first engineering attempt used an invalid second begin in one MCP process;
it was removed, not repaired by redesigning the adapter. A fresh stale probe was
not executed. P20/P25 stale findings remain historical evidence; no recovery
success or new accepted-stale-write zero is invented. Qualification iterations
are not agent retries or new scientific slots; raw output stays ignored locally.

Reproduce from this branch (Linux is the **only** candidate execution backend):

```text
python -m unittest benchmarks.maintenance_design.test_design -v
python benchmarks/maintenance_design/feasibility.py run --alva /approved/alva --toolchain /approved/rust-sysroot --registry /approved/public-registry --output out/maintenance-raw.json
```

The last command writes raw engineering logs only to the requested ignored
destination and a sanitized derived `FEASIBILITY.json`. CI uploads its logs as
Artifacts, never as Git files. Success exit means the declared three candidate
dispositions were obtained, **not all candidates passed**. Unknown SDK/OS/
transport failure is FAILED, not converted into candidate support. There is no
host-permission fallback. Native Windows/macOS are unsupported; Windows may
orchestrate an explicit Linux WSL invocation as used locally.

`prepare` is not needed to use the checked catalogue. If deliberately rebuilding
it, commit the unchanged component manifest first: preparation reads immutable
Git blobs, not arbitrary worktree bytes, and binds the actual adapter commit.
Do not modify this catalogue after a future model freeze. Actual binary and
script hashes are in FEASIBILITY; external SDK/OS must be re-bound in a future
execution freeze. The previous execution logs and this node's engineering raw
output are not required by ordinary provenance tests.

No model study is authorized by these commands. The proposed next scope is one
MM01 T/S pair only, still **NOT_STARTED**. No historical frozen input/result,
Core source, semantic operation or installed plugin changed. STOP after review.
