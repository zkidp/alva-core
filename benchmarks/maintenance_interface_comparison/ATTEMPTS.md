# Preparation attempts (before generation)

1. SSH login as zip failed; user clarified zeke. Original pinned server host
   key matched. Authentication was established without saving the password.
2. Six-case zero-model preflight wave 01 failed before Native initialization:
   MCP_EXIT_BEFORE_RESPONSE. A direct isolated probe exposed actual bwrap
   stderr: `Creating new namespace failed: Resource temporarily unavailable`.
3. Host diagnostic showed 139 threads for the execution UID versus the old
   per-UID RLIMIT_NPROC=128. Other services were left untouched. New experiment
   uses an explicit fixed 512 per-UID profile in both arms. The original
   sandbox/persistence sources and historical freezes are not edited. CPU,
   address space, mount/network isolation and other limits are unchanged.
   This is not a 128-process per-candidate bound, nor a CPU-isolated timing
   benchmark on a dedicated host. Shared-host timing is a limitation.
4. Real owned-service probes 01–03, still zero-model, exposed a second issue:
   the outer PID namespace retained host procfs, and nested bwrap reported
   `open /proc/7/ns/ns failed`. A new-run owner adapter mounts private procfs
   in a private mount namespace before launching the service. The existing
   P36 owner and its pidfd/tombstone cleanup stay byte-identical. Direct
   sandbox preflight alone did not cover this nested-process launch path.
5. Probe 04's first procfs adapter mounted too early and invalidated the
   original owner's host-PID handshake. Corrected it to remount only after
   the pinned identity handshake, before service exec. Probe 05 then exposed
   AF_UNIX's path-length limit. Probe 06's private-tmpfs attempt made IPC
   unreachable from the trusted SSH relay; that attempt was removed. The
   final adapter uses a short unique host IPC socket, outside candidate mounts,
   and removes exactly that socket after confirmed owner cleanup.
6. Probe 07's source route passed but the synthetic Native host call used
   `name` instead of the current `tool` field. Fixed the no-model probe schema;
   the actual model tool schema and registered conditions are unchanged.

Original wave 01 JSON and direct diagnostics are retained in controlled local
preparation evidence. Model generations so far: zero. These failures do not
consume model slots and are not ordinary model task failures. Runtime and
profile hashes must be frozen after preflight and before the first turn.

## Model wave 01 and post-run limitations

The paragraph above describes preparation only. Wave 01 submitted 24 turn
requests: 21 ordinary outcomes (17 correct completions, four token observation
interruptions), then three usageLimitExceeded outcomes. Slot 22 had already
made 32 tools when quota ended its turn. Slots 23/24 made zero tools and have
no reported usage. Upstream provider request count and dollars are unknown.

**Protocol deviation:** the reused controller accepted terminal `failed` as an
ordinary terminal status and the batch did not classify the common provider
failure. It wrongly submitted two further scheduled requests after the first
quota error. Preserve them; no replacement, extra turn, changed prompt,
alternative account or later automatic resume. The primary disposition is
INCONCLUSIVE_PROVIDER_LIMIT, not a clean 24-slot efficacy result.

Post-run analysis adds provider_gate.py, its tests and safe_run.py. These are
prospective repairs, NOT bytes used in wave 01. The safe entry refuses the old
freeze before accessing a connection or generating a turn. A future separately
authorized freeze must bind the repaired gate; it must not reuse this ledger.

**Additional executable identity limitation:** the initial CLI hash matched the
freeze. After the batch, the default resolver points to a different binary hash
with the same 0.167.0-alpha.3.2 version string; the original cache path is gone.
No per-slot executable stamps exist, so within-run change is UNKNOWN, not
asserted. The driver inherited its launch environment, but this is insufficient
to certify every subsequent resolution. SDK and all 145 Python runtime files
still match. The future safe entry requires an explicit pinned CLI and before/
after stamps per slot. No new live model run tests that repair here.
