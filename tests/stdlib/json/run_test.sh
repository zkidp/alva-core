#!/usr/bin/env bash
# STDLIB-MATURATION-00 Phase 1：alva.std.json 端到端测试。
# 1) project check 自动注入 alva.std.json（2 modules checked）
# 2) project build --test 生成 Rust 并运行 16 个 json 测试
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
DIR="$ROOT/tests/stdlib/json"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "== stdlib: json (STDLIB-MATURATION-00 Phase 1) =="
"$ALVA" project check "$DIR/alva.toml" | grep -q "2 modules checked"
"$ALVA" project build "$DIR/alva.toml" --test --out-dir "$OUT/json" >/dev/null
echo "PASS stdlib json"
