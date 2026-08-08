#!/usr/bin/env bash
# 语义哈希稳定性测试：
#   same1 vs same2           -> interface_hash 相同（注释/空白/参数名/私有函数不影响）
#   same1 vs changed_type    -> 不同（参数类型变化）
#   same1 vs changed_contract-> 不同（契约变化）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
DIR="$ROOT/tests/manifest"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

hash_of() {
  "$ALVA" manifest "$1" | "$PY" -c "import json,sys; print(json.load(sys.stdin)['interface_hash'])"
}

same1="$(hash_of "$DIR/same1.alva")"
same2="$(hash_of "$DIR/same2.alva")"
changed_type="$(hash_of "$DIR/changed_type.alva")"
changed_contract="$(hash_of "$DIR/changed_contract.alva")"

echo "same1=$same1 same2=$same2"
echo "changed_type=$changed_type changed_contract=$changed_contract"

[ "$same1" = "$same2" ] || { echo "FAIL: same1/same2 hash differ"; exit 1; }
[ "$same1" != "$changed_type" ] || { echo "FAIL: type change did not alter hash"; exit 1; }
[ "$same1" != "$changed_contract" ] || { echo "FAIL: contract change did not alter hash"; exit 1; }
echo "MANIFEST HASH TESTS PASSED"
