# ALVA body reference

These are generic language forms, not a task solution. Names below are examples;
use actual declarations and types returned by the compiler. The Host accepts
one body fragment, not a module/function declaration. Builtin aliases may also
appear under `call` in imported programs; direct builtin forms are unambiguous.

## body

`(body expression...)` returns its final expression. Typical values are
`(int 3)`, `(float 1.5)`, `(bool true)`, `(string "text")`, `(nil)` and
`(ref local_name)`. Strings are double-quoted; escape quotes as `\"` and
backslashes as `\\`. User functions use `(call module.function arg...)`.
Do not send Markdown fences or a whole function as the body argument.

## bindings

`(let name value body)` binds a local in its body. An explicit type is also
allowed: `(let count (prim i64) (int 2) (+ (ref count) (int 1)))`.
`(if condition then_expression else_expression)` needs compatible branches.
Arithmetic/comparisons use `(+ a b)`, `(- a b)`, `(* a b)`, `(/ a b)`,
`(== a b)`, `(< a b)`, `(>= a b)`. Boolean forms include `and`, `or`, `not`.
Named primitive types use `(prim i64)`, `(prim string)`, `(prim bool)`.

## collections

Vectors: `(vec (prim string))`, `(vec (prim i64) (int 2) (int 4))`.
Operations: `(len v)`, `(get v index)`, `(append v value)`,
`(slice v start end)` with an exclusive end, `(range start end)`.
A fold is `(fold item sequence (acc total (prim i64) (int 0))
  (+ (ref total) (ref item)))`. It returns the accumulator, not a loop statement.
Maps: `(map (prim string) (prim i64))`, `(keys m)`, `(contains m key)`,
`(lookup m key)`, `(set m key value)`, `(remove m key)`.
Honor index/range bounds and arithmetic overflow constraints.

## records

Record types are named; access a field with `(field value "field_name")`.
Construct `(record Item (value expression) (label expression))` with every
required field. Update with `(record-update Item base (value expression))`,
preserving other fields. Use actual field types from the declaration.

## results

Result values use `(ok value)` and `(err error)`. Inspection operations include
`(is-ok result)`, `(is-err result)`, `(unwrap result)`, `(unwrap-err result)`.
Only unwrap the appropriate variant. An explicit Result return may wrap an
ordinary final value in Ok, but explicit variants make branches clear.
Enums: `(variant Flag enabled)` and
`(match Flag value (case enabled yes_expression) (case disabled no_expression))`.
Use the actual enum type and cover its variants.

## strings

Common forms are `(concat a b)`, `(split text separator)`,
`(join parts separator)`, `(trim text)`, `(starts-with text prefix)`,
`(strip-prefix text prefix)`, `(to-string value)` and `(parse-int text)`.
Consult compiler feedback for the actual supported operation/return type.
Do not invent escaping, parsing or collection APIs from another language.

## diagnostics

Use the returned error code and position to repair the submitted fragment.
Parse errors leave the prior draft intact; type/scope rejections do not
authorize publication. A failed behavior test supplies status, not its hidden
assertions. A new preparation always invalidates an older passing proposal.
After a conflict or expired view, call `read_target` again. Preserve all guards
and task/regression assertions while repairing a candidate.
