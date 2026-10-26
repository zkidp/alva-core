# Adaptation log (before any scientific model call)

All four fixed tasks now qualify: compiling-but-task-failing stubs; passing
Python, ALVA Text and AEP reference witnesses against the same typed input/output
vectors. References are development witnesses, not model inputs. No task was
selected, removed, or replaced using a model outcome.

Preparation failures were retained locally and fixed before freezing:

- Stripping the Windows toolchain environment prevented MSVC linker discovery.
  The evaluator now retains explicitly listed non-credential toolchain/OS keys;
  no credential environment is passed to candidate checks.
- Construction type strings use primitive names (`i64`, `bool`), not the source
  spelling `(prim ...)`. Type child arguments are strings, not revision handles.
- The attempted vector accumulator fold witness is **unsupported via that
  construction path**: compound types are not parsed from its type-string field,
  and replace_expression does not expose an acc_type slot. No Core change was
  made. The same vector-mapping task has a supported recursive witness using
  ordinary create_call/create_if, slice, append and veclit. This is not evidence
  that every vector-fold operation is unsupported or that the task is impossible.
- Same-module recursion uses unqualified `solve`; `bench.solve` was rejected by
  the source checker as an external call. Final witnesses use the supported name.

Coverage: 4/4 selected adapted task domains have executable witnesses in all
three conditions. Excluded domains are Unicode code-point length, unbounded
integers/overflow and heterogeneous lists. No coverage estimate over all 164
HumanEval tasks is claimed. No language/API feature was added to obtain PASS.

Public origin and MIT notice are in PROVENANCE.json/HUMANEVAL-LICENSE.txt.
The source commit, selection rule, references, vectors and stubs are frozen.
This is not MultiPL-E's translator or official scoring pipeline. Familiarity,
public-task contamination, tiny convenience sampling, language/tool learning
costs, algorithm choice and AEP construction affordances remain limitations.

Host/controller follows the official app-server thread/turn/interrupt protocol:
https://learn.chatgpt.com/docs/app-server . The reused AppServer class is only
the P0 transport; the prospective event controller is new, not P3's executor.
