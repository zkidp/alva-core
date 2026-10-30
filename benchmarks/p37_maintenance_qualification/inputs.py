"""Allowlisted future inputs only; this is not a model runner or authorization."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import decode

HERE = Path(__file__).parent


def model_inputs(ident, condition):
    if ident not in ("MM04", "MM05", "MM06", "MM07") or condition not in ("T", "S"):
        raise ValueError("Explicit registered ID and condition required")
    task = json.loads((HERE / "public" / ident / "task.json").read_text())
    bundle = json.loads((HERE / "TASK-BUNDLES.json").read_text())[ident]
    docs = json.loads((HERE / "APPROVED-DOCS.json").read_text())
    files = decode(docs, docs["payload_sha256"])
    approved = {"language.md": files["alva/README.md"]}
    if condition == "S":
        approved.update({p.removeprefix("integrations/skills/alva/"): b for p, b in files.items() if p.startswith("integrations/skills/alva/")})
    return {"public_task": task, "project": decode(bundle, bundle["payload_sha256"]), "approved_docs": approved}
