"""Projection boundaries over synthetic graph descriptors; not agent trials."""
import copy
import unittest

from integrations.codex.bounded_target_context import project_context, Unsupported
from integrations.codex.maintenance_host import canonical


def fixture():
    nodes = {}
    def node(key, kind, values=None, **slots):
        nodes[key] = dict(revision=key, kind=kind, entity="", fields=values or {}, slots=slots)
        return key
    node("i64", "type_expr", dict(shape="prim", name="i64"))
    node("flag_ref", "type_expr", dict(shape="named", name="Flag"))
    node("alias_ref", "type_expr", dict(shape="named", name="Alias"))
    node("flag", "type", dict(name="Flag", kind="enum", variants=["on", "off"]))
    node("alias", "type", dict(name="Alias", kind="alias"), alias=["flag_ref"])
    node("item_ref", "type_expr", dict(shape="named", name="Item"))
    node("field", "type_field", dict(name="flag"), type=["alias_ref"])
    node("item", "type", dict(name="Item", kind="record"), fields=["field"])
    node("param", "param", dict(name="item"), type=["item_ref"])
    node("body", "block", steps=["call"])
    node("call", "call", dict(name="helper"), args=[])
    node("secret", "literal", dict(value="PRIVATE_HELPER_BODY_MUST_NOT_LEAK"))
    node("helper_body", "block", steps=["secret"])
    for name, body in (("target", "body"), ("helper", "helper_body")):
        node(name, "function", dict(name=name, pure=True, eff=[]), params=["param"], returns=["i64"],
             body=[body], pre=[], post=[], inv=[])
    node("module", "module", dict(name="m"), functions=["target", "helper"], types=["item", "alias", "flag"], tests=[])
    return {"project": {"modules": {"module:m": "module"}, "project_revision": "a" * 64}, "nodes": nodes}


class ContextTests(unittest.TestCase):
    def test_nested_record_alias_enum_and_callee_signature(self):
        s = fixture()
        original = copy.deepcopy(s)
        result = project_context(s, "m.target", set())
        self.assertEqual(result["status"], "COMPLETE_WITHIN_BOUNDARY")
        self.assertEqual([t["name"] for t in result["types"]], ["m.Alias", "m.Flag", "m.Item"])
        self.assertEqual(result["types"][1]["variants"], ["on", "off"])
        self.assertEqual(result["callees"][0]["function"], "m.helper")
        self.assertNotIn("PRIVATE_HELPER_BODY_MUST_NOT_LEAK", str(result))
        self.assertNotIn("body", result["callees"][0])
        self.assertEqual(s, original)
        self.assertEqual(result, project_context(s, "m.target", set()))

    def test_missing_type_and_external_call_are_partial_not_guessed(self):
        s = fixture()
        s["nodes"]["alias_ref"]["fields"]["name"] = "unavailable.Remote"
        s["nodes"]["call"]["fields"]["name"] = "ffi.unavailable"
        result = project_context(s, "m.target", set())
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["unresolved_count"], 2)
        self.assertIn("unresolved_type:unavailable.Remote", result["unresolved"])
        self.assertIn("unresolved_callee:ffi.unavailable", result["unresolved"])

    def test_declared_builtins_do_not_become_missing_local_functions(self):
        s = fixture()
        s["nodes"]["call"]["fields"]["name"] = "split"
        result = project_context(s, "m.target", {"split"})
        self.assertEqual(result["status"], "COMPLETE_WITHIN_BOUNDARY")
        self.assertEqual(result["callees"], [])

    def test_callee_only_types_resolve_in_callee_module_not_target_module(self):
        s = fixture()
        s["nodes"]["target"]["slots"]["params"] = []
        s["nodes"]["module"]["slots"].update(functions=["target"], types=[])
        s["nodes"]["other"] = dict(revision="other", kind="module", entity="", fields={"name": "other"},
                                     slots={"functions": ["helper"], "types": ["item", "alias", "flag"], "tests": []})
        s["project"]["modules"]["module:other"] = "other"
        s["nodes"]["call"]["fields"]["name"] = "other.helper"
        result = project_context(s, "m.target", set())
        self.assertEqual(result["status"], "COMPLETE_WITHIN_BOUNDARY")
        self.assertEqual([t["name"] for t in result["types"]], ["other.Alias", "other.Flag", "other.Item"])
        self.assertEqual(result["callees"][0]["params"][0]["type"], {"named": "other.Item"})

    def test_bounds_have_no_silent_field_or_declaration_truncation(self):
        for mode in ("declarations", "bytes"):
            s = fixture()
            if mode == "bytes":
                s["nodes"]["flag"]["fields"]["variants"] = ["x" * 20000]
            result = project_context(s, "m.target", set(), max_declarations=1 if mode == "declarations" else 64)
            self.assertEqual(result["status"], "TOO_BROAD")
            self.assertEqual(result["types"], [])
            self.assertEqual(result["callees"], [])
            self.assertLessEqual(len(canonical(result)), 16384)
            self.assertEqual(len(result["complete_payload_sha256"]), 64)

    def test_named_cycles_terminate_but_bad_snapshots_are_not_complete(self):
        s = fixture()
        s["nodes"]["flag_ref"]["fields"]["name"] = "Item"
        result = project_context(s, "m.target", set())
        self.assertEqual(result["status"], "COMPLETE_WITHIN_BOUNDARY")
        for change in (lambda n: n.pop("i64"),
                       lambda n: n["item"].update(revision="wrong"),
                       lambda n: n["module"]["slots"].update(functions=["target", "target"]),
                       lambda n: n.update(detached=dict(revision="detached", kind="literal", fields={}, slots={})),
                       lambda n: n["i64"]["fields"].update(shape="future_type")):
            s = fixture()
            change(s["nodes"])
            with self.assertRaises(Unsupported):
                project_context(s, "m.target", set())

    def test_revision_and_content_are_bound_without_source_or_task_input(self):
        s = fixture()
        a = project_context(s, "m.target", set())
        s["project"]["project_revision"] = "b" * 64
        s["nodes"]["flag"]["fields"]["variants"].append("third")
        b = project_context(s, "m.target", set())
        self.assertNotEqual(a["project_revision"], b["project_revision"])
        self.assertNotEqual(a["snapshot_sha256"], b["snapshot_sha256"])
        self.assertEqual(b["types"][1]["variants"][-1], "third")


if __name__ == "__main__":
    unittest.main()
