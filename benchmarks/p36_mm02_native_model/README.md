# P36 — MM02 Native autonomous maintenance pilot

Canonical base: `88cb64c9a9361c00f061bb1da2043d55315f8235`.
One fresh `gpt-5.6-sol / low` Native-only model turn is authorized. This study
reuses the original P29 MM02 source-only bundle, original public requirement,
original hidden goal/regression assertions and current complete official Skill.
It uses P32's controller/workbench and P31's scoped approval configuration,
with the actual unchanged P34 Guard on every Native session.

Only `store.xml.parse_prefix` body edits are authorized. No engineering witness,
prior results, historical candidate, shared-node hint or experimental execution
instructions are passed to the model. Only public input and official Skill/docs
are installed in its fresh working directory. The source project is supplied
only to the Linux sandbox; the trusted research checkout, evaluators, SSH key,
endpoint, service socket and raw records are outside candidate mounts.

The trusted Windows AppServer connects over SSH to a dedicated Linux service
directory. This changes transport from WSL; the original P22/P23 execution
backend, mounts, resource limits and fail-closed behavior remain unchanged.
The trusted service starts in an outer **unprivileged** `unshare -Ur` namespace
so the shared login account's unrelated threads do not consume the existing
128-process per-UID limit. No unrelated process is stopped, no process limit is
raised, and no host/root privilege is granted to the candidate.

The original source compiles and passes regressions but fails the new task
before generation. The actual P36 parsed strict Host configuration, single
20-tool server, complete Skill discovery and real Guard baseline are checked
without a model turn. P31/P34's prior synthetic approval-route evidence is
reused; no historical engineering answer or candidate is executed in preflight.

`prepare` freezes actual task/prompt/instructions, docs, tool schemas, policy,
Host configuration, actual runtime bytes, evaluator, identities, resources,
classification rules and unique schedule. Commit and push that freeze with a
clean worktree before `run`. An exclusive study-wide ledger is created before
the only model slot. No slot retry, replacement, follow-up turn, recovery by
the Host, new Text slot or later experiment is supported.

```text
python benchmarks/p36_mm02_native_model/pilot.py prepare --connection <private-local-connection.json> --attempt <fresh-preflight-id> --alva <Linux-ELF> --toolchain <Linux-Rust-sysroot> --registry <public-registry>
# Commit and push the actual freeze; verify origin equality and clean worktree.
python benchmarks/p36_mm02_native_model/pilot.py run --connection <same-private-connection.json> --attempt <unique-execution-id> --alva <same-ELF> --toolchain <same-sysroot> --registry <same-registry>
python benchmarks/p36_mm02_native_model/validate.py
```

The connection file is local machine configuration, excluded from Git and the
study archive. SSH credentials are handled only by SSH, never read/hash-copied
by the runtime. The AppServer alone consumes existing authentication via P32's
temporary hardlink mechanism; that temporary CLI home is not archived or mounted
into the candidate. Remote setup and controlled evidence use separate paths.

Limits: 80 model tool calls, 480 active-turn seconds, 600,000 cumulative reported
tokens observed, 20-second interrupt grace, concurrency one. Cached input is
retained in reported total. Provider request counts/dollar cost are null when
unavailable; no provider hard token cap is claimed. Same-turn autonomous
abort/rebegin or correction remains permitted within those fixed limits.

`analyze.py` recomputes per-attempt AppServer/Guard/Native call linkage, scope,
commit publication, independent final behavior and resource/terminal outcome.
Private observers read all nine staged body revisions and never alter feedback.
Raw requests/results, candidate source/AIR, Guard reads and independent evaluator
logs remain in the controlled local archive. Public JSON contains derived data
and hashes only. `validate.py` materializes exact frozen runtime bytes and runs
five attribution regressions on Linux/Windows, without executing any model.

P20–P35 frozen evidence, Core/AEP/MCP and official Skill are unchanged. This is
one S-only developmental observation, never pooled with historical Text or
credited with an engineering witness. A safe Guard denial alone is unfinished
maintenance. Final results, archive identity and interpretation are delivered
after the unique formal slot. STOP after the independent PR; no auto-merge.
