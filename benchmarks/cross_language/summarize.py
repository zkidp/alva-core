"""Post-closure descriptive accounting only; never requests generation."""
from collections import Counter
import json
from common import ROOT,HERE,load,save,sha
from prepare import RUNTIME


def main():
    freeze=load(HERE/"FREEZE.json")
    rows=[]
    for slot in freeze["schedule"]:
        path=RUNTIME/"slots"/slot["id"]/"result.json"
        if not path.exists():continue
        r=load(path)
        actions=Counter(x["action"] for x in r.get("tools",[]))
        aep=load(path.parent/"aep-tools.json")
        operations=Counter(x["request"]["tool"] for x in aep)
        successful_operations=Counter(x["request"]["tool"] for x in aep if x["response"]["ok"])
        rejected=[x["response"] for x in aep if not x["response"]["ok"]]
        usage=(r.get("usage") or {}).get("total")
        events=r.get("tools",[])
        source_mutations=[i+1 for i,e in enumerate(events) if e["action"]=="edit" and e["response"].get("accepted")]
        aep_mutations=[i+1 for i,e in enumerate(events) if e["action"]=="aep" and e["arguments"].get("tool") in ("replace_expression","change_field","append_step","add_function","add_param","add_call_arg") and e["response"].get("ok")]
        rows.append({"slot":r["slot"],"task":r["task"],"arm":r["arm"],"correctness":r["final"]["status"],
                     "terminal_status":r.get("terminal_status"),"stop_reason":r.get("stop_reason"),
                     "infrastructure_hold":r.get("infrastructure_hold"),"tools":r.get("tool_calls"),
                     "actions":dict(actions),"aep_operations":dict(operations),"aep_rejections":rejected,
                     "successful_aep_operations":dict(successful_operations),
                     "accepted_source_edits":r["accepted_source_edits"],"commits":r["successful_commits"],
                     "first_mutation_callback_ordinal":min(source_mutations+aep_mutations,default=None),
                     "elapsed_seconds":r.get("elapsed_seconds"),"last_reported_provider_usage":usage,
                     "usage_complete_per_host_terminal":r.get("usage_complete",False),
                     "provider_generation_requests":None,"dollar_cost":None,
                     "interrupt_requested":r.get("interrupt_requested"),"interrupt_ack":r.get("interrupt_ack"),
                     "unauthorized_items":r.get("unauthorized_items",[])})
    groups={a:{"executed":sum(r["arm"]==a for r in rows),
               "passed":sum(r["arm"]==a and r["correctness"]=="PASS" for r in rows),
               "compile_fail":sum(r["arm"]==a and r["correctness"]=="COMPILE_FAIL" for r in rows),
               "test_fail":sum(r["arm"]==a and r["correctness"]=="TEST_FAIL" for r in rows)} for a in "ABC"}
    pairs=[]
    for t in (41,23,42,3):
        by_arm={r["arm"]:r for r in rows if r["task"]==t}
        pairs.append({"task":t,"arms":by_arm,
                      "Python_vs_ALVA_Text":{a:by_arm.get(a,{}).get("correctness","NOT_STARTED") for a in "AB"},
                      "ALVA_Text_vs_AEP":{a:by_arm.get(a,{}).get("correctness","NOT_STARTED") for a in "BC"}})
    save(HERE/"ANALYSIS.json",{"classification":"DESCRIPTIVE_DEVELOPMENTAL_ONLY","groups":groups,"rows":rows,"pairs":pairs})
    intact=all(sha((ROOT/name).read_bytes())==value for name,value in freeze["files"].items())
    # Captured-output audit only; never change the frozen evaluator or scores.
    def typed_equal(a,b):
        if type(a) is not type(b):return False
        if isinstance(a,list):return len(a)==len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
        return a==b
    captured_types=[]
    for slot in freeze["schedule"]:
        path=RUNTIME/"slots"/slot["id"]/"result.json"
        if slot["arm"]=="A" and path.exists():
            captured_types.extend(typed_equal(t.get("actual"),t["expected"]) for t in load(path)["final"].get("tests",[]))
    save(HERE/"VALIDATION.json",{"frozen_files_unchanged":intact,"started_model_tasks":len(rows),"scheduled":12,
                                 "all_slots_closed":len(rows)==12,"infrastructure_holds":[r["slot"] for r in rows if r.get("infrastructure_hold")],
                                 "all_terminal_confirmed":all(r["terminal_status"] is not None for r in rows),
                                 "all_interrupts_acknowledged":all(not r["interrupt_requested"] or r["interrupt_ack"] for r in rows),
                                 "captured_python_outputs_recursive_type_audit_pass":bool(captured_types) and all(captured_types),
                                 "frozen_python_comparator_limit":"Top-level type equality only; nested element-type equivalence is not enforced. Captured final outputs audited without reruns or score changes.",
                                 "model_generation_calls_in_analysis":0,"input_token_api_calls":0,"extra_replacement_slots":0})
    print(json.dumps(groups,indent=2))


if __name__=="__main__":main()
