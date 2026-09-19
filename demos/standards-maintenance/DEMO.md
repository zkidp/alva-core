# 3–5 minute operation script (not a recording)

Prepare two actual release binaries by running the source-mode reproduction
ahead of the presentation; compiling them is not assumed to fit in four minutes.
Keep its printed artifact directory and RESULTS.json available. On Windows,
PowerShell can invoke the same Python commands; substitute the printed `.exe`
paths. This document is an operation script; no video has been produced.

**0:00–0:40 — requirement.** Show REQUIREMENT.md and the links to RFC 6901 §6
and JSON Schema's media-type rule. Explain that this is new explicit support,
not an old bug, a benchmark, a schema validator or external adoption.

**0:40–1:15 — before.** Show the baseline's actual recorded command/input/exit
for `schema-def`: `mode: fragment`, pointer `#/$defs/name`. Show empty stdout,
exit 1 and its unsupported-mode diagnostic. Existing JSON-string Pointer is
still supported. Do not describe an unrun command as live output.

**1:15–2:00 — change.** Show `parse_fragment` in `pointer.alva`, the explicit
`resolve_fragment` entry, and native mode dispatch. Point out one decoding layer,
strict UTF-8 and unchanged Patch `path`/`from`. Explain the generic stdlib
conversion primitive, not a third-party Pointer implementation.

**2:00–3:10 — actual after acceptance.** Run the binary-only mode with the
previously built paths:

```sh
python demos/standards-maintenance/reproduce.py --before-binary OLD_RELEASE --after-binary NEW_RELEASE
```

Show the new schema selection result, percent/UTF-8 rejection cases, old
regression counts, and four separately disabled upstream tests. Binary-only
mode intentionally does not claim a new source build or source-consumer run.

**3:10–3:45 — independent source consumer.** Open the source-mode result's
consumer manifest outside Core: its path dependency points to the same ALVA
library; there is no vendor or preparer. Show the recorded check/build/release
commands from a different cwd and result `{"minimum":9007199254740993.0}`.
Optionally rerun that exact retained consumer using its saved input.

**3:45–4:30 — boundaries and cost.** Show environment-specific RESULTS.json,
artifact hashes and command wait times. Distinguish target-owned Linux from
GitHub-hosted Linux and Windows. Human active time/token costs are missing unless
actually measured. No superiority claim, controlled study, deployment, release,
external-user endorsement or AIR/AEP local-library editing is demonstrated.
