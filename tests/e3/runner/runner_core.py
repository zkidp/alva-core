"""Shared E3 runner core: frozen-workspace creation, gates, recording,
arm-blind verifier, provenance, call-log schema, termination mapping.

Implements the frozen runner principles (see research-private
e3-feasibility/NO-MODEL-REHEARSAL-PLAN.md and METADATA-LEAKAGE-AUDIT.md).
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
QUALIFY_DIR = os.path.dirname(HERE) + os.sep + "qualify"
VERIFIER = os.path.join(QUALIFY_DIR, "hidden_verifier.py")
CHURN = (r"C:\Users\BEStaff\Desktop\alva-repos\alva-research-private"
         r"\alva-paper\saner\e3-feasibility\scripts\churn_classifier.py")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fixture_tree_sha256(fixture_dir):
    h = hashlib.sha256()
    for root, _, files in os.walk(fixture_dir):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, fixture_dir).replace("\\", "/")
            h.update(rel.encode())
            h.update(sha256_file(fp).encode())
    return h.hexdigest()


def load_freeze_manifest(path):
    """Parse C1-FREEZE-MANIFEST.md -> {cid: (manifest_sha, tree_sha)}."""
    text = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"^\| (M\d\d|N\d\d) \| `(\w{64})` \| `(\w{64})` \|",
                         text, re.M):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


def make_workspace(cid, candidates_dir, freeze_manifest, out_root):
    """Create a run workspace from the C1-frozen fixture ONLY."""
    fixture_dir = os.path.join(candidates_dir, cid, "fixture")
    if not os.path.isdir(fixture_dir):
        raise RuntimeError(f"fixture missing for {cid}")
    live_tree = fixture_tree_sha256(fixture_dir)
    expected_tree = freeze_manifest[cid][1]
    if live_tree != expected_tree:
        raise RuntimeError(
            f"{cid} fixture tree hash {live_tree[:12]} != frozen "
            f"{expected_tree[:12]} -- refusing to run on drifting input")
    run_root = tempfile.mkdtemp(prefix=f"e3-{cid}-")
    ws = os.path.join(run_root, "workspace")
    shutil.copytree(fixture_dir, ws)
    # workspace allowlist: fixture files only
    leaked = []
    for root, _, files in os.walk(ws):
        for fn in files:
            if fn in ("candidate.json", "hidden_verifier.py",
                      "QUALIFICATION-RECORD.jsonl") or fn.endswith(".json"):
                leaked.append(os.path.join(root, fn))
    if leaked:
        raise RuntimeError(f"workspace leak in {cid}: {leaked}")
    return run_root, ws, fixture_tree_sha256(ws)


def extract_high_call(manifest):
    """Derive the frozen HIGH call for a MATCHED candidate from its
    qualified LOW sequence (add_param + the create_literal used for the
    call-site argument)."""
    ops = manifest["low_sequence"]["ops"]
    add = next((o for o in ops if o["tool"] == "add_param"), None)
    if add is None:
        return None
    arg_key = next((o.get("as") for o in ops if o["tool"] == "create_literal"
                    and o.get("as")), None)
    lit = next((o for o in ops if o["tool"] == "create_literal"
                and o.get("as") == arg_key), None)
    high = {
        "tool": "migrate_signature",
        "args": {
            "function": add["args"]["function"],
            "param": add["args"]["name"],
            "type": add["args"]["type"],
        },
    }
    if lit is not None:
        high["args"]["value"] = lit["args"]["value"]
    return high


class RecordingAgent:
    """Agent protocol driver that records every call for the frozen churn
    classifier (raw facts only; churn is derived later, never online)."""

    def __init__(self, alva, project_toml, gate_on, call_log):
        env = dict(os.environ)
        if gate_on:
            env["ALVA_AEP_ENABLE_E3_HIGH"] = "1"
        else:
            env.pop("ALVA_AEP_ENABLE_E3_HIGH", None)
        env.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")
        self.p = subprocess.Popen(
            [alva, "agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", env=env)
        self.project = project_toml
        self.gate_on = gate_on
        self.call_log = call_log
        self.session_id = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        self.ordinal = 0

    def call(self, tool, **kw):
        self.ordinal += 1
        msg = {"request_id": str(self.ordinal), "tool": tool}
        msg.update(kw)
        started = time.time()
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        elapsed = round(time.time() - started, 3)
        if not line.strip():
            raise RuntimeError("agent process closed")
        r = json.loads(line)
        output_rev = None
        res = r.get("result")
        if isinstance(res, dict):
            output_rev = (res.get("revision") or res.get("new_revision")
                          or res.get("entity"))
        self.call_log.append({
            "ordinal": self.ordinal,
            "tool": tool,
            "args": kw,
            "ok": bool(r.get("ok")),
            "error_code": r.get("error_code"),
            "message": r.get("message"),
            "result": res,
            "output_revision": output_rev,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           time.gmtime()),
            "elapsed_s": elapsed,
            "session_id": self.session_id,
        })
        return r

    def ok(self, tool, **kw):
        r = self.call(tool, **kw)
        if not r.get("ok"):
            raise RuntimeError(f"{tool} {kw} -> {r.get('message')}")
        return r

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def surface_probe(a, project_toml):
    """Per-run runtime surface assertion: with the E3 gate OFF the compound
    op must be invisible/inert; with the gate ON it must be dispatched
    (reaching entity resolution). Also verifies a transaction exists."""
    a.ok("begin_transaction", project=project_toml)
    r = a.call("migrate_signature", function="__e3_probe__", param="x",
               type="i64", value="1")
    if a.gate_on:
        if r.get("ok") or r.get("error_code") == "E_AEP_UNKNOWN_TOOL":
            raise RuntimeError("surface gate: HIGH arm did not expose "
                               "migrate_signature")
    else:
        if r.get("error_code") != "E_AEP_UNKNOWN_TOOL":
            raise RuntimeError("surface gate: LOW arm exposed "
                               "migrate_signature")
    return True


def run_verifier_arm_blind(alva, project_dir, checkspec, baseline):
    """Invoke the hidden verifier with ONLY workspace + host checkspec.
    The arm is never passed; the checkspec and baseline are supplied
    host-side in a scratch dir."""
    spec_dir = tempfile.mkdtemp(prefix="verify-")
    with open(os.path.join(spec_dir, "checkspec.json"), "w",
              encoding="utf-8") as fh:
        json.dump(checkspec, fh)
    if baseline is not None:
        with open(os.path.join(spec_dir, "baseline.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(baseline, fh)
    p = subprocess.run(
        [sys.executable, VERIFIER, project_dir, spec_dir],
        env=dict(os.environ, ALVA=alva), capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr)[-400:]


def derive_churn(call_log, final_reachable):
    """Feed the RAW call log to the frozen churn classifier; the derived
    score is a derived artifact, never the primary storage."""
    traj = {
        "calls": [{"tool": c["tool"], "ok": c["ok"],
                   "output_revision": c.get("output_revision")}
                  for c in call_log],
        "final_reachable_revisions": list(final_reachable or []),
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(traj, fh)
    p = subprocess.run([sys.executable, CHURN, path],
                       capture_output=True, text=True)
    os.unlink(path)
    return p.returncode, (p.stdout + p.stderr)


def provenance_record(cid, group, arm, rep, alva_bin, runner_head,
                      fixture_hash, workspace_hash, gate_env, model, start,
                      end, termination, out_dir):
    rec = {
        "task_id": cid,
        "group": group,
        "arm": arm,
        "rep": rep,
        "source_commit": _git_head(),
        "binary_sha256": sha256_file(alva_bin),
        "fixture_hash": fixture_hash,
        "workspace_pre_run_hash": workspace_hash,
        "gate_env": gate_env,
        "model_provider": model.get("provider"),
        "model_identifier": model.get("identifier"),
        "model_settings": model.get("settings"),
        "runner_commit": runner_head,
        "container_image": model.get("image"),
        "started_utc": start,
        "ended_utc": end,
        "termination": termination,
    }
    return rec


def _git_head():
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"],
                           capture_output=True, text=True, cwd=HERE)
        return p.stdout.strip()
    except Exception:
        return "unknown"
