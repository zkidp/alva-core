# MIC-01 cost diagnosis, before MIC-02

8 November 2026. Read-only analysis of the retained 24-slot archive. Archive
SHA256 matches the previously committed manifest; every record and Linux log
matches its recorded digest. No model generation or token-counting API was used.
The old study remains INCONCLUSIVE_PROVIDER_LIMIT, with its CLI-identity
limitation. This diagnosis does not repair or rescore it.

## Matched observations

Use the eight pairs where both conditions completed correctly. These are the
same known-task observations used in the original report, not a new sample.

| Per-slot median, eight matched successes per condition | Text | Old Native |
| --- | ---: | ---: |
| Cumulative reported total tokens | 157,012.5 | 459,289 |
| Completed model tool calls | 12 | 30.5 |
| Explicit textual tool replies, UTF-8 bytes | 20,981 | 33,701.5 |
| Tool errors | 1 | 2 |

The token median ratio is approximately 2.93; the call median ratio is 2.54;
the text-reply median ratio is 1.61. These different ratios do not establish a
causal decomposition. In particular, a 2.93 token ratio is not a dollar ratio.
Reported totals include cached input. Both eligible arms' input tokens are
over 99% of their reported totals, but those arm sums have unequal denominators
and are not used to estimate an arm effect.

| All calls within the same eight matched successes | Text calls | Native calls | Text / Native reply bytes |
| --- | ---: | ---: | ---: |
| Documentation | 18 | 20 | 104,980 / 126,407 |
| Source reads/search | 19 | 21 | 53,755 / 61,925 |
| Navigation/discovery | 8 | 67 | 1,208 / 38,338 |
| Graph inspection | 0 | 15 | 0 / 38,087 |
| Node construction | 0 | 47 | 0 / 4,004 |
| Native node mutation | 0 | 9 | 0 / 747 |
| Source edit/write requests | 9 | 7 | 1,114 / 259 |
| Checks/tests | 28 | 25 | 2,628 / 1,612 |
| Preview/diff | 9 | 19 | 7,614 / 3,478 |
| Native begin/commit/abort | 0 | 16 | 0 / 1,776 |
| Finish | 8 | 8 | 144 / 144 |
| Total | 99 | 254 | 171,443 / 276,777 |

All seven Native source-edit requests in this matched subset were rejected as
unsupported. The full archive contains nine such requests. The Native model
nevertheless recovered in these eight successful pairs. Source writes in N are
not credited as successful mutation, and neither rejected requests nor calls
after an error automatically mean avoidable work.

The full archive also contains eleven EXPECTED_EMPTY_ARGUMENTS and two
INVALID_TOOL_ARGUMENTS study responses. T's matched successes include ten
tool errors, all on check/test calls; N's include twelve errors across check,
preview and rejected source writes. These are tool/protocol errors, not counts
of failed behavioral tests. The common serialized-JSON workbench contract is
a concrete source of friction in both conditions.

The 20-tool Native schema list occupies 12,643 canonical JSON UTF-8 bytes in
the retained logs. This is its logged schema representation, not a tokenizer
measurement or proof that this exact payload was sent repeatedly to the model.
Startup tools/list responses are not counted as model tool calls.

## Engineering priorities supported by these observations

1. **Use declaration-level mutation.** Navigation plus construction accounts
   for 114 of 254 Native calls in matched successes. The new read/body-replace
   prototype directly addresses this interaction burden. Whether the model
   actually takes that shorter route still needs a fresh experiment.
2. **Make arm exposure and arguments explicit.** Hide source-write tools from
   N and expose separate typed study tools in both arms. Empty-argument checks
   become ordinary empty-object calls, with no nested JSON string. This is a
   common workbench repair, not a Native-only benefit.
3. **Keep feedback compact and authoritative.** Read a target body once,
   return exact revisions, and avoid repeating it in declaration context.
   Full-body writes may still cost more than small Text patches. Do not add a
   smaller expression editor until new traces show that full-body cost is the
   remaining bottleneck.
4. **Measure visible and backend work separately.** Guard inspection is not
   free merely because it is hidden from the model. Future logging must label
   model, trusted inspection, evaluator and finalization calls independently.

The existing documents are a substantial shared payload. Both conditions
should retain equal access to the same full documentation; shortening only
Native's docs would introduce another treatment. The new profile guide is
available to both and does not contain engineering solutions or trajectories.

## Measurement boundary and reproduction

`COST-PROFILE.json` contains per-slot categories, tool counts, usage, backend
log counts and raw-record bindings. No transcript text is published. Category
tokens, actual provider request count and dollar cost remain null.

The analyzer reads unique item/completed events. It handles MCP `text` and
AppServer `inputText`/`outputText`, ignores duplicate terminal events, and
reports missing terminal items without inventing results. Explicit text is
counted once; separately serialized replies may also contain structuredContent
and metadata. The adapter's actual prompt representation is unknown. Repeated
reply bytes are exact repeats within a slot, not measured possible savings.

Historical backend logs are partial execution evidence, not a complete Host
cost trace. Usage cannot be allocated exactly to individual operations or
documents. Compaction, caching and unobserved provider behavior prevent a
causal token attribution from this archive. Survivor selection, quota faults,
familiar tasks and CLI uncertainty remain material limitations.

With the controlled original archive:

```sh
python -m benchmarks.compact_maintenance.cost_profile /path/to/MODEL-RAW.zip \
  --output out/mic02-cost-reproduction.json
python -m unittest benchmarks.compact_maintenance.test_study -v
```

Compare the reproduced JSON bytes with the committed summary. CI tests the
analyzer's normalization/accounting and summary bindings using synthetic cases
and committed digests; CI does not claim to possess or replay the private raw
archive.
