#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
ALVA="$ALVA" "$PY" "$ROOT/tests/air/air_test.py"
ALVA="$ALVA" "$PY" "$ROOT/tests/air/air_check_soundness_test.py"
ALVA="$ALVA" "$PY" "$ROOT/tests/air/agent_tools_test.py"
