"""Read-only archive projection. No evaluator, candidate execution or model SDK."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return sha(canonical(value))


def manifest():
    return json.loads((HERE / "INPUT-MANIFEST.json").read_bytes())


def public_sources():
    bank = {}
    for entry in manifest()["public_sources"]:
        data = subprocess.check_output(["git", "show", "HEAD:" + entry["path"]], cwd=ROOT)
        if sha(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise ValueError("PUBLIC_INPUT_IDENTITY_MISMATCH:" + entry["path"])
        bank[entry["path"]] = json.loads(data)
    return bank


def pointer(value, path):
    for part in path.strip("/").split("/") if path else []:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def ref(source, path, value):
    return {"source": source, "pointer": path, "record_sha256": identity(value)}


def read_archives(paths):
    bank, availability = {}, {}
    for unit in manifest()["units"]:
        uid, expected = unit["id"], unit["archive"]
        if expected is None:
            availability[uid] = {"status": "PUBLIC_RECORDS", "archive_required": False}
            continue
        path = paths.get(uid)
        if path is None:
            availability[uid] = {"status": "EVIDENCE_UNAVAILABLE", "reason": "ARCHIVE_NOT_SUPPLIED"}
            continue
        try:
            data = Path(path).read_bytes()
            if len(data) != expected["bytes"] or sha(data) != expected["sha256"]:
                raise ValueError("ARCHIVE_IDENTITY_MISMATCH")
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if len(names) != len(set(names)):
                    raise ValueError("DUPLICATE_ARCHIVE_MEMBER")
                for member in expected["members"]:
                    raw = z.read(member)
                    # Config carries task/test source; never inspect reasoning or
                    # expose these bytes in the public derived certificate.
                    key = uid + ":" + member
                    bank[key] = ([json.loads(line) for line in raw.splitlines()]
                                 if member.endswith(".jsonl") else json.loads(raw))
            availability[uid] = {"status": "ARCHIVE_VERIFIED", "sha256": expected["sha256"],
                                 "bytes": len(data), "selected_members": expected["members"]}
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            for key in list(bank):
                if key.startswith(uid + ":"):
                    del bank[key]
            availability[uid] = {"status": "EVIDENCE_UNAVAILABLE", "reason": type(exc).__name__ + ":" + str(exc)}
    return bank, availability


def envelope(response):
    return response.get("structuredContent", response.get("result")) or {}


def project(bank, availability):
    """No historical disposition, score, reference patch or private reasoning features."""
    units = []
    coverage_path = "benchmarks/native_mcp_skill/evidence/NATIVE-COVERAGE.json"
    coverage = bank[coverage_path]
    probes = []
    for ri, row in enumerate(coverage["rows"]):
        advertised = row["advertised_names"]
        for ci, call in enumerate(row["calls"]):
            if call["name"] in {"create_reference", "create_literal", "create_binary", "create_call", "replace_expression"}:
                probes.append({"operation": call["name"], "advertised_by_registry": call["name"] in advertised,
                    "isError": call["response"].get("isError"),
                    "response_sha256": identity(call["response"]),
                    "error_text": " ".join(t.get("text", "") for t in call["response"].get("content", []))[:500],
                    "evidence": ref(coverage_path, f"/rows/{ri}/calls/{ci}", call),
                    "advertised_evidence": ref(coverage_path, f"/rows/{ri}/advertised_names", advertised)})
    units.append({"id": "U1", "model_unit": False, "availability": availability["U1"], "coverage_probes": probes,
                  "missing": ["model stages not applicable: no model slot"], "backend": [], "frontend": [], "observer": []})
    for unit in manifest()["units"][1:]:
        uid, prefix = unit["id"], unit["historical_id"] + "/"
        row = {"id": uid, "model_unit": True, "availability": availability[uid],
               "coverage_probes": [], "backend": [], "frontend": [], "observer": [], "missing": []}
        source = uid + ":" + prefix + "linux.json"
        if source not in bank:
            row["missing"] = ["backend calls", "baseline/final target state", "publication", "independent evaluation", "observer"]
            units.append(row)
            continue
        linux = bank[source]
        for i, call in enumerate(linux["calls"]):
            request = call.get("request", {})
            params = request.get("params", {})
            if call.get("action") == "aep":
                args = call["arguments"]
                operation, arguments = args["tool"], {k: v for k, v in args.items() if k != "tool"}
                call_id = None
            elif request.get("method") == "tools/call":
                operation, arguments = params["name"], params.get("arguments", {})
                call_id = params.get("_meta", {}).get("callId")
            else:
                continue
            response = call["response"]
            row["backend"].append({"operation": operation, "call_id": call_id,
                "request_id": request.get("id"), "arguments_sha256": identity(arguments),
                "success": response.get("ok") if "ok" in response else (not response["isError"] if "isError" in response else None),
                "withheld": call.get("withheld", False), "response_sha256": identity(response),
                "result_revision": envelope(response).get("revision"),
                "generation": envelope(response).get("generation"),
                "problems": envelope(response).get("problems"),
                "evidence": ref(source, f"/calls/{i}", call)})
        record_source = uid + ":" + prefix + ("result.json" if uid == "U2" else "record.json")
        for i, event in enumerate(bank[record_source]["events"]):
            if event.get("method") not in {"item/started", "item/completed"}:
                continue
            item = event.get("params", {}).get("item", {})
            if item.get("type") not in {"mcpToolCall", "dynamicToolCall"}:
                continue
            # Only tool items. Never agentMessage/reasoning/analysis content.
            row["frontend"].append({"event": event["method"], "type": item["type"], "call_id": item["id"],
                "operation": item.get("tool"), "status": item.get("status"), "error": item.get("error"),
                "arguments_sha256": identity(item.get("arguments")),
                "evidence": ref(record_source, f"/events/{i}/params/item", item)})
        observer_source = uid + ":" + prefix + "observer.jsonl"
        for i, point in enumerate(bank.get(observer_source, [])):
            row["observer"].append({k: point[k] for k in ["call_id", "transaction_id", "after_operation", "baseline", "body_sha256"]} |
                                   {"evidence": ref(observer_source, f"/{i}", point)})
        target = "demo.model.touch_size"
        row["state"] = {}
        for phase in ("initial_authority", "final_authority"):
            value = linux[phase]
            row["state"][phase] = {"project_revision": value.get("project_revision"),
                "target_body_sha256": value.get("body_sha256", value.get("bodies", {}).get(target)),
                "bodies": value.get("bodies"), "evidence": ref(source, "/" + phase, value)}
        files = {p: base64.b64decode(data, validate=True) for p, data in linux["final_files"].items()}
        current = files.get("alva-air/current", b"").decode().splitlines()
        row["state"]["stored_current_revision"] = current[1] if len(current) == 2 else None
        row["state"]["final_file_hashes"] = {p: sha(b) for p, b in files.items()}
        row["state"]["file_evidence"] = ref(source, "/final_files", linux["final_files"])
        row["evaluation"] = {kind: {"exit": value["exit"], "stdout_sha256": sha(value.get("stdout", "").encode()),
                                      "stderr_sha256": sha(value.get("stderr", "").encode()),
                                      "evidence": ref(source, "/final/" + kind, value)}
            for kind, value in linux["final"].items() if isinstance(value, dict) and "exit" in value}
        # No record contains a standalone evaluation-revision receipt. Preserve
        # this limitation instead of manufacturing an observed revision field.
        row["evaluation_identity"] = {"explicit_revision_receipt": None,
            "relation": "CO_RECORDED_FINAL_FILES_AND_FINAL_EVALUATION",
            "evidence": ref(source, "/final", linux["final"])}
        row["missing"] = ["explicit independently echoed evaluated-revision receipt"]
        if not row["observer"]:
            row["missing"].append("per-operation staged target observer")
        if uid == "U2":
            row["missing"].append("backend bridge callId (only op_index/order and frontend IDs retained)")
        units.append(row)
    return {"schema": "rdr02-observations/v1", "units": units,
            "projection_excludes": ["historical_disposition", "scores", "private_reasoning", "reference_patches"],
            "model_generation_calls": 0, "input_token_api_calls": 0}
