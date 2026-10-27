"""Engineering-only modifications and independent tests; NEVER model inputs.

These mechanically authored witnesses qualify expressibility, not agent skill.
Future model namespaces must contain only catalogue public_inputs and approved
public docs. Do not mount this directory or the repository into an agent slot.
"""


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after, 1)


def text_change(task, source):
    result = dict(source)
    if task == "MM01":
        path = "src/model.alva"
        text = source[path].decode()
        start = text.index("  (fn touch_size")
        original = text[start:]
        before = "    (body\n      (record Meta"
        after = '    (body\n      (if (< (field (ref m) "size") (int 0))\n        (ref m)\n        (record Meta'
        changed = replace_once(original, before, after)
        # One additional conditional around the existing complete record body.
        changed = changed.rstrip() + ")\n"
        result[path] = (text[:start] + changed).encode()
    elif task == "MM02":
        path = "src/xml.alva"
        text = source[path].decode()
        split = text.index("  (fn parse_delimiter")
        before = '(if (== (ref rest) (ref part))'
        after = '(if (if (== (ref found) (string "")) (== (ref rest) (ref part)) (bool true))'
        result[path] = (replace_once(text[:split], before, after) + text[split:]).encode()
    elif task == "MM03":
        path = "src/model.alva"
        text = source[path].decode()
        start, end = text.index("  (fn size_of"), text.index("  (fn touch_size")
        fn = text[start:end]
        fn = replace_once(fn, "(param m Meta))", "(param m Meta)\n      (param fallback (prim i64)))")
        fn = replace_once(fn, '(field (ref m) "size")))',
            '(if (< (field (ref m) "size") (int 0)) (ref fallback) (field (ref m) "size"))))')
        result[path] = (text[:start] + fn + text[end:]).encode()
        path = "src/app.alva"
        result[path] = replace_once(source[path].decode(),
            '(call demo.model.make_meta (string "a") (int 5) (string "e1"))))))',
            '(call demo.model.make_meta (string "a") (int 5) (string "e1"))) (int 0))))').encode()
    else:
        raise ValueError(task)
    return result


def mutate_native(task, c):
    """c provides current real transaction operations and graph inspection."""
    if task == "MM01":
        nodes = c.nodes("demo.model.touch_size")
        plus = next(n for n in nodes.values() if n["kind"] == "binary" and n["fields"].get("op") == "+")
        block = next(n for n in nodes.values() if n["kind"] == "block")
        original = block["slots"]["steps"][0]
        zero = c.call("create_literal", type="i64", value="0")["revision"]
        cond = c.call("create_binary", op="<", left=plus["slots"]["left"][0], right=zero)["revision"]
        m = c.call("create_reference", name="m")["revision"]
        branch = c.call("create_if", **{"cond": cond, "then": m, "else": original})["revision"]
        c.call("replace_expression", parent=block["revision"], child=branch, position="step")
    elif task == "MM02":
        nodes = c.nodes("store.xml.parse_prefix")
        choices = []
        for node in nodes.values():
            if node["kind"] != "if":
                continue
            cond = nodes[node["slots"]["cond"][0]]
            if cond["kind"] != "binary" or cond["fields"].get("op") != "==":
                continue
            left, right = (nodes[cond["slots"][p][0]] for p in ("left", "right"))
            if left["fields"].get("name") == "rest" and right["fields"].get("name") == "part":
                choices.append(node)
        assert len(choices) == 1
        target = choices[0]
        found = c.call("create_reference", name="found")["revision"]
        empty = c.call("create_literal", type="string", value="")["revision"]
        unset = c.call("create_binary", op="==", left=found, right=empty)["revision"]
        yes = c.call("create_literal", type="bool", value="true")["revision"]
        cond = c.call("create_if", **{"cond": unset, "then": target["slots"]["cond"][0], "else": yes})["revision"]
        c.call("replace_expression", parent=target["revision"], child=cond, position="cond")
    else:
        raise ValueError("No native witness for unsupported signature candidate")


def regressions(task):
    if task in ("MM01", "MM03"):
        return r'''
#[cfg(test)] mod maintenance_regression {
 use super::{demo_app, demo_model};
 #[test] fn app_compatibility(){assert_eq!(demo_app::run(),6);}
 #[test] fn construction_and_fields(){
  for s in [-9,0,11] {
   let m=demo_model::make_meta("key".into(),s,"tag".into());
   assert_eq!(m.key,"key"); assert_eq!(m.size,s); assert_eq!(m.etag,"tag");
  }
 }
}
'''
    return r'''
#[cfg(test)] mod maintenance_regression {
 use super::{store_xml,store_model};
 #[test] fn delimiter_unchanged(){
  assert_eq!(store_xml::parse_delimiter("delimiter=%2F&delimiter=%21".into()),"!");
  assert_eq!(store_xml::parse_delimiter("prefix=a".into()),"");
 }
 #[test] fn response_record_unchanged(){
  let r=store_model::text_response(201,vec![65u8]);
  assert_eq!(r.status,201); assert_eq!(r.content_type,"text/plain");
  assert_eq!(r.body,vec![65u8]); assert_eq!(r.head_content_length,0);
 }
 #[test] fn list_render_unchanged(){
  let r=store_xml::list_objects_xml("".into(),"".into(),"".into());
  assert_eq!(r,"<?xml version=\"1.0\"?><ListBucketResult></ListBucketResult>");
  assert!(store_xml::list_buckets_xml("one\n".into()).contains("<Name>one</Name>"));
 }
}
'''


def goals(task):
    if task == "MM01":
        return r'''
#[cfg(test)] mod maintenance_goal {
 use super::demo_model;
 #[test] fn negative_is_noop_and_fields_survive(){
  for (s,want) in [(-9,-9),(-1,-1),(0,1),(7,8)] {
   let m=demo_model::touch_size(demo_model::make_meta("k".into(),s,"e".into()));
   assert_eq!(m.size,want); assert_eq!(m.key,"k"); assert_eq!(m.etag,"e");
  }
 }
 #[test] fn unrelated_accessor(){
  assert_eq!(demo_model::size_of(demo_model::make_meta("k".into(),-3,"e".into())),-3);
 }
}
'''
    if task == "MM02":
        return r'''
#[cfg(test)] mod maintenance_goal {
 use super::store_xml;
 #[test] fn first_nonempty_decoded_prefix(){
  for (q,want) in [("prefix=a&prefix=b","a"),("prefix=&prefix=a&prefix=b","a"),
   ("x=1&prefix=a%2Fb&prefix=c","a/b"),("prefix=a&prefix=","a"),
   ("prefix=&prefix=",""),("x=1",""),("","")] {
   assert_eq!(store_xml::parse_prefix(q.into()),want);
  }
 }
}
'''
    return r'''
#[cfg(test)] mod maintenance_goal {
 use super::demo_model;
 #[test] fn accessor_fallback_api(){
  for (s,f,want) in [(-5,8,8),(0,8,0),(9,8,9),(-2,-9,-9)] {
   let m=demo_model::make_meta("k".into(),s,"e".into());
   assert_eq!(demo_model::size_of(m,f),want);
  }
 }
 #[test] fn touch_still_increments(){
  assert_eq!(demo_model::touch_size(demo_model::make_meta("k".into(),-3,"e".into())).size,-2);
 }
}
'''
