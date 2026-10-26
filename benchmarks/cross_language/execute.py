from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from common import ROOT,HERE,Workbench,TOOLS,hashes,load,save,sha,evaluate
from controller import Controller,InfrastructureError,drive,simulated_validation
from prepare import RUNTIME
from tasks import TASKS
sys.path.insert(0,str(ROOT/"tests/integrations"))
from codex_native_test import AppServer


def host():
    env=dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR",None)
    env.pop("CODEX_PERMISSION_PROFILE",None)
    args=["-c","features.plugins=false","-c","features.shell_tool=false",
          "-c",'web_search="disabled"',"-c",'approval_policy="never"']
    if os.name=="nt":args += ["-c",'windows.sandbox="unelevated"']
    empty=RUNTIME/"host-empty"
    empty.mkdir(exist_ok=True)
    h=AppServer(shutil.which("codex"),env,empty,extra_args=args)
    c=Controller(h)
    c.rpc("initialize",{"clientInfo":{"name":"alva-cross-language","version":"1"},"capabilities":{"experimentalApi":True}})
    h.send({"method":"initialized","params":{}})
    return h,c,empty


def params(config,cwd):
    return {"cwd":str(cwd),"approvalPolicy":"never","sandbox":"read-only","ephemeral":True,
            "model":config["model"],"dynamicTools":TOOLS,
            "developerInstructions":"Use only the study tool supplied for this single task. Do not use native shell/edit, internet, other directories/sessions, skills, or delegation. No access to host references/evaluators. Finish within the provided limits. Your code is evaluated independently."}


def freeze():
    config=load(HERE/"CONFIG.json")
    tests=simulated_validation()
    h,c,empty=host()
    try:
        resolved=c.rpc("thread/start",params(config,empty))
        assert resolved["model"]==config["model"],resolved
        assert resolved["modelProvider"]==config["provider"],resolved
        tests["real_host_no_generation"]={"model":resolved["model"],"provider":resolved["modelProvider"]}
        try:c.rpc("turn/interrupt",{"threadId":resolved["thread"]["id"],"turnId":"no-model-turn-started"})
        except InfrastructureError:tests["real_rpc_error_handled"]=True
        else:raise AssertionError("Unexpected nonexistent-turn interrupt success")
    finally:h.close()
    save(HERE/"PREFLIGHT.json",tests)
    source_files=[p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name not in ("FREEZE.json",)]
    bind={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in source_files}
    bind["tests/integrations/codex_native_test.py"]=sha((ROOT/"tests/integrations/codex_native_test.py").read_bytes())
    bind["feasibility/native_api/run.py"]=sha((ROOT/"feasibility/native_api/run.py").read_bytes())
    binary=RUNTIME/("alva.exe" if os.name=="nt" else "alva")
    result={"status":"FROZEN_BEFORE_GENERATION","base_commit":"7ca5f44e8c4b01d24c416cef838c429f79046345",
            "config":config,"files":bind,"binary_sha256":sha(binary.read_bytes()),
            "schedule":load(HERE/"SCHEDULE.json"),"preflight":"PASS",
            "codex":subprocess.check_output([shutil.which("codex"),"--version"],text=True).strip(),
            "python":sys.version,"model_generation_calls_before_freeze":0,
            "toolchain_environment_keys":[k for k in ("USERPROFILE","ProgramFiles","ProgramFiles(x86)","INCLUDE","LIB","LIBPATH","CARGO_HOME","RUSTUP_HOME") if k in os.environ]}
    save(HERE/"FREEZE.json",result)
    print("FREEZE PASS. Commit/push before any generation.")


