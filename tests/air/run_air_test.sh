#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALVA="${ALVA:-$ROOT/alva/target/debug/alva}"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
ALVA="$ALVA" "$PY" "$ROOT/tests/air/air_test.py"
ALVA="$ALVA" "$PY" "$ROOT/tests/air/air_check_soundness_test.py"
ALVA="$ALVA" "$PY" "$ROOT/tests/air/query_aep_test.py"
ALVA="$ALVA" "$PY" "$ROOT/tests/air/rfc0006_construction_test.py"
# agent_tools_test.py drives the high-level AEP tools against the frozen
# A/C task fixtures under benchmarks/ac (research artifacts). Run it when
# the harness is present; SKIP with a visible message otherwise (the public
# snapshot keeps CI green without silently hiding the test).
if [ -d "$ROOT/benchmarks/ac/tasks" ]; then
  ALVA="$ALVA" "$PY" "$ROOT/tests/air/agent_tools_test.py"
else
  echo "SKIP agent_tools_test (benchmarks/ac fixtures not in this tree)"
fi
