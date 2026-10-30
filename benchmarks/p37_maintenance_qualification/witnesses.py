"""Codex engineering witnesses only. Never include in future model inputs."""
import re


def function_region(text, target):
    start = text.index("  (fn " + target + "\n")
    match = re.search(r"^  \((?:fn|test) ", text[start + 1:], re.M)
    end = start + 1 + match.start() if match else text.rfind("\n)")
    return start, end


def text_change(candidate, source):
    result = dict(source)
    text = source["src/model.alva"].decode()
    target = candidate["target"].rsplit(".", 1)[1]
    start, end = function_region(text, target)
    original = text[start:end]
    if candidate["id"] == "MM04":
        old = "(ok (ref ordered))"
        new = '(if (== (call len (ref ordered)) (call len (ref pkgs))) (ok (ref ordered)) (err (string "unresolved dependencies or cycle")))'
    elif candidate["id"] == "MM05":
        old = '(or (not (== (ref current_source_hash) (field (ref p) "prev_source_hash")))\n          (call dep_output_changed (ref p) (ref pkgs)))'
        new = '(if (or (== (call state_label (field (ref p) "state")) (string "PENDING")) (== (call state_label (field (ref p) "state")) (string "FAILED"))) (bool true) ' + old + ')'
    elif candidate["id"] == "MM06":
        old = '(call append (ref out) (field (ref p) "name"))'
        new = '(if (call vec_contains (ref out) (field (ref p) "name")) (ref out) ' + old + ')'
    else:
        changed = original
        for name in ("code", "message"):
            expr = "(ref " + name + ")"
            replacement = expr
            for before, after in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")):
                replacement = '(call join (call split ' + replacement + ' (string "' + before + '")) (string "' + after + '"))'
            assert changed.count(expr) == 1
            changed = changed.replace(expr, replacement)
        result["src/model.alva"] = (text[:start] + changed + text[end:]).encode()
        return result
    assert original.count(old) == 1
    result["src/model.alva"] = (text[:start] + original.replace(old, new) + text[end:]).encode()
    return result


def native(candidate, c):
    target = candidate["target"]
    def literal(value, typ="string"):
        return c.call("create_literal", type=typ, value=value)["revision"]
    def reference(name):
        return c.call("create_reference", name=name)["revision"]
    def call(name, *args):
        return c.call("create_call", name=name, args=list(args))["revision"]
    def binary(op, left, right):
        return c.call("create_binary", op=op, left=left, right=right)["revision"]
    def branch(cond, yes, no):
        return c.call("create_if", **{"cond": cond, "then": yes, "else": no})["revision"]
    nodes = c.nodes(target)
    if candidate["id"] == "MM04":
        parents = [n for n in nodes.values() if n["kind"] == "binding" and n["fields"].get("name") == "ordered"]
        assert len(parents) == 1
        parent = parents[0]
        complete = binary("==", call("len", reference("ordered")), call("len", reference("pkgs")))
        error = c.call("construct_expression", kind="err", value=literal("unresolved dependencies or cycle"),
                       expected_type="(result (vec (prim string)) (prim string))")["revision"]
        changed = branch(complete, parent["slots"]["body"][0], error)
        c.call("replace_expression", parent=parent["revision"], position="body", child=changed)
    elif candidate["id"] == "MM05":
        root = c.call("inspect_entity", entity=target)
        block = nodes[root["slots"]["body"][0]]
        state = c.call("construct_expression", kind="field", name="state", value=reference("p"))["revision"]
        label = call("build.model.state_label", state)
        bad = binary("or", binary("==", label, literal("PENDING")), binary("==", label, literal("FAILED")))
        changed = branch(bad, literal("true", "bool"), block["slots"]["steps"][0])
        c.call("replace_expression", parent=block["revision"], position="step", child=changed)
    elif candidate["id"] == "MM06":
        parents = [n for n in nodes.values() if n["kind"] == "binding" and n["fields"].get("name") == "hit"]
        assert len(parents) == 1
        parent = parents[0]
        name = c.call("construct_expression", kind="field", name="name", value=reference("p"))["revision"]
        seen = call("build.model.vec_contains", reference("out"), name)
        changed = branch(seen, reference("out"), parent["slots"]["body"][0])
        c.call("replace_expression", parent=parent["revision"], position="body", child=changed)
    else:
        for name in ("code", "message"):
            nodes = c.nodes(target)
            matches = [(n, slot) for n in nodes.values() if n["kind"] == "concat" for slot in ("left", "right")
                if nodes[n["slots"][slot][0]]["kind"] == "ref" and nodes[n["slots"][slot][0]]["fields"].get("name") == name]
            assert len(matches) == 1
            parent, slot = matches[0]
            value = parent["slots"][slot][0]
            for before, after in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")):
                value = call("join", call("split", value, literal(before)), literal(after))
            c.call("replace_expression", parent=parent["revision"], position=slot, child=value)
