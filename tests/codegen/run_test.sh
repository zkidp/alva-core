#!/usr/bin/env bash
# codegen 回归测试（cd30061 时代修复的可重建回归）：
#   xres  — 外部 result 函数作为最后表达式，不得双重 Ok 包装
#   xenum — 跨模块枚举构造/匹配套 type_path()
#   xfold — result 型 fold 累加器作为最后表达式，不得双重 Ok 包装
#   xfoldnest — 嵌套 fold 引用外层 acc（GAP-009），必须运行时正确
#   record_update — RFC-0001 partial record update（T1/T2/T3/T4/T9/T11/T13/T14）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
DIR="$ROOT/tests/codegen"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "== codegen: xres (external result fn, no double Ok wrap) =="
"$ALVA" project check "$DIR/xres/alva.toml" | grep -q "2 modules checked"
"$ALVA" project build "$DIR/xres/alva.toml" --test --out-dir "$OUT/xres" >/dev/null
if grep -q "Ok(crate::xres_a::fetch" "$OUT/xres/xres/src/xres_b.rs"; then
  echo "FAIL: xres_b.rs double-wraps external result call"
  exit 1
fi
grep -q "crate::xres_a::fetch()" "$OUT/xres/xres/src/xres_b.rs"
echo "PASS xres"

echo "== codegen: xenum (cross-module enum construct/match) =="
"$ALVA" project check "$DIR/xenum/alva.toml" | grep -q "2 modules checked"
"$ALVA" project build "$DIR/xenum/alva.toml" --test --out-dir "$OUT/xenum" >/dev/null
if grep -q "xenum.a.Color::" "$OUT/xenum/xenum/src/xenum_b.rs"; then
  echo "FAIL: xenum_b.rs uses raw dotted enum path"
  exit 1
fi
grep -q "crate::xenum_a::Color::Red" "$OUT/xenum/xenum/src/xenum_b.rs"
grep -q "crate::xenum_a::Color::Green" "$OUT/xenum/xenum/src/xenum_b.rs"
echo "PASS xenum"

echo "== codegen: xfold (result-typed fold accumulator, no double Ok wrap) =="
"$ALVA" project check "$DIR/xfold/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/xfold/alva.toml" --test --out-dir "$OUT/xfold" >/dev/null
if grep -qE "Ok\(\{ let mut __acc[0-9]+" "$OUT/xfold/xfold/src/xfold_x.rs"; then
  echo "FAIL: xfold_x.rs double-wraps result-typed fold"
  exit 1
fi
grep -qE "let mut __acc[0-9]+: Result" "$OUT/xfold/xfold/src/xfold_x.rs"
echo "PASS xfold"

echo "== codegen: xfoldnest (nested fold referencing outer acc, GAP-009) =="
"$ALVA" project check "$DIR/xfoldnest/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/xfoldnest/alva.toml" --test --out-dir "$OUT/xfoldnest" >/dev/null
echo "PASS xfoldnest"

echo "== codegen: record_update (RFC-0001 partial record update) =="
"$ALVA" project check "$DIR/record_update/alva.toml" | grep -q "2 modules checked"
"$ALVA" project build "$DIR/record_update/alva.toml" --test --out-dir "$OUT/record_update" >/dev/null
# T3: base 只求值一次（绑定到唯一临时变量）
if ! grep -q "let __base0 = it.clone()" "$OUT/record_update/record_update/src/recup_b.rs"; then
  echo "FAIL: record_update base not bound to a single temp"
  exit 1
fi
# T4: update value 按书写顺序求值（name/tag 在未指定字段读取之前）
if ! grep -qE "Item \{ name: .*tag: .*qty: __base0\.qty" "$OUT/record_update/record_update/src/recup_b.rs"; then
  echo "FAIL: record_update written-order evaluation not preserved"
  exit 1
fi
echo "PASS record_update"

echo "== codegen: query (RFC-0003 vec contains / any / all / find) =="
"$ALVA" project check "$DIR/query/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/query/alva.toml" --test --out-dir "$OUT/query" >/dev/null
for t in contains_ok any_all find_ok; do
  if ! grep -q "fn test_$t" "$OUT/query/query/src/query_x.rs"; then
    echo "FAIL: query test $t missing from generated Rust"
    exit 1
  fi
done
echo "PASS query"

echo "== codegen: discarded_ok (CS-002: discarded Ok/Err must typecheck) =="
"$ALVA" project check "$DIR/discarded_ok/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/discarded_ok/alva.toml" --test --out-dir "$OUT/discarded_ok" >/dev/null
echo "PASS discarded_ok"

echo "== codegen: discarded_nested (CS-002 R2: used Result keeps local type) =="
"$ALVA" project check "$DIR/discarded_nested/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/discarded_nested/alva.toml" --test --out-dir "$OUT/discarded_nested" >/dev/null
# the used (ok 1) inside the discarded call must NOT be turbofished with String
if grep -qE "Ok::<_, String>\(1" "$OUT/discarded_nested/discarded_nested/src/discarded_nested_x.rs"; then
  echo "FAIL: discarded_nested over-annotated a used Ok with fn error type"
  exit 1
fi
grep -q "consume(Ok(1i64))" "$OUT/discarded_nested/discarded_nested/src/discarded_nested_x.rs"
echo "PASS discarded_nested"

echo "== codegen: discarded_err (CS-002 R3: discarded Err typechecks) =="
"$ALVA" project check "$DIR/discarded_err/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/discarded_err/alva.toml" --test --out-dir "$OUT/discarded_err" >/dev/null
echo "PASS discarded_err"

echo "== codegen: discarded_local_result (CS-002 R4: discarded local Result differs from fn Result) =="
"$ALVA" project check "$DIR/discarded_local_result/alva.toml" | grep -q "1 modules checked"
"$ALVA" project build "$DIR/discarded_local_result/alva.toml" --test --out-dir "$OUT/discarded_local_result" >/dev/null
echo "PASS discarded_local_result"

echo "CODEGEN REGRESSIONS PASSED (xres/xenum/xfold/xfoldnest/record_update/query/discarded_ok/discarded_nested/discarded_err/discarded_local_result)"
