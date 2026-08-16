# FORMAL-72 — Held-out confirmatory dataset

72 runs: **12 held-out tasks (h01–h12) × 2 arms × 3 replicates**.

The two arms are `OFF` (baseline editing mode) and `ON` (structured-AEP editing
mode). Each run is an autonomous agent attempting a real software-change task
in the Alva project; `hidden_verifier` records whether the final state passed
the held-out verifier.

## Layout

```text
formal72/
  metas/     one meta.json per run: hXX/{on,off}/run-{1,2,3}/meta.json
  sessions/  one session.jsonl per run, same layout (full agent transcript)
  logs/      runner logs + checkpoint
  SHA256SUMS.txt   sha256 over every published file (freeze)
  README.md
```

## meta.json schema

| field | meaning |
|---|---|
| `task`, `arm`, `run` | run identity (h01–h12, on/off, 1–3) |
| `harness_version` | experiment harness version (`v0.2` h01–h04, `v0.3` h05–h12) |
| `started_at`, `completed_at` | run window (UTC) |
| `wall_clock_s` | wall time in seconds (cap 3600) |
| `timeout` | whether the 60-minute cap was hit |
| `agent_exit` | `0` or `"timeout"` |
| `hidden_verifier` | held-out verifier outcome (`true`/`false`) |
| `qualification_status` | `"VALID"` for every published run |
| `build_ok` | whether the project build succeeded after the edit |
| `final_air_hash` | content hash of the final AIR state |
| `gates`, `workspace_prep` | pre-run hygiene checks (leak/access probes) |
| `binary_sha256`, `image_digest`, `prompt_sha256`, `task_hashes`, `docs` | provenance hashes |
| `session` | absolute path to the session file on the experiment host |

## session.jsonl format

Each `session.jsonl` starts with **8 probe lines** produced by the container
security gate (`PASS: /host-secrets/marker not readable`, …) — those lines are
not JSON. Everything after line 8 is one JSON object per line (Codex
transcript: thread/turn/item events).

## Integrity audit (2026-08-16)

- 72/72 `meta.json` present, valid JSON, required fields complete
- h05–h12 (48 runs): runner-log ↔ meta cross-check **48/48 consistent**
  (verifier result, `wall_clock_s` ±1s, exit/timeout)
- sessions: 40,796 JSON lines checked, **0 malformed** (after the 8-line header)
- `verify.log`: none empty (verify.log and workspaces are kept with the raw
  data on the experiment host and are not part of this public export)

## Raw results (no analysis)

| task | arm | run | verifier | wall_min |
|---|---|---|---|---|
| h01 | OFF | 1 | F | 22 |
| h01 | OFF | 2 | F | 25 |
| h01 | OFF | 3 | F | 28 |
| h01 | ON | 1 | F | 28 |
| h01 | ON | 2 | F | 29 |
| h01 | ON | 3 | F | 23 |
| h02 | OFF | 1 | F | 14 |
| h02 | OFF | 2 | F | 16 |
| h02 | OFF | 3 | F | 21 |
| h02 | ON | 1 | F | 25 |
| h02 | ON | 2 | F | 16 |
| h02 | ON | 3 | F | 60 |
| h03 | OFF | 1 | F | 2 |
| h03 | OFF | 2 | F | 3 |
| h03 | OFF | 3 | F | 1 |
| h03 | ON | 1 | F | 1 |
| h03 | ON | 2 | F | 2 |
| h03 | ON | 3 | F | 2 |
| h04 | OFF | 1 | F | 60 |
| h04 | OFF | 2 | F | 60 |
| h04 | OFF | 3 | F | 44 |
| h04 | ON | 1 | F | 53 |
| h04 | ON | 2 | F | 60 |
| h04 | ON | 3 | F | 60 |
| h05 | OFF | 1 | T | 27 |
| h05 | OFF | 2 | T | 9 |
| h05 | OFF | 3 | T | 18 |
| h05 | ON | 1 | F | 60 |
| h05 | ON | 2 | F | 60 |
| h05 | ON | 3 | T | 11 |
| h06 | OFF | 1 | F | 9 |
| h06 | OFF | 2 | F | 16 |
| h06 | OFF | 3 | F | 14 |
| h06 | ON | 1 | F | 19 |
| h06 | ON | 2 | F | 10 |
| h06 | ON | 3 | F | 35 |
| h07 | OFF | 1 | F | 38 |
| h07 | OFF | 2 | F | 60 |
| h07 | OFF | 3 | F | 60 |
| h07 | ON | 1 | F | 60 |
| h07 | ON | 2 | F | 28 |
| h07 | ON | 3 | F | 38 |
| h08 | OFF | 1 | F | 60 |
| h08 | OFF | 2 | F | 60 |
| h08 | OFF | 3 | T | 45 |
| h08 | ON | 1 | T | 56 |
| h08 | ON | 2 | F | 60 |
| h08 | ON | 3 | F | 36 |
| h09 | OFF | 1 | F | 33 |
| h09 | OFF | 2 | F | 60 |
| h09 | OFF | 3 | F | 18 |
| h09 | ON | 1 | F | 60 |
| h09 | ON | 2 | F | 60 |
| h09 | ON | 3 | F | 16 |
| h10 | OFF | 1 | T | 41 |
| h10 | OFF | 2 | T | 16 |
| h10 | OFF | 3 | T | 11 |
| h10 | ON | 1 | F | 60 |
| h10 | ON | 2 | F | 24 |
| h10 | ON | 3 | T | 6 |
| h11 | OFF | 1 | T | 48 |
| h11 | OFF | 2 | T | 34 |
| h11 | OFF | 3 | F | 60 |
| h11 | ON | 1 | F | 60 |
| h11 | ON | 2 | F | 60 |
| h11 | ON | 3 | T | 23 |
| h12 | OFF | 1 | T | 8 |
| h12 | OFF | 2 | F | 12 |
| h12 | OFF | 3 | T | 24 |
| h12 | ON | 1 | T | 27 |
| h12 | ON | 2 | F | 26 |
| h12 | ON | 3 | F | 27 |

## Provenance notes

- h01/h02 and h05–h12 come from the main formal batch; h03/h04 come from the
  fixed-verifier replacement batch. Earlier defect-polluted h03/h04 runs are
  excluded from this dataset (raw copies are preserved on the experiment host).
- Timeout runs (60 min, `agent_exit="timeout"`) are valid observations by
  protocol and are included.
- `SHA256SUMS.txt` freezes this exact export; full raw data (workspaces,
  `verify.log`, task assets) remains on the experiment host.
