# Latest development / 最新开发进展

[English homepage](../README.md) · [中文首页](../README.zh-CN.md) · [CLI setup](getting-started.md)

Status checked **9 November 2026**. This page brings recent public work into the
overview; it does **not** merge those implementations into `main` or the release.
Links below pin actual commits, not a promise that a moving branch is stable.

当前发布 CLI 为 `v0.14.1-preview.2`。下列维护能力仍在独立开发分支中；不要只安装发布包后
直接运行这些开发命令。英文复现文档中的命令、平台和依赖要求同样适用于中文读者。

## Guarded maintenance

**Start with the public packing walkthrough**, not a low-level graph-operation
catalogue. It exposes `read_target / prepare_change / publish_change`; the Host
owns the scope policy and tests. The sample rejects malformed and behavior-failing
drafts, accepts a repaired candidate, publishes through the actual Guard, rereads
authority and separately verifies a source-only handoff.

- [Exact consumer Quickstart](https://github.com/zkidp/alva-core/blob/3bddc89f476336170bfa158903d09766fcf91a98/docs/maintenance-consumer-quickstart.md)
- [Public fixture and requirements](https://github.com/zkidp/alva-core/tree/3bddc89f476336170bfa158903d09766fcf91a98/examples/maintenance_packing)
- [PR #43](https://github.com/zkidp/alva-core/pull/43): OPEN at inspection; author-assisted
  real stdio walkthrough and CI, **not external-user validation**.

Use a new directory for this opt-in checkout:

```bash
git clone https://github.com/zkidp/alva-core.git alva-maintenance-preview
cd alva-maintenance-preview
git checkout --detach 3bddc89f476336170bfa158903d09766fcf91a98
```

Then follow that checkout's `docs/maintenance-consumer-quickstart.md`. It needs
Linux/WSL, Python, Rust/Cargo, bubblewrap, prlimit, an available public Cargo
registry cache, and operator-owned scope/tests. It does not call a model API or
update a user's installed plugin. Windows/macOS candidate execution has no
native fallback on this path. It is not a one-command installation for arbitrary
projects.

**交付结果要点：** AIR 发布不会自动重写原 `.alva` 文件。
示例同时提供 `handoff-air/` 与单独投影、重新验证的 `handoff-source/`。
不要只复制仍未改变的原源码，以为它已经包含修改。两个状态不构成联合原子写入。

## What recent verification established

| Public work | Actual evidence | What it does not establish |
| --- | --- | --- |
| [Engineering baseline / PR #42](https://github.com/zkidp/alva-core/blob/29c473165f74c8ee16c1a8d22182025e104c1d9f/docs/maintenance-engineering-baseline.md) | Stable three-action starting point and opt-in bounded dependency context | Context economy or a new default tool surface |
| [Consumer walkthrough / PR #43](https://github.com/zkidp/alva-core/pull/43) | Actual stdio calls, rejected drafts, repaired publication, fresh read and tested handoff | Independent usability or model correctness gains |
| [Git baseline feasibility / PR #44](https://github.com/zkidp/alva-core/blob/e0f160f4307ae6fa66733b350b63f081af712168/docs/research/guarded-publication-feasibility.md) | One public fixture, six deterministic paired scenarios; strong Git/tests and ALVA made the same publication decisions | System-wide equivalence, novelty, cost savings or Agent superiority |

PR #44 is OPEN at inspection. It uses real immutable Git objects and old-ref
checks, not a deliberately weak text baseline. No additional safety decision
was observed in that fixture. It did not execute a CodeStruct/Serena arm or a
new model study. A non-author walkthrough remains **NOT_EXECUTED**.

这些是有限工程证据，不是“ALVA 比常规工具更安全/更正确”的通用结论。
目前继续收集真实使用障碍，比扩大能力清单更重要。

## Other opt-in work

These are separate development paths, not bundled features of the released CLI:

| Work | Pinned entry | Boundary |
| --- | --- | --- |
| Python Guard + optional Codex workflow | [Quickstart](https://github.com/zkidp/alva-core/blob/7168a2346b9f3656e0f8d68fbee294d525a292a0/docs/python-guard-codex-quickstart.md) | Source remains authoritative; isolated candidate workspace and patch evidence; trusted-local execution is not a malicious-code sandbox |
| JSON Pointer / JSON Patch component | [Component README](https://github.com/zkidp/alva-core/blob/be979e4947688117022e839377600bbfb603a5c8/examples/json_patch_component/README.md) and [usage envelope](https://github.com/zkidp/alva-core/blob/be979e4947688117022e839377600bbfb603a5c8/docs/json-patch-usage-envelope.md) | Native component prototype, bounded driver and supported numeric/operation limits; not an unrestricted RFC or decimal guarantee |

Do not combine these branches by copying files into a release installation.
Read each path's exact configuration and support limits; they are not a unified
stable distribution. No language migration, general Python AIR or automatic
production deployment is implied.

## Evidence and feedback

Engineering success, model task completion and behavioral correctness are
different observations. Check/commit success is not a substitute for independent
task and regression tests. The project's historical negative and inconclusive
findings remain valid; this overview does not rescore them or turn private
materials into public claims.

For hands-on feedback, use a disposable public project and tell us where setup,
diagnostics, recovery or final handoff was unclear. Share only redacted details
through [Issues](https://github.com/zkidp/alva-core/issues). No paid model run is
required to reproduce the public consumer walkthrough.
