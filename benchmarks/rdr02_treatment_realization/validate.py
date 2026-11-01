"""Independent evidence/certificate verifier. Does not import either classifier."""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.rdr02_treatment_realization import evidence as e


def validate(observations, comparison, paths=None):
    sources = e.public_sources()
    raw, access = e.read_archives(paths or {})
    sources.update(raw)
    assert [r["id"] for r in observations["units"]] == ["U1", "U2", "U3", "U4"]
    assert [r["id"] for r in comparison["rows"]] == ["U1", "U2", "U3", "U4"]
    checked, private_unchecked, records = 0, 0, []
    for observation, result in zip(observations["units"], comparison["rows"]):
        assert result["evidence_sha256_E0"] == result["evidence_sha256_E1"] == e.identity(observation)
        assert result["model_unit"] == observation["model_unit"] == (observation["id"] != "U1")
        assert result["agreement"] == (result["E0"] == result["E1"])
        refs = []
        def collect(value):
            if isinstance(value, dict):
                if set(value) == {"source", "pointer", "record_sha256"}:
                    refs.append(value)
                else:
                    for child in value.values(): collect(child)
            elif isinstance(value, list):
                for child in value: collect(child)
        collect(observation)
        for ref in refs:
            assert len(ref["record_sha256"]) == 64
            if ref["source"] not in sources:
                assert ref["source"].startswith(observation["id"] + ":")
                private_unchecked += 1
                continue
            actual = e.pointer(sources[ref["source"]], ref["pointer"])
            assert e.identity(actual) == ref["record_sha256"], ref
            checked += 1
        # Independently check the portable proposition calculation, then bind
        # the values back to raw records when supplied. No historical grade input.
        expected = {k: "UNKNOWN" for k in result["E0"]["stages"]}
        if observation["id"] == "U1":
            expected = {k: "NOT_APPLICABLE" for k in expected}
            actual_gaps = []
            for probe in observation["coverage_probes"]:
                call = e.pointer(sources[probe["evidence"]["source"]], probe["evidence"]["pointer"])
                descriptor = probe["advertised_evidence"]
                assert probe["response_sha256"] == e.identity(call["response"])
                assert probe["isError"] == call["response"].get("isError")
                if descriptor is not None:
                    d = e.pointer(sources[descriptor["source"]], descriptor["pointer"])
                    assert d["response"].get("isError") is False
                    assert d["response"]["structuredContent"]["name"] == call["name"]
                actual_gaps.append(bool(descriptor and call["response"].get("isError") and
                    "E_MCP_UNKNOWN_TOOL" in str(call["response"].get("structuredContent", {}))))
            expected["exposure"] = "FALSE" if any(actual_gaps) else "UNKNOWN"
            label = "CAPABILITY_COVERAGE_GAP" if any(actual_gaps) else "UNKNOWN"
            tests, staged = "NOT_APPLICABLE", "NOT_APPLICABLE"
        elif "state" not in observation:
            label, tests, staged = "UNKNOWN", "UNKNOWN", "UNKNOWN"
            assert observation["availability"]["status"] == "EVIDENCE_UNAVAILABLE"
        else:
            backend, frontend = observation["backend"], observation["frontend"]
            for b in backend:
                ref = b["evidence"]
                if ref["source"] not in sources: continue
                original = e.pointer(sources[ref["source"]], ref["pointer"])
                response = original["response"]
                assert b["response_sha256"] == e.identity(response)
                assert b["success"] == (response.get("ok") if "ok" in response else not response["isError"])
                payload = response.get("structuredContent", response.get("result")) or {}
                assert b["result_revision"] == payload.get("revision")
                assert b["generation"] == payload.get("generation")
                assert b["problems"] == payload.get("problems")
                assert b["withheld"] == original.get("withheld", False)
                if "request" in original:
                    p = original["request"]["params"]
                    assert b["operation"] == p["name"] and b["call_id"] == p.get("_meta", {}).get("callId")
                    assert b["arguments_sha256"] == e.identity(p.get("arguments", {}))
                else:
                    assert b["operation"] == original["arguments"]["tool"]
            for f in frontend:
                ref = f["evidence"]
                if ref["source"] not in sources: continue
                item = e.pointer(sources[ref["source"]], ref["pointer"])
                assert f["call_id"] == item["id"] and f["operation"] == item["tool"]
                assert f["error"] == item.get("error") and f["status"] == item["status"]
            prefix = {"U2": "P26-12-HE23-B", "U3": "MM01-S", "U4": "P32-MM01-S"}[observation["id"]]
            record_source = observation["id"] + ":" + prefix + ("/result.json" if observation["id"] == "U2" else "/record.json")
            if record_source in sources:
                events = sources[record_source]["events"]
                retained = [f"/events/{i}/params/item" for i, event in enumerate(events)
                            if event.get("method") in {"item/started", "item/completed"} and
                            event.get("params", {}).get("item", {}).get("type") in {"mcpToolCall", "dynamicToolCall"}]
                assert [f["evidence"]["pointer"] for f in frontend] == retained
            for point in observation["observer"]:
                ref = point["evidence"]
                if ref["source"] not in sources: continue
                original = e.pointer(sources[ref["source"]], ref["pointer"])
                for key in ("call_id", "transaction_id", "body_sha256", "after_operation", "baseline"):
                    assert point[key] == original[key]
            states = observation["state"]
            start, end = states["initial_authority"], states["final_authority"]
            for state in (start, end):
                ref = state["evidence"]
                if ref["source"] in sources:
                    original = e.pointer(sources[ref["source"]], ref["pointer"])
                    assert state["project_revision"] == original["project_revision"]
                    assert state["target_body_sha256"] == original.get("body_sha256", original.get("bodies", {}).get("demo.model.touch_size"))
                    assert state["bodies"] == original.get("bodies")
            file_ref = states["file_evidence"]
            if file_ref["source"] in sources:
                files = e.pointer(sources[file_ref["source"]], file_ref["pointer"])
                decoded = {k: base64.b64decode(v, validate=True) for k, v in files.items()}
                assert states["final_file_hashes"] == {k: e.sha(v) for k, v in decoded.items()}
                current = decoded.get("alva-air/current", b"").decode().splitlines()
                assert states["stored_current_revision"] == (current[1] if len(current) == 2 else None)
                # Source-order completeness: an omitted denied/actual commit
                # must not disappear merely because the retained rows agree.
                linux = sources[file_ref["source"]]
                native = [i for i,c in enumerate(linux["calls"]) if c.get("action") == "aep" or
                          c.get("request", {}).get("method") == "tools/call"]
                assert [b["evidence"]["pointer"] for b in backend] == [f"/calls/{i}" for i in native]
            accepted = [b for b in backend if b["success"] and not b["withheld"]]
            commits = [b for b in accepted if b["operation"] == "commit_transaction"]
            refused = any(f["operation"] == "commit_transaction" and "approval" in str(f["error"]).lower() for f in frontend)
            attachment_ids = {b["call_id"] for b in accepted if b["operation"] == "replace_expression"}
            attached = any(p["call_id"] in attachment_ids and not p["baseline"] and
                           p["body_sha256"] != start["target_body_sha256"] for p in observation["observer"])
            expected["exposure"] = expected["tool_dispatch"] = "TRUE" if backend else "UNKNOWN"
            expected["construction"] = "TRUE" if any(b["operation"].startswith("create_") and b["result_revision"] for b in accepted) else "FALSE"
            if observation["observer"]:
                expected["target_attachment"] = expected["connected_staging"] = "TRUE" if attached else "FALSE"
            expected["host_authorization"] = "FALSE" if refused else "TRUE" if commits else "UNKNOWN"
            published = bool(commits and commits[-1]["generation"] and commits[-1]["result_revision"] ==
                             end["project_revision"] == states["stored_current_revision"])
            expected["publication"] = "TRUE" if published else "FALSE" if refused and not commits else "UNKNOWN"
            evaluation = observation["evaluation"]
            for check in evaluation.values():
                ref = check["evidence"]
                if ref["source"] in sources:
                    original = e.pointer(sources[ref["source"]], ref["pointer"])
                    assert check["exit"] == original["exit"]
                    assert check["stdout_sha256"] == e.sha(original.get("stdout", "").encode())
                    assert check["stderr_sha256"] == e.sha(original.get("stderr", "").encode())
            task = evaluation.get("goal", evaluation.get("execution"))
            tests = "UNKNOWN" if task is None else "PASS" if task["exit"] == 0 else "FAIL"
            assert observation["evaluation_identity"]["explicit_revision_receipt"] is None
            expected["independent_published_behavior"] = "UNKNOWN"
            staged = "NOT_INDEPENDENTLY_EVALUATED"
            if attached and refused: label = "CONNECTED_NOT_PUBLISHED"
            elif published and start["target_body_sha256"] == end["target_body_sha256"]: label = "PUBLISHED_WITHOUT_TARGET_CHANGE"
            elif published and tests == "PASS": label = "PUBLISHED_TESTS_PASS_IDENTITY_RECEIPT_UNAVAILABLE"
            else: label = "UNKNOWN"
        for evaluator in ("E0", "E1"):
            assert result[evaluator]["stages"] == expected
            assert result[evaluator]["classification"] == label
            assert result[evaluator]["task_tests"] == tests
            assert result[evaluator]["staged_behavior"] == staged
        raw_complete = not observation["model_unit"] or observation["availability"]["status"] == "ARCHIVE_VERIFIED"
        sufficient = raw_complete and label != "UNKNOWN" and (not observation["model_unit"] or
            expected["publication"] == "FALSE" or observation.get("evaluation_identity", {}).get("explicit_revision_receipt") is not None)
        assert result["archive_available"] == raw_complete
        assert result["full_chain_evidence_sufficient"] == sufficient
        records.append({"id": observation["id"], "propositions_independently_recomputed": True,
                        "raw_archive_reopened": access[observation["id"]]["status"] == "ARCHIVE_VERIFIED"})
    assert comparison["actual_disagreement_count"] == sum(r["E0"] != r["E1"] for r in comparison["rows"])
    complete = all(r["full_chain_evidence_sufficient"] for r in comparison["rows"])
    expected_disposition = ("INCONCLUSIVE_EVIDENCE_LIMITATION" if not complete else
        "OBSERVED_INCREMENTAL_MEASUREMENT_VALUE" if comparison["actual_disagreement_count"] else "NO_OBSERVED_INCREMENTAL_VALUE")
    assert comparison["disposition"] == expected_disposition
    assert comparison["model_generation_calls"] == comparison["input_token_api_calls"] == 0
    assert comparison["next_model_experiment"] == "NOT_AUTHORIZED"
    return {"status": "PASS_WITH_EXPLICIT_EVIDENCE_LIMITATIONS", "mode": "RAW_AND_PUBLIC" if raw else "PUBLIC_CERTIFICATE_ONLY",
            "records": records, "source_pointers_checked": checked, "private_pointers_not_reopened": private_unchecked,
            "raw_validation_complete": private_unchecked == 0, "historical_scores_changed": False,
            "no_model_denominator_or_pooled_success_rate": True, "independent_of_analyzer_implementation": True}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for uid in ("U2", "U3", "U4"):
        p.add_argument("--" + uid.lower(), type=Path)
    args = p.parse_args()
    print(json.dumps(validate(json.loads((e.HERE / "OBSERVATIONS.json").read_bytes()),
        json.loads((e.HERE / "E0-E1-COMPARISON.json").read_bytes()),
        {u: getattr(args, u.lower()) for u in ("U2", "U3", "U4")}), indent=2))
