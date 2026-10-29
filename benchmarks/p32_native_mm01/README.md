# P32 — one fresh MM01 Native Semantic slot

Base: `c9aecd0bfbbc6b7444d50bf85ca1558ae969d3db` (P31).
This is a prospective S-only developmental feasibility run, not a clean paired
comparison with historical P30-T. No Core/MCP/AEP/Skill changes.

`pilot.py` reuses P30's source bundle, public input, complete official Skill and
references, dynamic workbench, exact 20 Native MCP schemas, observer, Linux
service and independent evaluator. It adds only a prospective entry point using
P31's strict, trusted per-tool commit approval. Global `never`, default `auto`,
read-only Host, disabled shell/web/delegation and P22/P23 OS isolation remain.
Only `alva.commit_transaction` has an explicit approval override. The actual
AppServer-parsed configuration and destructive annotation are checked before
any real model turn. There is no Host rescue commit.

Preparation uses the existing P31 standalone synthetic Responses test to
exercise the **model-tool approval path**, without provider generation, then
checks the actual P32 Host's policy, all 20 schemas, Skill discovery and original
baseline. It does not perform an MM01 engineering solution. The original
baseline must compile, pass regressions and fail the new task requirement.

```text
python -m unittest benchmarks.p32_native_mm01.test_pilot -v
python benchmarks/p32_native_mm01/pilot.py prepare --attempt preflight-01 --alva <approved-Linux-ELF> --toolchain <Linux-sysroot> --registry <public-registry>
# Commit and push FREEZE.json/PREFLIGHT.json plus code before proceeding.
python benchmarks/p32_native_mm01/pilot.py run --attempt execution-01 --alva <same-ELF> --toolchain <same-sysroot> --registry <same-registry>
```

Windows trusted AppServer orchestration + Ubuntu-26.04 WSL is the tested host;
candidate compilation/execution remains Linux-only inside OS namespaces.
Runtime input byte provenance is explicit: original P30 Git-blob input/docs,
current exact executing runtime bytes embedded in the freeze, versioned SDK
identity and CLI executable hash. CI materializes exactly those bytes; it does
not accept arbitrary CRLF/LF alternatives. Runtime-specific ready paths are
fresh lifecycle endpoints, not a treatment variable.

One fresh S slot, `gpt-5.6-sol / low`, 80 model tools, 480 active-turn seconds,
600000 cumulative reported tokens observation threshold, 20-second interrupt
grace. The latter is not a provider hard cap or unique context size. Cached
tokens are not subtracted. Request counts/dollar costs unavailable from this
transport are null, not zero. No retries/replacements/additional slots.
A study-wide exclusive ledger prevents restarting under another attempt name.

Separate outcomes: staged target change; transaction check; actual AppServer to
MCP commit delivery (matched call IDs); changed AIR publication; fresh-process
authority read; independent task/regression/scope; final terminal and resources.
Only their appropriate conjunction can establish correct maintenance. Source
projection need not change after AIR publication. `check`/commit alone are not
independent behavioral truth. P30/P31 records remain unchanged.

Raw requests/events, candidate sources/AIR and evaluator output remain in the
controlled `.local/p32-native-mm01/` archive, not public Git. Credentials are
never read, copied, printed, hashed or archived: the existing authenticated CLI
consumes its own auth through the inherited temporary hardlink mechanism. The
raw archive excludes the model working directory and temporary CLI home.
Public Git contains normative input freezes, code and derived summaries only.
No model execution is performed by CI.
