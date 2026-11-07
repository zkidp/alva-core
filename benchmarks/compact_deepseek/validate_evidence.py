"""Post-run independent receipt, request reconstruction and scoring checks. No models."""
import json,base64,hashlib,pathlib,statistics
root=pathlib.Path(__file__).resolve().parents[2]
import argparse
p=argparse.ArgumentParser();p.add_argument("directory",type=pathlib.Path);args=p.parse_args()
wave=args.directory.resolve()
frozen=json.loads((root/"benchmarks/compact_deepseek/FREEZE.json").read_bytes())
batch=json.loads((wave/"RESULTS.json").read_bytes())
h=lambda b:hashlib.sha256(b).hexdigest()
can=lambda v:json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
assert json.loads((wave/"GENERATION-STARTED.json").read_bytes())["freeze_sha256"]==h((root/"benchmarks/compact_deepseek/FREEZE.json").read_bytes())
rows=[]
for i,r in enumerate(batch["rows"]):
 entry=frozen["schedule"][i]
 assert all(r[k]==entry[k] for k in ("id","arm","task","repeat"))
 assert json.loads((wave/r["id"]/"record.json").read_bytes())==r
 if not r.get("valid"):
  rows.append({"id":r["id"],"status":"UNKNOWN_INFRASTRUCTURE"});continue
 assert r["identity_before"] and r["identity_after"] and r["cleanup_confirmed"]
 assert r["model_sessions_started"]==1
 assert len(r["responses"])==r["submitted_chat_requests"]
 rawusage=[e["response"]["usage"] for e in r["responses"]]
 mapping={"totalTokens":"total_tokens","inputTokens":"prompt_tokens","outputTokens":"completion_tokens"}
 for dst,src in mapping.items():assert r["reported_usage"][dst]==sum(u[src] for u in rawusage)
 assert all(u["total_tokens"]==u["prompt_tokens"]+u["completion_tokens"] for u in rawusage)
 assert r["reported_usage"]["cachedInputTokens"]==sum(u.get("prompt_cache_hit_tokens",u.get("prompt_tokens_details",{}).get("cached_tokens")) for u in rawusage)
 assert r["observed_tool_calls"]==sum(len(e["response"]["choices"][0]["message"].get("tool_calls",[])) for e in r["responses"])
 assert r["dispatched_tool_calls"]==len(r["tool_events"])
 messages=list(r["initial_messages"]); cursor=0
 assert [m["role"] for m in messages]==["system","user"]
 assert messages[0]["content"]==frozen["developer_instructions"]+"\nCondition: "+r["arm"]
 for event in r["responses"]:
  payload={"model":frozen["model"],"messages":messages,"tools":frozen["provider_tools"][r["arm"]],**frozen["api_parameters"]}
  assert h(json.dumps(payload,ensure_ascii=True).encode())==event["request_sha256"]
  message=event["response"]["choices"][0]["message"]
  if not message.get("tool_calls"):continue
  messages.append(message)
  for call in message["tool_calls"]:
   if cursor>=len(r["tool_events"]):break
   e=r["tool_events"][cursor]
   assert e["name"]==call["function"]["name"]
   messages.append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(e["response"],ensure_ascii=False)})
   cursor+=1
 assert cursor==len(r["tool_events"])
 evidence=json.loads((wave/r["id"]/"linux.json").read_bytes())
 assert h((wave/r["id"]/"linux.json").read_bytes())==r["evidence_sha256"]
 assert json.loads((wave/r["id"]/"cleanup.json").read_bytes())["confirmed"]
 files={p:base64.b64decode(b) for p,b in evidence["final_files"].items()}
 assert h(can({p:h(b) for p,b in files.items()}))==evidence["final"]["tested_snapshot_sha256"]
 a,b=evidence["initial_authority"],evidence["final_authority"]
 scope=a.get("modules")==b.get("modules") and set(a.get("functions",{}))==set(b.get("functions",{}))
 changed=[]
 if scope:
  for name,before in a["functions"].items():
   after=b["functions"][name]
   scope &= {k:v for k,v in before.items() if k!="body"}=={k:v for k,v in after.items() if k!="body"}
   if before["body"]!=after["body"]:changed.append(name)
 authorized=frozen["tasks"][r["task"]]["policy"]["authorized_functions"]
 candidate=bool(scope and changed and set(changed)<=set(authorized) and evidence["final"]["status"]=="PASS")
 expected=candidate and r["terminal_confirmed"]
 if r["arm"]=="N":
  commits=[e for e in evidence["calls"] if e.get("request",{}).get("method")=="tools/call" and e["request"]["params"]["name"]=="commit_transaction" and not e.get("response",{}).get("isError")]
  expected &= bool(commits and "alva-air/current" in files and b["project_revision"]==commits[-1]["response"]["structuredContent"]["revision"])
 assert bool(expected)==r["correct"]
 rows.append({"id":r["id"],"status":"VERIFIED","correct":r["correct"],"request_reconstruction":"EXACT","evidence_bound":True})
print(json.dumps({"status":"PASS","rows":rows,"complete_schedule":len(rows)==16},indent=2))
