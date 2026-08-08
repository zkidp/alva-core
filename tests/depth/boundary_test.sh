#!/usr/bin/env bash
# AST depth boundary tests (no worker thread stack workaround).
#
# With the default ALVA_MAX_AST_DEPTH=512 the compiler must:
#   - accept and fully process (check / manifest / codegen) inputs whose
#     nesting is at the limit (deep nested binop chain, max source depth 511);
#   - reject nesting one level over the limit with a stable E_PARSE_002
#     diagnostic (no stack overflow).
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

FAILED=0

gen_deep_binop() { # $1 = k (binop levels)  $2 = outfile
  local k="$1" out="$2" expr="(int 1)" i
  for ((i = 0; i < k; i++)); do
    expr="(+ (int 1) $expr)"
  done
  {
    printf '(module\n  (name "deep_boundary")\n  (version "0.1.0")\n'
    printf '  (export f)\n  (fn f\n    (params)\n    (returns (prim i64))\n'
    printf '    (pure)\n    (body %s)))\n' "$expr"
  } > "$out"
}

# k=254 binop levels -> max source nesting depth 511 (within default 512).
gen_deep_binop 254 "$TMP/deep_valid.alva"
if "$ALVA" check "$TMP/deep_valid.alva" >/dev/null 2>&1; then
  echo "PASS depth check within limit (source depth 511)"
else
  echo "FAIL depth check within limit"
  FAILED=1
fi

if "$ALVA" manifest "$TMP/deep_valid.alva" >/dev/null 2>&1; then
  echo "PASS depth manifest within limit (semantic serializer recursion)"
else
  echo "FAIL depth manifest within limit"
  FAILED=1
fi

if "$ALVA" build "$TMP/deep_valid.alva" --out-dir "$TMP/out" >/dev/null 2>&1; then
  echo "PASS depth codegen within limit (generated Rust compiles)"
else
  echo "FAIL depth codegen within limit"
  FAILED=1
fi

# One level over the limit must yield E_PARSE_002, never a stack overflow.
# 512 open parens + atom + 512 close parens: atom sits at depth 513.
printf '%sx%s\n' "$(printf '%.0s(' $(seq 1 512))" "$(printf '%.0s)' $(seq 1 512))" > "$TMP/deep_invalid.alva"
out="$("$ALVA" check "$TMP/deep_invalid.alva" --json 2>&1)"
code=$?
if [ "$code" -ne 0 ] && printf '%s' "$out" | grep -q 'E_PARSE_002'; then
  echo "PASS depth over limit rejected with E_PARSE_002"
else
  echo "FAIL depth over limit: exit=$code out=$out"
  FAILED=1
fi
if printf '%s' "$out" | grep -qi 'stack overflow\|panicked'; then
  echo "FAIL depth over limit: compiler stack overflow/panic"
  FAILED=1
fi

exit $FAILED
