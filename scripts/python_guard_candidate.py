#!/usr/bin/env python3
"""Run the optional trusted-host CLI from any consumer working directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrations.python_guard_codex.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
