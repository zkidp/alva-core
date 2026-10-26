from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("native_case_agent", ROOT / "feasibility/native_api/run.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
Agent = native.Agent


def sha(data): return hashlib.sha256(data).hexdigest()
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def hashes(p): return {f.relative_to(p).as_posix(): sha(f.read_bytes()) for f in sorted(p.rglob("*")) if f.is_file() and "__pycache__" not in f.parts}


def command(argv, cwd, timeout=90):
    # Evaluated code must not inherit provider credentials or user environment.
    env = {"PATH": os.environ.get("PATH", os.defpath), "CARGO_NET_OFFLINE": "true",
           "PYTHONDONTWRITEBYTECODE": "1"}
    if "SystemRoot" in os.environ: env["SystemRoot"] = os.environ["SystemRoot"]
    for key in ("USERPROFILE","HOME","TEMP","TMP","ProgramFiles","ProgramFiles(x86)",
                "ProgramData","INCLUDE","LIB","LIBPATH","VCINSTALLDIR","VSINSTALLDIR",
                "CARGO_HOME","RUSTUP_HOME"):
        if key in os.environ: env[key]=os.environ[key]
    try:
        p = subprocess.run(list(map(str, argv)), cwd=cwd, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"exit": p.returncode, "stdout": p.stdout[-16000:], "stderr": p.stderr[-16000:], "timeout": False}
    except subprocess.TimeoutExpired:
        return {"exit": None, "stdout": "", "stderr": "TIMEOUT", "timeout": True}


def literal(value):
    if isinstance(value, bool): return str(value).lower()
    if isinstance(value, int): return str(value) + "i64"
    if isinstance(value, str): return json.dumps(value) + ".to_string()"
    return "vec![" + ",".join(map(literal, value)) + "]"


def evaluate(project, arm, task, binary, out, check_only=False):
    if arm == "A":
        try:
            compile((project / "program.py").read_text(encoding="utf-8"), "program.py", "exec")
        except (SyntaxError, UnicodeError) as exc:
            return {"status": "COMPILE_FAIL", "diagnostic": str(exc)}
        if check_only: return {"status": "PASS"}
        script = """import importlib.util,json,sys
s=importlib.util.spec_from_file_location('candidate',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rows=[]
for x,expected in json.loads(sys.argv[2]):
 try:
  actual=m.solve(x);ok=type(actual)==type(expected) and actual==expected
  rows.append({'pass':ok,'actual':actual,'expected':expected})
 except Exception as e:rows.append({'pass':False,'error':type(e).__name__})
print(json.dumps(rows))
"""
        row = command([sys.executable, "-I", "-c", script, project / "program.py", json.dumps(task["vectors"])], project, 15)
        try: tests = json.loads(row["stdout"]) if row["exit"] == 0 else []
        except ValueError: tests = []
        return {"status": "PASS" if tests and all(t["pass"] for t in tests) else "TEST_FAIL",
                "tests": tests, "execution": row}
    check = command([binary, "project", "check", project / "alva.toml", "--json"], project)
    if check["exit"] != 0: return {"status": "COMPILE_FAIL", "check": check}
    if check_only: return {"status": "PASS", "check": check}
    build = command([binary, "project", "build", project / "alva.toml", "--out-dir", out], project)
    if build["exit"] != 0: return {"status": "COMPILE_FAIL", "build": build}
    crate = out / "bench"
    code = "\n#[cfg(test)] mod independent { use super::bench::solve;\n"
    for i, (x, expected) in enumerate(task["vectors"]):
        code += f"#[test] fn vector_{i}() {{ assert_eq!(solve({literal(x)}),{literal(expected)}); }}\n"
    code += "}\n"
    # project build regenerates lib.rs; this never edits candidate ALVA/AIR.
    with (crate / "src/lib.rs").open("a", encoding="utf-8") as f: f.write(code)
    tests = command(["cargo", "test", "--manifest-path", crate / "Cargo.toml"], project)
    return {"status": "PASS" if tests["exit"] == 0 else "TEST_FAIL", "check": check, "build": build, "execution": tests}


def construct(agent, e):
    op, *a = e
    call = agent.result
    if op in ("int", "bool"):
        return call("create_literal", type="i64" if op == "int" else "bool", value=str(a[0]).lower())["revision"]
    if op == "ref": return call("create_reference", name=a[0])["revision"]
    if op == "vec": return call("construct_expression", kind="veclit", elem_type="i64", items=[])["revision"]
    if op == "call": return call("create_call", name=a[0], args=[construct(agent, x) for x in a[1:]])["revision"]
    if op == "bin": return call("create_binary", op=a[0], left=construct(agent,a[1]), right=construct(agent,a[2]))["revision"]
    if op == "if": return call("create_if", **dict(zip(("cond","then","else"),[construct(agent,x) for x in a])))["revision"]
    if op == "fold":
        i, acc, ty, start, end, init, body = a
        ty = ty.removeprefix("(prim ").removesuffix(")")
        revision = call("construct_expression", kind="fold", index=i, acc_name=acc, acc_type=ty,
                    range_start=construct(agent,start), range_end=construct(agent,end),
                    acc_init=construct(agent,init), body=construct(agent,body))["revision"]
        return revision
    raise ValueError(op)


TOOLS = [{"name":"study", "description":"Read/edit the candidate, run its check/test, or invoke public AEP. Only this tool is authorized. Arguments is a JSON-encoded object. read/edit: {path,content?}. aep: any native request with tool; project is host-bound. finish: {}. No shell/network/reference access.",
          "inputSchema":{"type":"object","properties":{"action":{"type":"string","enum":["read","edit","check","test","aep","finish"]},"arguments":{"type":"string"}},"required":["action","arguments"],"additionalProperties":False}}]


class Workbench:
    def __init__(self, path, arm, task, binary, evidence):
        self.path,self.arm,self.task,self.binary,self.evidence=path,arm,task,binary,evidence
        self.agent=None
        self.aep=[]
        self.edits=0
        self.commits=0
    def dispatch(self, action, args):
        if not isinstance(args,dict): return {"error":"ARGUMENT_OBJECT_REQUIRED"}
        if action in ("read","edit"):
            name=args.get("path")
            allowed=["program.py"] if self.arm=="A" else ["src/task.alva","alva.toml"]
            if name not in allowed: return {"error":"PATH_NOT_ALLOWED","allowed":allowed}
            if action=="read": return {"content":(self.path/name).read_text(encoding="utf-8")}
            if self.arm=="C" or name=="alva.toml":return {"error":"TEXT_EDIT_NOT_ALLOWED"}
            if not isinstance(args.get("content"),str):return {"error":"CONTENT_STRING_REQUIRED"}
            (self.path/name).write_text(args["content"],encoding="utf-8")
            self.edits+=1
            return {"accepted":True}
        if action=="aep":
            if self.arm!="C":return {"error":"AEP_NOT_AVAILABLE"}
            tool=args.get("tool")
            if not isinstance(tool,str):return {"error":"TOOL_STRING_REQUIRED"}
            args={k:v for k,v in args.items() if k not in ("project","request_id")}
            if tool=="begin_transaction":
                if self.agent: return self.agent.call(tool,expected=None,project=str(self.path/"alva.toml"))
                self.agent=Agent(self.binary,self.path,self.aep,"model")
                return self.aep[-1]["response"]
            if not self.agent:return {"error":"BEGIN_TRANSACTION_FIRST"}
            response=self.agent.call(expected=None,**args)
            if tool=="commit_transaction" and response["ok"]:self.commits+=1
            return response
        if action in ("check","test"):
            return evaluate(self.path,self.arm,self.task,self.binary,self.evidence/"build",action=="check")
        if action=="finish":return {"finished":True}
        return {"error":"UNKNOWN_ACTION"}
    def close(self):
        if self.agent:self.agent.close()
