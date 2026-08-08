#!/usr/bin/env bash
# alva conformance harness:
#   tests/parser/            -> must parse + check OK
#   tests/typecheck/pass/    -> must check OK
#   tests/typecheck/fail/    -> must FAIL to check (exit != 0)
#   tests/effects/           -> must FAIL (effect violations)
#   tests/contracts/         -> must build + pass tests
#   tests/modules/           -> reserved for cross-module linking
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
if [ ! -x "$ALVA" ]; then
  echo "alva binary not found at $ALVA (build it first: cd alva && cargo build)"
  exit 1
fi

FAILED=0

# 结构平衡预检：任何 .alva 文件都不允许括号不配对（词法级，先于语义检查）。
if "$PY" "$ROOT/scripts/check_parens.py" --check-tree "$ROOT/examples" && \
   "$PY" "$ROOT/scripts/check_parens.py" --check-tree "$ROOT/tests" --exclude "tests/parser/fail"; then
  echo "PASS paren balance (all .alva)"
else
  echo "FAIL paren balance"
  FAILED=1
fi

run_check_ok() {
  local dir="$1"
  for f in "$ROOT"/tests/"$dir"/*.alva; do
    [ -e "$f" ] || continue
    if "$ALVA" check "$f" >/dev/null 2>&1; then
      echo "PASS check  $dir/$(basename "$f")"
    else
      echo "FAIL check  $dir/$(basename "$f")"
      FAILED=1
    fi
  done
}

run_check_fail() {
  local dir="$1"
  local files=()
  for f in "$ROOT"/tests/"$dir"/*.alva; do
    [ -e "$f" ] && files+=("$f")
  done
  if [ ${#files[@]} -gt 0 ]; then
    if "$PY" "$ROOT/tests/golden_check.py" "$ALVA" "${files[@]}"; then
      :
    else
      FAILED=1
    fi
  fi
}

run_check_ok parser
run_check_ok typecheck/pass
run_check_fail parser/fail
run_check_fail typecheck/fail
run_check_fail effects
run_check_fail externs
run_check_fail modules/fail
run_check_fail contracts/fail
run_check_fail limits
run_check_ok modules

# strict-mode self tests (matching semantics)
if "$PY" "$ROOT/tests/golden_check.py" --self-test; then
  echo "PASS golden strict self-test"
else
  echo "FAIL golden strict self-test"
  FAILED=1
fi

# negative test: strict mode must reject deliberately incomplete expectations
if "$PY" "$ROOT/tests/golden_check.py" "$ALVA" "$ROOT/tests/strict_negative/extra_diag.alva" >/dev/null 2>&1; then
  echo "FAIL strict negative: extra diagnostics were accepted"
  FAILED=1
else
  echo "PASS strict negative: extra diagnostics rejected"
fi

# AST depth boundary (check/manifest/codegen recursion, no worker stack)
if bash "$ROOT/tests/depth/boundary_test.sh"; then
  echo "PASS depth boundary"
else
  echo "FAIL depth boundary"
  FAILED=1
fi

# AIR / AEP (source-less typed program construction)
if bash "$ROOT/tests/air/run_air_test.sh"; then
  echo "PASS air/aep"
else
  echo "FAIL air/aep"
  FAILED=1
fi

# manifest 语义哈希稳定性
if bash "$ROOT/tests/manifest/run_test.sh"; then
  echo "PASS manifest hashes"
else
  echo "FAIL manifest hashes"
  FAILED=1
fi

# 跨模块 linking + impact
if bash "$ROOT/tests/project/run_test.sh"; then
  echo "PASS project linking"
else
  echo "FAIL project linking"
  FAILED=1
fi

# contracts: build and run tests
for f in "$ROOT"/tests/contracts/*.alva; do
  [ -e "$f" ] || continue
  if "$ALVA" build "$f" --test >/dev/null 2>&1; then
    echo "PASS contract $(basename "$f")"
  else
    echo "FAIL contract $(basename "$f")"
    FAILED=1
  fi
done

exit $FAILED
