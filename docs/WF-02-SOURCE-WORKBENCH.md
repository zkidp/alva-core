# Source workbench with optional semantic observation

Linux JSONL host: `scripts/source_workbench.py`. Requires Python 3.11+ and a
working ALVA CLI/native build toolchain. No MCP/plugin installation or model
transport is required. This is a local development interface, not a sandbox.
Give a future model agent only the selected arm's advertised tools, not a shell
that bypasses the arm boundary. Use an isolated checkout/container per run.

```bash
python3 scripts/source_workbench.py \
  --project /path/to/isolated/build_system \
  --binary /path/to/alva --arm T+V \
  --out /path/outside/source/native \
  --audit /path/outside/source/new-audit.jsonl \
  --acceptance /path/host-owned/acceptance.py --task W02-1
```

The audit must be new and outside the project; it is not agent-visible input.
It contains actual requests/responses and should remain local/private. `--task`
is optional for existing WF-01 `config_cases.py`. No provider API is called.

One request per line, one JSON answer per line:

```json
{"tool":"tools"}
{"tool":"environment"}
{"tool":"revision"}
{"tool":"search","revision":"<returned SHA>","text":"needs_build"}
{"tool":"read","revision":"<returned SHA>","path":"src/model.alva","start_line":1,"line_count":100}
{"tool":"observe","revision":"<returned SHA>","view":"inspect_function","args":{"name":"build.model.needs_build"}}
{"tool":"edit","revision":"<returned SHA>","path":"src/store.alva","old":"<unique text>","new":"<replacement>"}
{"tool":"check","revision":"<new SHA>"}
{"tool":"build","revision":"<new SHA>"}
{"tool":"test","revision":"<new SHA>"}
```

`ok` means host operation accepted; also inspect nested compiler/view `ok` or
process `returncode`. A successful check is not behavioral acceptance. `test`
requires a successful build at the exact current revision. `tools` provides the
closed schemas. Observation allows only inspect_project/module/function/body
and resolve_entity. No arbitrary AEP passthrough, commit, semantic mutation,
transactional text editing, recovery context, or ledger is exposed.

Reads are paged (default first 100 lines). `start_line` is one-based and must
identify an existing line (or line 1 for an empty file); `line_count` is 1..100.
The model-visible schema and host use these same bounds. Invalid requests name
the rejected argument, the legal range and total line count. Successful pages
return requested and actual ranges, total lines, EOF and the next start line.
Oversized envelopes remain explicitly `truncated`, retain their page metadata
and digest, and never claim omitted content was supplied.

## Source authority and freshness

The same ordinary unique-substring editor is used by T and T+V. Empty `old` is
allowed only for a new file. Edits may target .alva files and alva.toml; tests
remain host-owned. No AIR directory is permitted. Revision covers sorted
relative paths and exact content hashes of project files, excluding .git,
out, target and __pycache__. Symlinks and external manifest module paths are
rejected. Invalid manifest syntax can still be read/edited to repair it.

For each observation the host captures current bytes, imports a temporary copy
using a fresh `alva agent`, executes one allowlisted view, and aborts that same
process's transaction. No index is reused. A second live-source hash comparison
must match before the view is returned. Stale or concurrently changed snapshots
return only an error, never their view. Every successful answer carries its
source revision; it is a fact about that revision, not a promise that source
cannot change after the response. Agents must obtain a fresh revision after an
external edit. A single writer is required; the text editor is not a filesystem
CAS or multi-writer transaction service.

## Accounting and output bounds

Audit records host startup separately. Each call measures wall time, host CPU,
and child CPU, including binary hash check, snapshot copying, import/parsing,
indexing, observation, abort and final revision verification. Response byte
counts are recorded; they are NOT model-token estimates. Oversized results
(over 16 KiB before wrapping) return an explicit bounded preview and digest;
narrow the query rather than silently assuming omitted content was read.
Ordinary text, transactional text and semantic mutation accounting are separate;
the latter two remain zero. Provider tokens/billing require the eventual model
host's real usage ledger; this tool does not invent them.

Run live tests (WF-01 is calibration, not independent treatment evidence):

```bash
ALVA_BIN=/path/to/alva python3 tests/runtime/source_workbench_test.py -v
```