def run():
    frozen=load(HERE/"FREEZE.json")
    for name,digest in frozen["files"].items():assert sha((ROOT/name).read_bytes())==digest,name
    assert subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True)=="","Research must be clean"
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    upstream=subprocess.check_output(["git","rev-parse","@{upstream}"],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(["git","ls-remote","origin","refs/heads/codex/cross-language-coding-pilot"],cwd=ROOT,text=True).split()[0]
    assert head==upstream==remote,"Freeze not pushed"
    binary=RUNTIME/("alva.exe" if os.name=="nt" else "alva")
    assert sha(binary.read_bytes())==frozen["binary_sha256"]
    ledger=RUNTIME/"EXECUTION-STARTED.json"
    with ledger.open("x",encoding="utf-8") as f:json.dump({"freeze_commit":head,"started":True},f)
    rows=[]
    for slot in frozen["schedule"]:
        path=RUNTIME/"slots"/slot["id"]
        task=next(t for t in TASKS if t["id"]==slot["task"])
        assert sha((path/"input.json").read_bytes())==slot["input_sha256"]
        assert hashes(path/"candidate")==slot["initial_files"]
        record={"slot":slot["id"],"task":slot["task"],"arm":slot["arm"],"freeze_commit":head,
                "model_tasks_started":0,"provider_requests":None,"dollar_cost":None,"hard_token_cap":False}
        wb=Workbench(path/"candidate",slot["arm"],task,binary,path/"evidence")
        h=None
        print("START "+slot["id"],flush=True)
        try:
            h,c,empty=host()
            thread=c.rpc("thread/start",params(frozen["config"],empty))
            assert thread["model"]==frozen["config"]["model"]
            assert thread["modelProvider"]==frozen["config"]["provider"]
            record["resolved_model"]=thread["model"]
            record["resolved_provider"]=thread["modelProvider"]
            record["model_tasks_started"]=1
            turn=c.rpc("turn/start",{"threadId":thread["thread"]["id"],"input":[{"type":"text","text":(path/"input.json").read_text(encoding="utf-8")}],"effort":frozen["config"]["effort"],"approvalPolicy":"never","sandboxPolicy":{"type":"readOnly"}})
            c.bind(thread,turn)
            drive(c,wb,frozen["config"],record)
        except Exception as exc:
            record["infrastructure_hold"]=type(exc).__name__+": "+str(exc)
        finally:
            if h is not None:
                try:h.close()
                except Exception as exc:record["cleanup_error"]=str(exc)
            wb.close()
        record["accepted_source_edits"]=wb.edits
        record["successful_commits"]=wb.commits
        record["aep_calls"]=len(wb.aep)
        if slot["arm"]=="C":record["authoritative_files"]=hashes(path/"candidate/alva-air")
        save(path/"aep-tools.json",wb.aep)
        record["final"]=evaluate(path/"candidate",slot["arm"],task,binary,path/"terminal-build")
        if slot["arm"]=="C" and wb.commits==0:
            record["condition_disposition"]="NO_COMMITTED_CANDIDATE"
        record["final_files"]=hashes(path/"candidate"/"src") if slot["arm"]!="A" else {"program.py":sha((path/"candidate/program.py").read_bytes())}
        save(path/"result.json",record)
        rows.append(record)
        print("CLOSED "+slot["id"]+" "+record["final"]["status"],flush=True)
        save(RUNTIME/"progress.json",[{"slot":r["slot"],"closed":True} for r in rows])
        if record.get("infrastructure_hold"):break
    # No attempt to resume/retry a partially completed schedule here.
    public=[]
    for row in rows:
        cleaned=dict(row)
        cleaned.pop("tools",None)
        cleaned["tool_actions"]=[{k:v for k,v in t.items() if k not in ("arguments","response")} for t in row.get("tools",[])]
        public.append(cleaned)
        p=RUNTIME/"slots"/row["slot"]/"candidate"
        extension="py" if row["arm"]=="A" else "alva"
        src=p/"program.py" if extension=="py" else p/"src/task.alva"
        target=HERE/"final"/(row["slot"]+"."+extension)
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(src,target)
        if row["arm"]=="C" and (p/"alva-air/current").is_file():
            authority=p/"alva-air"
            generation=(authority/"current").read_text(encoding="utf-8").splitlines()[0]
            public_authority=HERE/"final"/row["slot"]/"alva-air"
            public_authority.mkdir(parents=True,exist_ok=True)
            for name in ("current",f"gen-{generation}.air"):
                shutil.copy2(authority/name,public_authority/name)
        # C source is intentionally only the original projection; retain native tool
        # evidence and authoritative bytes privately, not misleading text as final code.
    text=json.dumps(public,ensure_ascii=False,indent=2)
    for value,label in ((str(ROOT),"<REPO>"),(str(RUNTIME),"<RUNTIME>")):
        text=text.replace(json.dumps(value)[1:-1],label)
    (HERE/"RESULTS.json").write_text(text+"\n",encoding="utf-8")
    archive=ROOT/".local/CROSS-LANGUAGE-EVIDENCE.zip"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for p in sorted(RUNTIME.rglob("*")):
            rel=p.relative_to(RUNTIME)
            if p.is_file() and not any(x in rel.parts for x in ("target","qualification","build","terminal-build","__pycache__")) and p!=binary:
                z.write(p,rel.as_posix())
    save(HERE/"ARCHIVE.json",{"sha256":sha(archive.read_bytes()),"bytes":archive.stat().st_size,
                              "entries":len(zipfile.ZipFile(archive).namelist()),"local_only":True,"raw_reasoning_saved":False})
    print("STOP. Executed positions: "+str(len(rows)),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=("freeze","run"));args=parser.parse_args()
    freeze() if args.mode=="freeze" else run()
