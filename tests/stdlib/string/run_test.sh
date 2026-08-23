#!/usr/bin/env bash
# STDLIB-MATURATION-00：alva.std.string 端到端测试。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
DIR="$ROOT/tests/stdlib/string"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "== stdlib: string (STDLIB-MATURATION-00) =="
"$ALVA" project check "$DIR/alva.toml" | grep -q "2 modules checked"
"$ALVA" project build "$DIR/alva.toml" --test --out-dir "$OUT/string" >/dev/null
echo "PASS stdlib string"
