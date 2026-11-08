"""Fresh authored maintenance fixtures, not externally sourced holdout tasks.

Public requirements and independent checks live in separate fields. Never send
this module, engineering candidates or assertions to the model.
"""
from integrations.codex.maintenance_host import canonical, sha
import base64


def bundle(files):
    entries = [{"path": p, "origin": {"kind": "authored_public_fixture"}, "length": len(b),
                "sha256": sha(b), "base64": base64.b64encode(b).decode()} for p, b in sorted(files.items())]
    payload = {"schema": "alva-benchmark-freeze/v2", "byte_policy": "exact-git-blob-no-normalization", "entries": entries}
    return {"payload": payload, "payload_sha256": sha(canonical(payload))}


def task(ident, target, requirement, files, functions, types, goal, regression):
    manifest = '[project]\nname="context_trial"\n[modules]\n' + ''.join(f'{m}="{m}.alva"\n' for m in functions)
    files = {"alva.toml": manifest.encode(), **{p: s.encode() for p, s in files.items()}}
    return {"public_task": {"id": ident, "target": target, "requirement": requirement},
        "bundle": bundle(files), "input_paths": sorted(files), "crate": "context_trial",
        "policy": {"authorized_functions": [target], "modules": {
            m: {"functions": names, "types": types.get(m, [])} for m, names in functions.items()}},
        "assertions": {"goal": '#[test] fn maintenance_goal(){' + goal + '}',
                       "regression": '#[test] fn preserved_behavior(){' + regression + '}'}}


def tasks():
    return {
      "Q01": task("Q01", "billing.charge", "Normalize negative subtotal and cap to zero; charge is the smaller normalized value. Preserve all non-target behavior and signatures.",
        {"billing.alva": '''(module (name "billing") (version "1") (export charge tax)
 (fn charge (params (param subtotal (prim i64)) (param cap (prim i64))) (returns (prim i64)) (pure)
  (body (ref subtotal)))
 (fn tax (params (param amount (prim i64))) (returns (prim i64)) (pure) (body (/ (ref amount) (int 10)))))''',
         "audit.alva": '''(module (name "audit") (version "1") (export label)
 (fn label (params) (returns (prim string)) (pure) (body (string "receipt-v1"))))'''},
        {"billing": ["charge", "tax"], "audit": ["label"]}, {},
        'for (s,c,e) in [(-4,10,0),(8,-2,0),(0,0,0),(4,8,4),(12,8,8),(9,9,9),(1000,17,17)] {assert_eq!(crate::billing::charge(s,c),e);}',
        'assert_eq!(crate::billing::tax(250),25);assert_eq!(crate::audit::label(),"receipt-v1");'),
      "Q02": task("Q02", "shipping.quote", "A request with parcel mass <= 0 must quote zero. Otherwise use the existing rates.base charge, and add 20 only for a priority request. Preserve base pricing and the public quote_for adapter.",
        {"model.alva": '''(module (name "model") (version "1") (export Parcel Request)
 (type Parcel (record (field mass (prim i64))))
 (type Request (record (field parcel Parcel) (field priority (prim bool)))))''',
         "rates.alva": '''(module (name "rates") (version "1") (export base)
 (fn base (params (param mass (prim i64))) (returns (prim i64)) (pure) (body (* (ref mass) (int 3)))))''',
         "shipping.alva": '''(module (name "shipping") (version "1") (dep "model" "1") (dep "rates" "1") (export quote quote_for)
 (fn quote (params (param request model.Request)) (returns (prim i64)) (pure)
  (body (call rates.base (field (field (ref request) "parcel") "mass"))))
 (fn quote_for (params (param mass (prim i64)) (param priority (prim bool))) (returns (prim i64)) (pure)
  (body (call quote (record model.Request (parcel (record model.Parcel (mass (ref mass)))) (priority (ref priority)))))))'''},
        {"model": [], "rates": ["base"], "shipping": ["quote", "quote_for"]}, {"model": ["Parcel", "Request"]},
        'for (m,p,e) in [(-1,true,0),(0,false,0),(0,true,0),(2,false,6),(2,true,26),(7,true,41)] {assert_eq!(crate::shipping::quote_for(m,p),e);}',
        'for m in [0,1,2,7,100] {assert_eq!(crate::rates::base(m),m*3);}'),
      "Q03": task("Q03", "retry.delay", "For negative attempts return zero. For other attempts increase the existing policy.base delay by 3, capped at 20. Do not change policy.base or audit behavior.",
        {"policy.alva": '''(module (name "policy") (version "1") (export base)
 (fn base (params (param attempts (prim i64))) (returns (prim i64)) (pure)
  (body (+ (* (ref attempts) (int 2)) (int 5)))))''',
         "retry.alva": '''(module (name "retry") (version "1") (dep "policy" "1") (export delay)
 (fn delay (params (param attempts (prim i64))) (returns (prim i64)) (pure)
  (body (call policy.base (ref attempts)))))''',
         "audit.alva": '''(module (name "audit") (version "1") (export label)
 (fn label (params) (returns (prim string)) (pure) (body (string "retry-v1"))))'''},
        {"policy": ["base"], "retry": ["delay"], "audit": ["label"]}, {},
        'for (n,e) in [(-2,0),(-1,0),(0,8),(1,10),(3,14),(6,20),(10,20),(100,20)] {assert_eq!(crate::retry::delay(n),e);}',
        'for n in [0,1,10,100] {assert_eq!(crate::policy::base(n),2*n+5);}assert_eq!(crate::audit::label(),"retry-v1");')}
