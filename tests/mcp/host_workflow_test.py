#!/usr/bin/env python3
"""Real Core/P34/Host lifecycle controls; evaluator fault injection is explicit.

These controls do not claim real behavioral qualification. The separate Linux
host_workflow_linux.py exercises the actual isolated evaluator on four tasks.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.codex.maintenance_host import AgentProcess, MaintenanceHost, TOOLS, project_source_loader, snapshot_digest, serve


class ReceiptEvaluator:
    def __init__(self):
        self.version = "controlled-evaluator-v1"
        self.fail = self.wrong_receipt = False
        self.snapshots = []
    def identity(self): return self.version
    def __call__(self, files, revision):
        self.snapshots.append(dict(files))
        return {"status":"FAIL" if self.fail else "PASS", "project_revision":revision,
                "tested_snapshot_sha256":"wrong" if self.wrong_receipt else snapshot_digest(files),
                "checks":{"check":"PASS","build":"PASS","test":"FAIL" if self.fail else "PASS"}}


def fixture(directory):
    root = Path(directory)
    (root / "alva.toml").write_text('[project]\nname="host_demo"\n[modules]\nm="m.alva"\n', encoding="utf-8")
    (root / "m.alva").write_text('''(module (name "m") (version "1") (export a b)
      (fn a (params) (returns (prim i64)) (pure) (body (int 1)))
      (fn b (params) (returns (prim i64)) (pure) (body (int 1))))''', encoding="utf-8")
    return {"authorized_functions":["m.a"], "modules":{"m":{"functions":["a","b"],"types":[]}}}


def controls(binary):
    checks = []
    def scenario(name, run):
        with tempfile.TemporaryDirectory(prefix="host-control-") as directory:
            root = Path(directory); policy = fixture(root); evaluator = ReceiptEvaluator()
            host = MaintenanceHost(lambda:AgentProcess(binary), root / "alva.toml", policy,
                                   project_source_loader(root / "alva.toml", ["alva.toml","m.alva"]), evaluator)
            try: run(host, root, evaluator)
            finally: host.close()
        checks.append(name)
    def prepare(h, body="(body (int 2))"):
        view = h.invoke("read_target", {"function":"m.a"})
        assert view["status"] == "READY", view
        proposal = h.invoke("prepare_change", {"view_id":view["view_id"],"body":body})
        assert proposal["status"] == "PREPARED", proposal
        return view, proposal

    def happy(h, root, e):
        source = (root / "m.alva").read_bytes()
        view, p = prepare(h)
        assert len(e.snapshots) == 1
        assert not (root / "alva-air/current").exists(), "prepare must not publish"
        assert e.snapshots[0]["m.alva"] == source
        assert "alva-air/gen-1.air" in e.snapshots[0]
        published = h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
        assert published["status"] == "PUBLISHED", published
        assert published["commit"]["host_scope"]["status"] == "SCOPE_ALLOWED"
        assert published["commit"]["host_scope"]["changed_functions"] == ["m.a"]
        assert published["fresh_authority_matches"]
        assert (root / "m.alva").read_bytes() == source
        before = (root / "alva-air/current").read_bytes()
        assert h.invoke("publish_change", {"proposal_id":p["proposal_id"]})["status"] == "REJECTED"
        assert (root / "alva-air/current").read_bytes() == before
        assert "air_hex" not in json.dumps([view,p,published])
    scenario("actual Guard commit, fresh AIR, draft isolation, no source rewrite, single use", happy)

    def failure(h, root, e):
        v,p = prepare(h)
        e.fail = True
        rejected = h.invoke("prepare_change", {"view_id":v["view_id"],"body":"(body (int 3))"})
        assert rejected["status"] == "VALIDATION_FAILED", rejected
        assert h.invoke("publish_change", {"proposal_id":p["proposal_id"]})["status"] == "REJECTED"
        assert not (root / "alva-air/current").exists()
    scenario("failed tests invalidate older passing proposal", failure)

    def wrong(h, root, e):
        e.wrong_receipt = True
        v=h.invoke("read_target", {"function":"m.a"})
        p=h.invoke("prepare_change", {"view_id":v["view_id"],"body":"(body (int 2))"})
        assert p["status"] == "UNVERIFIED_TEST_RECEIPT", p
        assert not (root / "alva-air/current").exists()
    scenario("mismatched isolated receipt cannot authorize publication", wrong)

    def malformed(h, root, e):
        v,p=prepare(h)
        r=h.invoke("prepare_change", {"view_id":v["view_id"],"body":"(body (string \"bad\"))"})
        assert r["status"] == "REJECTED" and "E_TYPE_001" in r["reason"], r
        assert h.invoke("publish_change", {"proposal_id":p["proposal_id"]})["status"] == "REJECTED"
        assert len(e.snapshots) == 1
        r=h.invoke("prepare_change", {"view_id":v["view_id"],"body":"(body (int 4))"})
        assert r["status"] == "PREPARED", r
        assert h.invoke("publish_change", {"proposal_id":r["proposal_id"]})["status"] == "PUBLISHED"
    scenario("semantic error atomicity and same-view recovery", malformed)

    def invalid_arguments(h, root, e):
        v,p=prepare(h)
        assert h.invoke("prepare_change", {"view_id":v["view_id"],"body":"x","authorized_functions":["m.b"]})["status"] == "REJECTED"
        assert h.invoke("publish_change", {"proposal_id":p["proposal_id"]})["status"] == "REJECTED"
        assert h.invoke("export_transaction", {})["status"] == "REJECTED"
        assert h.invoke("read_target", {"function":"m.b"})["status"] == "REJECTED"
        assert not (root / "alva-air/current").exists()
    scenario("argument/policy and raw Native bypasses closed", invalid_arguments)

    def changed(h, root, e):
        v,p=prepare(h)
        info=h._call("read_function",function="m.a")
        h._call("replace_function_body",function="m.a",expected_body_revision=info["body_revision"],body="(body (int 9))")
        result=h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
        assert result["reason"] == "DRAFT_OR_TEST_IDENTITY_CHANGED", result
        assert not (root / "alva-air/current").exists()
    scenario("draft tampering after tests rejected", changed)

    def identity(h, root, e):
        _,p=prepare(h);e.version="changed-suite"
        result=h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
        assert result["reason"] == "DRAFT_OR_TEST_IDENTITY_CHANGED", result
        assert not (root / "alva-air/current").exists()
    scenario("suite/toolchain identity change rejected", identity)

    def source(h, root, e):
        _,p=prepare(h)
        (root / "m.alva").write_bytes((root / "m.alva").read_bytes()+b"\n;; external edit\n")
        r=h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
        assert r["reason"] == "SOURCE_CHANGED_READ_TARGET", r
        assert not (root / "alva-air/current").exists()
    scenario("source/manifest change rejected before Native commit", source)

    def scope(h, root, e):
        v=h.invoke("read_target", {"function":"m.a"})
        other=h._call("read_function",function="m.b")
        h._call("replace_function_body",function="m.b",expected_body_revision=other["body_revision"],body="(body (int 9))")
        r=h.invoke("prepare_change", {"view_id":v["view_id"],"body":"(body (int 2))"})
        assert r["status"] == "SCOPE_VIOLATION", r
        assert not e.snapshots
        assert not (root / "alva-air/current").exists()
    scenario("actual P34 unauthorized draft refusal before evaluation", scope)

    def stale(h, root, e):
        peer=MaintenanceHost(lambda:AgentProcess(binary),root / "alva.toml",h.policy,h.sources,ReceiptEvaluator())
        try:
            _,p=prepare(h);_,q=prepare(peer, "(body (int 3))")
            assert peer.invoke("publish_change", {"proposal_id":q["proposal_id"]})["status"] == "PUBLISHED"
            before=(root / "alva-air/current").read_bytes()
            r=h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
            assert r["status"] == "PUBLISH_REJECTED" and "E_AEP_CONFLICT" in r["reason"],r
            assert (root / "alva-air/current").read_bytes() == before
        finally: peer.close()
    scenario("competing publication rejects stale base without rebase", stale)

    def expired(h, root, e):
        _,p=prepare(h);h.view["expires"]=-1
        r=h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
        assert r["reason"] == "VIEW_EXPIRED_READ_TARGET", r
        assert not (root / "alva-air/current").exists()
    scenario("expired view/proposal cannot publish", expired)

    def fresh_failure(h, root, e):
        _,p=prepare(h)
        def unavailable(): raise RuntimeError('controlled fresh process failure')
        h.factory=unavailable
        r=h.invoke("publish_change", {"proposal_id":p["proposal_id"]})
        assert r['status']=='PUBLISHED_UNVERIFIED' and r['commit']['revision'], r
        assert (root/'alva-air/current').exists()
        assert h.invoke('publish_change', {'proposal_id':p['proposal_id']})['status']=='BLOCKED'
    scenario("fresh reader failure preserves actual commit receipt and blocks retry", fresh_failure)

    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);policy=fixture(root)
        config={"alva":str(binary),"project":str(root/'alva.toml'),"inputs":["alva.toml","m.alva"],
                "policy":policy,"crate":"host_demo","toolchain":str(root),"registry":str(root)}
        path=root/'host-config.json';path.write_text(json.dumps(config))
        proc=subprocess.Popen([sys.executable,'-m','integrations.codex.maintenance_host','--config',str(path)],cwd=ROOT,
                              stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        reqs=[{"jsonrpc":"2.0","id":i,"method":method,"params":params} for i,(method,params) in enumerate([
            ('initialize',{}),('tools/list',{}),('tools/call',{'name':'read_target','arguments':{'function':'m.a'}}),
            ('tools/call',{'name':'export_transaction','arguments':{}})],1)]
        out,err=proc.communicate(''.join(json.dumps(r)+'\n' for r in reqs),timeout=20)
        assert proc.returncode == 0,err
        replies=[json.loads(line) for line in out.splitlines()]
        assert [t['name'] for t in replies[1]['result']['tools']] == ['read_target','prepare_change','publish_change']
        assert replies[2]['result']['structuredContent']['status']=='READY',replies
        assert replies[3]['result']['isError']
        assert not (root/'alva-air/current').exists()
    checks.append('actual three-tool MCP STDIO entry, no private AEP exposure')
    schema=[{'type':'function','function':{'name':t['name'],'description':t['description'],'parameters':t['inputSchema']}} for t in TOOLS]
    assert len(json.dumps(schema).encode()) < 4281
    print(json.dumps({"status":"PASS","controls":checks,"model_tools":3,
                      "schema_utf8_bytes":len(json.dumps(schema).encode()),"model_generation_calls":0},indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('binary',type=Path)
    controls(p.parse_args().binary.resolve())
