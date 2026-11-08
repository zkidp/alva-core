"""Deterministic qualification only; never included in model input."""
from benchmarks.p37_maintenance_qualification.witnesses import text_change
from benchmarks.compact_deepseek.preflight import end_form
from integrations.benchmark_runtime_v2.freeze import decode


def replacement(task):
    original=decode(task['bundle'],task['bundle']['payload_sha256']);changed=dict(original)
    public=task['public_task'];ident=public['id'];target=public['target'].rsplit('.',1)[1]
    if ident in ('H01','H02'):
        changed=text_change({'id':'MM05' if ident=='H01' else 'MM06','target':public['target']},original)
    else:
        text=original['src/metadata.alva'].decode()
        start=text.index('  (fn '+target+'\n');body=text.index('(body',start);end=end_form(text,body)
        if ident=='H03':new='''(body
 (let found (call lookup (field (ref bucket) "objects") (ref key))
  (if (not (call is-ok (ref found))) (ref found)
   (let meta (call unwrap (ref found))
    (match ObjectState (field (ref meta) "state")
     (case active (ok (ref meta)))
     (case archived (err (nil))))))))'''
        else:
            new=text[body:end].replace('(let end (+ (ref offset) (ref limit))',
                '(let end (if (> (ref limit) (- (ref total) (ref offset))) (ref total) (+ (ref offset) (ref limit)))')
        changed['src/metadata.alva']=(text[:body]+new+text[end:]).encode()
    path=next(p for p in original if original[p]!=changed[p]);text=changed[path].decode()
    start=text.index('  (fn '+target+'\n');body=text.index('(body',start)
    return changed,text[body:end_form(text,body)]
