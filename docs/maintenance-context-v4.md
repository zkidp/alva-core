# Compact maintenance context

Opt-in server:

```sh
python -m integrations.codex.maintenance_context --config /absolute/trusted-host.json
```

Use the same trusted project/SDK/assertions/policy configuration as
[Maintenance Host](maintenance-host-v2.md). The existing three-tool server and
20/9-tool Native profiles are unchanged. This entry advertises the same three
mutation actions plus read_reference and read_source. Its initialization
instructions contain the dedicated `integrations/skills/alva-host/SKILL.md`;
clients that install Skills can load that profile directly. Full general
Native references remain available without being mandatory preparation steps.

read_reference accepts a closed document name and section ID. `index` lists
sections; `all` retains full-document access. The small language guide contains
generic forms tested with the actual compiler, not task solutions. Source
reads are restricted to configured public source paths, at most 120 lines and
16 KiB per result, and preserve exact line endings. Continuation/EOF and the
source digest are explicit. A too-long single line is rejected, not truncated.
AIR files and arbitrary filesystem paths are not readable through this tool.

Native read_source results are import projections, not staged semantic
authority. Continue editing the body returned by read_target. Mutation,
proposal invalidation, scope authorization, isolated tests, publication and
fresh verification delegate to the existing Host. New read tools neither
authorize changes nor accept evaluator paths or test assertions.

Qualification found an existing code-generation omission for Result-valued
match/reference tails. The common generator now tracks direct Result parameter
and lexical let bindings, including shadowing, and recognizes match branches.
This preserves ordinary implicit Ok wrapping while preventing double wrapping
of existing Result values. Source and authoritative AIR execution tests cover
pass-through, local binding, match branches and shadowing. This is not a full
type-soundness claim or a change to scope authorization.

Engineering tests establish bounds, exact source reconstruction, full reference
availability and actual protected publication. Real model savings require the
separately frozen [prospective acceptance](../benchmarks/context_v4/PROTOCOL.md).
Do not infer provider tokens or dollar savings from shorter documentation alone.
