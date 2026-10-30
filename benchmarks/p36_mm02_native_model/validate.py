"""Portable public provenance validation; never starts a model or candidate."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import decode


def validate():
    here = Path(__file__).parent
    frozen = json.loads((here / "FREEZE.json").read_text())
    assert frozen["base"] == "88cb64c9a9361c00f061bb1da2043d55315f8235"
    assert frozen["task"]["bundle"]["payload_sha256"] == "352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf"
    assert set(decode(frozen["task"]["bundle"], frozen["task"]["bundle"]["payload_sha256"])) == {"alva.toml", "src/model.alva", "src/xml.alva"}
    assert frozen["policy"]["authorized_functions"] == ["store.xml.parse_prefix"]
    assert len(frozen["schedule"]) == 1 and frozen["schedule"][0]["arm"] == "N"
    assert len(frozen["native_tools"]) == 20
    expected_prompt = frozen["public_task_input"] + "\n$alva\nComplete official Skill and references follow verbatim:\n" + "".join(
        "\n--- " + name + " ---\n" + body for name, body in frozen["docs"].items())
    assert frozen["schedule"][0]["prompt"] == expected_prompt
    prior = json.loads((ROOT / "benchmarks/mm01_pilot/FREEZE.json").read_text())
    assert frozen["docs"] == prior["docs"] and frozen["language"] == prior["language"]
    assert frozen["config"]["model"] == "gpt-5.6-sol" and frozen["config"]["effort"] == "low"
    assert frozen["config"]["token_observation_threshold"] == 600000
    assert not any(p.startswith("benchmarks/p35_") for p in frozen["files"])
    with tempfile.TemporaryDirectory(prefix="p36-exact-bytes-") as d:
        root = Path(d)
        for path, digest in frozen["files"].items():
            data = base64.b64decode(frozen["runtime_bytes"][path], validate=True)
            assert hashlib.sha256(data).hexdigest() == digest, path
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # These tests consume the frozen analyzer/runtime bytes, not newline alternatives.
        subprocess.run([sys.executable, "-m", "unittest", "benchmarks.p36_mm02_native_model.test_pilot", "-v"], cwd=root, check=True)
    if (here / "RESULTS.json").exists():
        result = json.loads((here / "RESULTS.json").read_text())
        assert result["model_slots_started"] <= 1
        assert result["provider_requests"] is None and result["dollar_cost"] is None
        assert not result["cached_tokens_subtracted"]
        assert result["native_commit_dispatches"] == sum(a["native_dispatches"] for a in result["commit_attempts"])
        if result["disposition"] == "COMPLETED_CORRECT_MAINTENANCE":
            assert result["task"] == result["regression"] == result["scope"] == "PASS"
            assert result["fresh_revision_matches_commit"] and result["successful_native_commits"] > 0
        assert (here / "ARCHIVE.json").exists()
    print("P36 provenance/exact-byte attribution tests PASS; CI model generation=0")


if __name__ == "__main__":
    validate()
