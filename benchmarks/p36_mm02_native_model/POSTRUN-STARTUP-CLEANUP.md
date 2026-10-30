# P36 post-run technical fix — startup ownership (P2)

Pre-fix HEAD: `3991160cb8e62fb8750073a663d29c275fa729cd`.
Existing PR: [#36](https://github.com/zkidp/alva-core/pull/36).
Fix commits and final CI links are reported in the original P2 review thread;
this independent record is not a rewrite of the scientific report.

## Problem and change

The original constructor could throw after SSH launch, before the caller had a
Slot to close. A readiness timeout, early SSH exit or probe exception could
therefore leave local transport and remote sandbox processes alive.

The current constructor establishes a fresh instance identifier before launch,
waits with an actual bounded probe timeout, and catches startup exceptions on
the partially constructed object. Before rethrowing the **original** exception,
it requests precise remote cancellation, terminates/kills/reaps local SSH with
bounded waits and closes its pipes. `startup-failure.json` records the original
startup error and the independent `STARTUP_CLEANUP_CONFIRMED` or
`STARTUP_CLEANUP_UNCONFIRMED` result. Record/cleanup failure cannot replace the
startup error. Normal close also finishes the same owner after graceful stop.

`startup_owner.py` is a small Linux launch supervisor, not a Core or P22/P23
rewrite. The existing service executes as init in one additional unprivileged
PID namespace. Its exact host PID/start ticks/boot identity are reported over
inherited pipes, checked before/after pidfd acquisition, and execution is gated
until the owner has pinned that identity. The owner signals only these pidfds,
never a PID inferred from process names. Exit of namespace init destroys its
descendants, including separate sessions/groups and nested sandbox namespaces;
the owner verifies init exit, reaps the unshare helper, then removes only its
own scratch subtree. `TMPDIR` locates the existing backend's temporary storage
within that subtree. No unrelated task or broad `pkill` target is involved.

An instance-specific Unix socket supplies cancellation acknowledgments. A
lock-protected tombstone prevents delayed startup even if cancellation arrives
before the remote owner/identity exists. Duplicate/wrong-instance requests do
not signal anything. Termination or acknowledgement failure stays unconfirmed,
even if local SSH has exited. All cleanup waits are bounded; no model task is
started by these tests or after a failed constructor.

## Validation and remaining boundary

Portable tests exercise normal start/close, readiness timeout with a stubborn
SSH requiring kill, early exit/reaping, injected remote cleanup failure, and a
probe exception plus failed error-record write. Existing P36 frozen-byte and
outcome-attribution tests continue to use the original embedded snapshot.
Existing seven P31 policy/protocol and seven P34 Guard units also pass locally.

A dedicated Ubuntu 22.04 CI job exercises **real local Linux processes**, not a
real SSH host: a live service without readiness, its setsid child, an unrelated
live process, early service failure, and cancellation before identity/start.
The tests check actual pidfd exit and owned scratch removal, and prove the
unrelated process remains alive. The portable fake-transport tests are not
claimed as evidence of actual remote termination. CI execution/status and the
exact patch SHA are provided in the review reply after completion.

**REMOTE_TERMINATION_VERIFIED**, using the user's previously authorized password
login. The initial BatchMode check failed because the old temporary key had
been deleted; that was not the only existing authentication method. No key was
recreated and no new permission was obtained. A separate trusted test checkout
at fix commit `617330dc4cb873ec573d3cb5b8a25d2b87f6bc52` was used, leaving the
original study workspace and raw archive untouched.

`ssh_startup_probe.py` supplies a manual, zero-model real SSH integration probe.
One actual SSH session launched the current owner and a controlled fake service
which never wrote readiness; a second already-authenticated control session
cancelled that exact instance after an injected short readiness deadline.
Actual pidfds confirmed the remote service init and its setsid descendant had
exited, the owner helper was reaped and scratch removed, and the unrelated
control task was still alive. The latter was then explicitly cleaned by its
own pidfd. The launch SSH process naturally exited with code 0 and was reaped;
both control sessions were also closed. No Native MCP/SDK or model was started.

This complements the actual Slot constructor unit tests using fake transport;
it does not claim the password-authenticated probe invoked Slot's noninteractive
SSH adapter end to end. It directly tests the new remote owner/cancel protocol
over real SSH, plus launch transport exit. Actual key-based automatic SSH auth
was not recreated. Local mocks are not used as remote termination evidence.

`STARTUP-CLEANUP-VALIDATION.json` records the separate derived verification.
Controlled new raw record `.local/p36-startup-fix/remote-proof.json` SHA256:
`ed6c205177e3ba6d40fbca6c4d44e03a948ecc2bd5e10173a34289aa520693d4`.
The copied bytes were checked against the remote file's SHA256. This record is
independent of the immutable P36 model RAW.zip. The P2 thread is resolved only
after final CI and a concrete review reply, using this real remote evidence.

## Frozen science remains separate

**P36_SCIENTIFIC_RESULT_UNCHANGED**: one original real slot, 18 model tools,
268,974 reported tokens, 36.093 active seconds, one allowed Guard decision and
one Native commit; AIR/fresh authority and original task/regression/scope PASS.
Disposition stays `COMPLETED_CORRECT_MAINTENANCE`.

Original generation freeze:
`822951be0edc2b49b0b9c7db71ace5fdcca342c1`.
Original controlled archive SHA256:
`2ab999b48a2b1854f290d409ccb57ebe7bad65c9391609b3a97fbf861205f203`.

FREEZE.json and its runtime_bytes, ARCHIVE.json, RESULTS.json, ANALYSIS.json,
VALIDATION.json, the original REPORT.md and the controlled RAW.zip are unchanged.
P20–P35 historical evidence is untouched. Current pilot.py/remote.py differ
from their embedded frozen versions **because this is a post-run engineering
fix**. The original versions remain exact in the freeze and original commits.
`validate.py` materializes the frozen bytes for historical checks;
`verify_postrun.py` separately checks protected scientific files against the
pre-fix commit and, when locally available, the original RAW archive digest.
Do not run the historical publisher against current repaired runtime bytes or
overwrite its old validation result. No latest-wins replacement is used.

Commands (zero models):

```text
python -m unittest benchmarks.p36_mm02_native_model.test_startup_cleanup -v
python benchmarks/p36_mm02_native_model/validate.py
python benchmarks/p36_mm02_native_model/verify_postrun.py
python -m unittest tests.integrations.test_native_commit_authorization tests.integrations.test_precommit_scope_guard -v
```

No prepare/run, model turn, P35 witness, historical P34 experiment, Core change,
new sample, P37 or merge is authorized by this fix.
