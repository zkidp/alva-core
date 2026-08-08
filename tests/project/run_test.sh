#!/usr/bin/env bash
# 跨模块 linking 测试：
#   1) project check 通过（含跨模块调用解析）
#   2) 循环依赖被检测
#   3) project build --test 通过
#   4) impact 输出 CHANGED + AFFECTED
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
PROJ="$ROOT/tests/project"
OUT="$PROJ/build"
BASE="$PROJ/impact-base"
HEAD="$PROJ/impact-head"

echo "== project check =="
"$ALVA" project check "$PROJ/alva.toml" | grep -q "2 modules checked"

echo "== cycle detection =="
if "$ALVA" project check "$PROJ/cycle/alva.toml" >/dev/null 2>&1; then
  echo "FAIL: cycle not detected"; exit 1
fi
echo "cycle detected"

echo "== project build + test =="
rm -rf "$OUT"
"$ALVA" project build "$PROJ/alva.toml" --test --out-dir "$OUT"

echo "== impact =="
TMPDIR2="$(mktemp -d)"
"$ALVA" project build "$ROOT/tests/project-base/alva.toml" --out-dir "$TMPDIR2/base" >/dev/null
"$ALVA" project build "$ROOT/tests/project/alva.toml" --out-dir "$TMPDIR2/head" >/dev/null
OUT2="$("$ALVA" impact --base "$TMPDIR2/base/manifests" --head "$TMPDIR2/head/manifests")"
echo "$OUT2"
echo "$OUT2" | grep -q "CHANGED  demo.model"
echo "$OUT2" | grep -q "AFFECTED demo.app"
rm -rf "$TMPDIR2"

echo "PROJECT TESTS PASSED"
