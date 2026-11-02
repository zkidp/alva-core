"""Read-only manuscript consistency checks, not a scientific/behavioral oracle."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def pointer(value, path):
    for key in path.strip("/").split("/"):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def check():
    manifest = json.loads((HERE / "evidence.json").read_bytes())
    assert manifest["canonical_base"] == "469358649e256ddff8c37baf421def25abc11671"
    identifiers = {e["id"].lower() for e in manifest["sources"]}
    assert len(identifiers) == len(manifest["sources"]) == 32
    facts = 0
    for entry in manifest["sources"]:
        data = subprocess.check_output(["git", "show", "HEAD:" + entry["path"]], cwd=ROOT)
        assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"], entry["id"]
        assert re.fullmatch(r"[0-9a-f]{40}", entry["last_change_commit"])
        for assertion in entry["facts"]:
            assert pointer(json.loads(data), assertion["pointer"]) == assertion["expected"], assertion
            facts += 1
    links = 0
    for file in HERE.glob("*.md"):
        text = file.read_text(encoding="utf-8")
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in link:
                continue  # Network availability is not a manuscript build dependency.
            path, _, fragment = link.partition("#")
            target = file.parent / path if path else file
            assert target.is_file(), (file.name, link)
            if fragment:
                content = target.read_text(encoding="utf-8")
                assert f'id="{fragment}"' in content, (file.name, link)
            links += 1
    paper = (HERE / "manuscript.md").read_text(encoding="utf-8")
    for section in ("Abstract", "Introduction", "Related Work", "System Design", "Case Study", "Evaluation", "Threats to Validity", "Discussion", "Conclusion"):
        assert re.search(r"^## .*" + section, paper, re.M), section
    assert len(paper.split()) >= 3000, "Full draft, not only an outline"
    assert not re.search(r"\b(TODO|TBD|PLACEHOLDER)\b", paper)
    assert set(re.findall(r"evidence\.md#(e\d+)", paper)) <= identifiers
    assert set(re.findall(r"references\.md#([a-z]+)", paper)) == {
        "sweagent", "codestruct", "serena", "openrewrite", "plump", "git", "taubench", "verifiedcalls", "aft"}
    spec = importlib.util.spec_from_file_location("paper_figures", HERE / "render_figures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, expected in module.figures().items():
        data = (HERE / "figures" / name).read_bytes()
        assert data == expected.encode("utf-8"), name
        svg = ET.fromstring(data)
        assert svg.find("{http://www.w3.org/2000/svg}title") is not None
        assert svg.find("{http://www.w3.org/2000/svg}desc") is not None
        assert not svg.findall(".//{http://www.w3.org/2000/svg}script")
    return {"status": "PASS", "public_sources": len(identifiers), "json_facts": facts,
            "local_links": links, "figures": 3, "model_experiments_started": 0,
            "scope": "public-byte/proposition/link/render consistency only; not independent prose or oracle review"}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
