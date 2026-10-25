# Python Guard CLI example

From the repository root:

```text
python examples/python_guard/demo.py
```

This uses actual snapshot/verify/report subprocess calls on a disposable Python
fixture and its public unittest suite. Expected result: good patch PASS; bad
behavior FAIL/NEW_REGRESSION; an old successful result becomes STALE after the
caller edits source. Both verify calls assert original project bytes unchanged.

See [implementation and policy contract](../../docs/python-guard-implementation.md)
for applying the same interface to an authorized trusted Python project. The
verifier does not apply patches to that project's real source or provide a sandbox.
