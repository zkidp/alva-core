from __future__ import annotations
import gzip
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

from common import ROOT,HERE,Agent,TOOLS,construct,evaluate,hashes,save,sha
from tasks import TASKS,source

RUNTIME=ROOT/".local/cross-language-execution"
MODEL="gpt-5.6-sol"
CONFIG={"model":MODEL,"provider":"openai","effort":"low","wall_observation_seconds":480,
        "tool_callback_limit":80,"token_observation_threshold":120000,"interrupt_grace_seconds":20,
        "hard_provider_token_cap":False,"concurrency":1,"model_turns_per_slot":1,
        "provider_generation_requests":None,"dollar_cost":None}
COMMON="Use only the study tool; do not use shell, native file tools, internet, other sessions, delegation, or references. Implement solve for all supported inputs, not only examples. Checks/tests execute host-owned code. You may iterate within the fixed limits, then finish. No automatic source publishing or Git operations."


def main():
    assert not RUNTIME.exists(),"Never overwrite prepared/executed positions"
    RUNTIME.mkdir(parents=True)
    binary=RUNTIME/("alva.exe" if sys.platform=="win32" else "alva")
    supplied=Path(sys.argv[1]).resolve()
    shutil.copy2(supplied,binary)
    upstream=ROOT/".local/human-eval"
    assert subprocess.check_output(["git","-C",str(upstream),"rev-parse","HEAD"],text=True).strip()=="b9453e8f1865df0a0057a1383767caa400acfbcf"
    items={t["task_id"]:t for t in map(json.loads,gzip.open(upstream/"data/HumanEval.jsonl.gz","rt",encoding="utf-8"))}
    shutil.copy2(upstream/"LICENSE",HERE/"HUMANEVAL-LICENSE.txt")
    provenance=[]
    qualifications=[]
    for task in TASKS:
        upstream_task=items[f'HumanEval/{task["id"]}']
        provenance.append({k:upstream_task[k] for k in ("task_id","entry_point","prompt")})
        row={"task":task["id"],"feature":task["feature"],"supported":False}
        try:
            for arm in "ABC":
                p=RUNTIME/"qualification"/str(task["id"])/arm
                (p/"src").mkdir(parents=True)
                (p/"alva.toml").write_text('[project]\nname="bench"\n[modules]\n"bench"="src/task.alva"\n',encoding="utf-8")
                (p/"src/task.alva").write_text(source(task),encoding="utf-8")
                (p/"program.py").write_text(f'def solve({task["argument"]}):\n    return {task["py_stub"]}\n',encoding="utf-8")
                before=evaluate(p,arm,task,binary,p/"out")
                assert before["status"]=="TEST_FAIL",before
                if arm=="A":
                    (p/"program.py").write_text(f'def solve({task["argument"]}):\n'+"\n".join("    "+line for line in task["py"].splitlines())+"\n",encoding="utf-8")
                elif arm=="B":(p/"src/task.alva").write_text(source(task,task["expr"]),encoding="utf-8")
                else:
                    trace=[]
                    agent=Agent(binary,p,trace,"qualification")
                    try:
                        agent.result("applicable_operations",entity="bench.solve")
                        for name in ("replace_expression","construct_expression","create_call","create_binary"):
                            agent.result("describe_operation",name=name)
                        for kind in ("fold","veclit"):agent.result("describe_construction",kind=kind)
                        fn=agent.result("inspect_entity",entity="bench.solve")
                        expression=construct(agent,task["expr"])
                        agent.result("replace_expression",parent=fn["slots"]["body"][0],child=expression,position="step")
                        agent.result("check_transaction")
                        agent.result("commit_transaction")
                    finally:agent.close()
                    save(p/"trace.json",trace)
                after=evaluate(p,arm,task,binary,p/"out")
                assert after["status"]=="PASS",after
                row[arm]={"baseline":before["status"],"reference":after["status"]}
            row["supported"]=True
        except Exception as exc:row["reason"]=str(exc)
        qualifications.append(row)
    save(HERE/"PROVENANCE.json",provenance)
    save(HERE/"QUALIFICATION.json",qualifications)
    assert all(r["supported"] for r in qualifications),"UNSUPPORTED adaptation recorded; no substitution/model execution"
    schedule=[{"task":t["id"],"arm":a} for t in TASKS for a in "ABC"]
    random.Random(20261027).shuffle(schedule)
    for i,slot in enumerate(schedule,1):
        slot["id"]=f'{i:02d}-HE{slot["task"]}-{slot["arm"]}'
        t=next(t for t in TASKS if t["id"]==slot["task"])
        path=RUNTIME/"slots"/slot["id"]
        project=path/"candidate"
        (project/"src").mkdir(parents=True)
        if slot["arm"]=="A":
            (project/"program.py").write_text(f'def solve({t["argument"]}):\n    return {t["py_stub"]}\n',encoding="utf-8")
        else:
            (project/"src/task.alva").write_text(source(t),encoding="utf-8")
            (project/"alva.toml").write_text('[project]\nname="bench"\n[modules]\n"bench"="src/task.alva"\n',encoding="utf-8")
        language="Python" if slot["arm"]=="A" else "ALVA"
        instructions="Ordinary source edit is available; use read/edit/check/test."
        if slot["arm"]=="C":instructions="Use native AEP only for mutation: begin_transaction, discovery, structured construction, replace_expression, check/commit. Source edits are refused. Tests build committed authority, not staging."
        prompt={"task":t["task"],"signature":f'solve({t["argument"]}: {t["alva_type"]}) -> {t["returns"]}' if language=="ALVA" else f'solve({t["argument"]})',
                "language":language,"condition":instructions,"examples":t["vectors"][:2],
                "initial_files":{p.relative_to(project).as_posix():p.read_text(encoding="utf-8") for p in project.rglob("*") if p.is_file()},
                "limits":CONFIG,"common":COMMON}
        save(path/"input.json",prompt)
        slot["input_sha256"]=sha((path/"input.json").read_bytes())
        slot["initial_files"]=hashes(project)
        save(HERE/"inputs"/(slot["id"]+".json"),prompt)
    save(HERE/"SCHEDULE.json",schedule)
    save(HERE/"CONFIG.json",CONFIG)
    save(HERE/"TOOLS.json",TOOLS)
    print("Four adaptations qualified; 12 real inputs prepared. No model calls.")


if __name__=="__main__":main()
