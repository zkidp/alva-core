# Flash continuation: completed remaining cells, no observed economy benefit

## Status and preserved history

The user authorized connectivity retest and continuation. The first continuation
stopped at Q01-B with a captured DNS error. After a separately frozen scoped
transport workaround, all seven still-unstarted cells completed publication and
independent task/regression/scope evaluation. There were no slot retries,
replacements, task changes, additional tasks or budget increases.

The original Q01-A HOLD and second Q01-B HOLD remain unchanged. Therefore the
original nine-slot primary comparison is **incomplete**. Seven completed cells
all passed, but this is not a clean nine-session success-rate sample or evidence
that one information interface improved correctness. At most two complete task
triples are descriptively comparable. These are tiny Codex-authored fixtures,
not real external repository tasks or independent holdouts.

## Transport attribution and actual repair

The second failure's exception chain was
`ProviderFault -> URLError -> gaierror(errno=11001)` before any response. A
separate no-model OS resolution call also failed. Git push independently reported
`Could not resolve host: github.com`. This supports an execution-host DNS problem;
it does not retroactively prove the first Q01-A URLError had the same cause.

DNS/TLS/root HTTPS checks and a repeated two-request toy canary initially passed,
then Q01-B failed on its first submitted request. Current connectivity probes
alone did not guarantee stable repeated resolution. Q01-B was not retried.

An explicit public DNS query against1.1.1.1 returned a public A address after
timeouts. A process-local TCP route to that answer retained the actual API URL,
Host header, SNI, normal certificate verification and hostname verification. No
system DNS, global Git config, adapter, proxy, firewall or CA configuration was
changed. Three no-credential HTTPS probes and a two-request toy canary then passed.
The route was limited to300 seconds, with no silent refresh/retry; foreign
origins, redirects, nonpublic addresses and proxy environments fail closed.
Credentials stayed in the Windows controller and were not archived or sent to
DNS, Linux or model tools. This is an experimental local workaround, **not a
permanent system-DNS repair or production network library**.

DNS-CONTINUATION-FREEZE.json was pushed at
`01f19776953d33f436606f5d04d860e7c98c6930` before any of the final seven model
requests. Earlier continuation freeze:
`16bda21ebafddd8bab19aec2f49a00d7fbad1e36`. Original freeze:
`1fac9d9c10f2bb2c17db11bb4be59b4aff757886`.
The original task inputs, initial request hashes, model/thinking, shared tools,
references, mutation/Guard/evaluation paths and budgets were unchanged. The new
connection route is an explicit infrastructure amendment, common to every
remaining cell; it is not claimed to be identical infrastructure to earlier waves.

GitHub DNS failed too. Freeze/results pushes used Git's supported command-scoped
`http.curloptResolve` with a current public DNS answer and ordinary HTTPS
certificate verification. No permanent Git configuration or insecure TLS flag.

## Per-task observations

A=source acquisition; B=ordinary ContextHost; C=P42 bounded context. All use the
same protected body replacement/publication and independent final tests. A has
paging/search/symbol catalog, not a complete IDE/LSP tool suite.

| Task | A total tokens | B total tokens | C total tokens | Final evaluated behavior |
| --- | ---: | ---: | ---: | --- |
| Q01 | Censored: original transport HOLD | Censored: DNS HOLD |16,696| C PASS; no eligible comparison |
| Q02 |18,199|15,377|32,858| All three PASS |
| Q03 |9,878|11,220|16,783| All three PASS |

Both comparable C/A token ratios are unfavorable: Q02=1.8055 (+80.55%),
Q03=1.6990 (+69.90%). Their descriptive median is1.7523; this is **not a formal
effect or a completed primary screen**. C/B is2.1368 for Q02 and1.4958 for Q03.
No significance test or superiority claim. All attempts remain recorded.

| Task | A raw source bytes | B raw source bytes | C raw source bytes |
| --- | ---: | ---: | ---: |
| Q02 |817|479|632|
| Q03 |0|191|176|

Unique and total raw delivery are equal here (no duplicate raw bytes). Target
body/context representations are separate, not raw source. Provider totals include
those representations and all repeated schema/docs/reasoning; cached input is not
subtracted. Q02 C read fewer raw bytes than A but more than B; Q03 A needed no
read_source/search delivery, while C read176 bytes. There is no consistent raw
exposure advantage across these tasks. A's zero is not zero program information:
it still received the public requirement and current target body/declaration.

First accepted change occurred at request7/5/4 for Q02 C/A/B and4/3/3 for Q03
C/A/B. Q02 requests totaled8/6/5; Q03 totaled5/4/4. C did not reach accepted
change earlier in either complete triple. These observable sequences cannot
identify model psychology or uniquely attribute the extra cost to projection
text. Extra rounds, source/reference choices and repeated input all contribute
to the recorded footprint; no causal component decomposition was performed.

## Completion and accounting

Final seven cells:37 submitted and received generation requests,56 model tool
calls,121,011 provider-reported tokens. All seven returned PUBLISHED with fresh
authority verification, independent task PASS, regression PASS, authorized scope
and unchanged original sources. The same isolated evaluator/Host as the original
freeze was used. No models were asked to judge their own correctness.

Earlier waves remain separate: Q01-A four submissions/three responses (7,762
known received tokens), Q01-B one submission/no response (usage UNKNOWN). Thus
42 scientific HTTP attempts were submitted across the original roster,40 returned
responses; **complete overall scientific token cost remains UNKNOWN**. Do not
count the two missing attempts as zero. Six non-scientific toy-canary requests
across preparation/retest/routing cost748+752+748=2,248 known tokens, separately.

Raw requests/responses, tool records, frozen inputs and exact runtime bytes are
in three separate local archives. Public manifests retain their hashes; no raw
provider text/reasoning/credential is in Git. Final routed-wave archive:
`c9716ad6781ee01854eaa5c1c1e46ed7eebc713b5a18f08a46abe177069bb89e`
(295 entries,839,168 bytes). Full final AIR files are not retained by the reused
Session before temp cleanup; candidate body calls and fresh authority/evaluation
digests/receipts are retained. No replacement trajectory or AIR file was invented.

## Bounded decision

The continuation establishes runnable agent maintenance through the existing
Host, and demonstrates the temporary DNS workaround for this execution. It does
**not** establish P42 acquisition economy. On the two complete tiny tasks, C
preserved correctness but cost more and did not produce earlier accepted action.
Do not promote bounded context to default or infer arbitrary-program or language
superiority/inferiority. Keep ordinary source/ContextHost fallback available.

The research question remains open beyond these small, known-target authored
fixtures; the present data do not justify automatically adding cases, larger
tasks, new features or more paid runs to seek a favorable result. No Core, AEP,
MCP, Skill, old study, paper or published release was modified. Stop after this
delivery; any future study needs a separate decision.
