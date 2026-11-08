"""Seal the final DNS-routed wave without changing either prior HOLD."""
import argparse
import json
from pathlib import Path
import zipfile

from benchmarks.context_flash_resume.analyze import describe
from benchmarks.context_flash_resume.runner import HERE
from benchmarks.context_flash_pilot.freeze import HERE as ORIGINAL, ROOT
from integrations.codex.maintenance_host import sha


def main(args):
    batch = json.loads((args.directory / "RESULTS.json").read_bytes())
    original = json.loads(args.original.read_bytes())
    second = json.loads(args.second.read_bytes())
    # Only for the descriptive existing analyzer's completion branch; the raw
    # seven-slot status remains exactly as written by its actual controller.
    analytical = dict(batch, status="COMPLETED_REMAINING_SLOTS" if batch["status"] == "COMPLETED_SEVEN_REMAINING" else "HOLD")
    result = describe(analytical, original)
    result["status"] = batch["status"]
    result["previous_second_wave"] = {"slot": "Q01-B", "status": second["status"], "requests_submitted": second["provider_requests_submitted"],
        "received_responses": len(second["rows"][0].get("requests", [])), "reason": "URLError -> gaierror errno 11001 (DNS)"}
    result["Q01_B_also_censored"] = True
    result["prior_unknown_usage_attempts"] = 2
    result["all_scientific_total_tokens"] = None
    result["classification"] = "DESCRIPTIVE_PARTIAL_CONTINUATION_ONLY" if batch["status"] == "COMPLETED_SEVEN_REMAINING" else "INCONCLUSIVE_INFRASTRUCTURE_HOLD"
    result["amendment_commit"] = batch["amendment_commit"]
    result["non_scientific_canary_requests_all_waves"] = 6
    result["full_original_screen_evaluable"] = False
    result["transport_note"] = "Process-local validated DNS route; no global DNS changes, TLS bypass, or request retry. Not a permanent OS DNS repair."
    (HERE / "DNS-RESULTS.json").write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    f = json.loads((ORIGINAL / "FREEZE.json").read_bytes())
    a = json.loads((HERE / "DNS-CONTINUATION-FREEZE.json").read_bytes())
    for path, expected in {**f["runtime"], **a["controller_files"]}.items():
        data = (ROOT / path).read_bytes()
        if sha(data) != expected: raise RuntimeError("ARCHIVE_RUNTIME_DRIFT:" + path)
        target = args.directory / "runtime-snapshot" / path
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    archive = args.directory.parent / (args.directory.name + ".zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(args.directory.rglob("*")):
            if path.is_file(): stream.write(path, path.relative_to(args.directory).as_posix())
    (HERE / "DNS-ARCHIVE.json").write_bytes(json.dumps({"archive": archive.name, "sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "entries": {p.relative_to(args.directory).as_posix(): sha(p.read_bytes()) for p in sorted(args.directory.rglob("*")) if p.is_file()}}, indent=2).encode() + b"\n")
    print(json.dumps({k: result[k] for k in ("status", "eligible_AC_pairs", "descriptive_median_C_over_A", "descriptive_worst_C_over_A", "continuation_requests_submitted")}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--second", type=Path, required=True)
    main(p.parse_args())
