# JSON component maintenance evaluation — design only

No provider-backed or human-subject comparison is authorized in this node. This document separates completed development cases from any future evaluation.

## Question

For one concrete, externally sourced JSON-component maintenance requirement, does the ALVA implementation/toolchain reduce the cost of completing and validating the change relative to a reasonable conventional Rust implementation while preserving task and regression correctness?

This is an implementation-stack comparison. It does not isolate ALVA syntax, semantic tools, or compiler mechanisms. The runtime-performance reference is not automatically a valid maintenance baseline.

## Comparability requirements

- The requirement and public contract must genuinely apply to both starting implementations.
- Each starting version must satisfy the same pre-change behavior and regressions.
- Both arms may modify the code that owns the behavior and may use normal ecosystem dependencies.
- A requirement already satisfied by one stack is recorded as no modification required; functionality is not removed to manufacture symmetry.
- Tasks already solved or whose complete repair has been inspected in this development line are development cases, not unseen evaluation tasks.

## Before any future execution

The user must explicitly approve and freeze:

- task list, traceable source, starting commits, and allowed files;
- shared public requirements/tests and independent host-owned acceptance;
- exact ALVA and Rust arm definitions;
- exact model/provider/configuration, if an agent comparison is requested;
- per-session wall, generation-request, tool, token, and monetary limits, including currency;
- total experiment budget and run order;
- failure, retry, missing-result, and infrastructure-incident handling;
- any human participants and how active time is recorded.

No credentials are needed or read by the offline runner.

## Outcomes

Primary per task: requirement correctness, regression correctness, and need for extra human correction. Secondary: recorded human active time when actually observed, agent elapsed time, build/test wait, tool calls, provider-reported tokens, rework count, and final acceptance. Every attempt remains in cost accounting. Tool calls are not independent statistical samples.

With only a few genuine requirements, report task-level case comparisons rather than significance claims. Missing human time remains missing; agent tokens do not proxy for human labor.

## Offline runner

`mock_runner.py` validates result ingestion for completion, task failure, budget exhaustion, expected tool error, provider/infrastructure failure, and missing result. It emits no model request and proves only that bookkeeping is executable.
