"""Decision mechanisms only; no oracle, case IDs or expected verdict inputs."""
import re


def source_scope(before, after, allowed):
    """Exact body-region diff for this registered, comment-free fixture grammar.

    Refuse unsupported syntax instead of claiming a general ALVA parser. The
    baseline uses source bytes, not AIR-derived edit permissions.
    """
    pattern = re.compile(r"  \(fn (\w+)\n.*?    \(body (.*?)\)\)\n", re.S)
    def split(text):
        matches = list(pattern.finditer(text))
        if not matches or text.count("  (fn ") != len(matches):
            raise ValueError("unsupported source grammar")
        bodies = {m[1]: m[2] for m in matches}
        if len(bodies) != len(matches):
            raise ValueError("ambiguous declarations")
        # Retain signatures and the complete outside-body text byte-for-byte.
        masked = pattern.sub(lambda m: m[0].replace(m[2], "<BODY>", 1), text)
        return bodies, masked
    try:
        a, am = split(before)
        b, bm = split(after)
        if am != bm or set(a) != set(b):
            return {"status": "REJECT", "reason": "protected source structure"}
        changed = sorted(n for n in a if a[n] != b[n])
        return {"status": "REJECT" if set(changed) - set(allowed) else "ALLOW", "changed": changed}
    except ValueError as exc:
        return {"status": "UNKNOWN", "reason": str(exc)}


def structural(before, after, allowed):
    changed = sorted(f for f in before["functions"] if f in after["functions"] and
                     before["functions"][f]["body"] != after["functions"][f]["body"])
    if before["modules"] != after["modules"] or set(before["functions"]) != set(after["functions"]):
        return {"status": "REJECT", "changed": changed, "reason": "protected inventory or module structure"}
    for f, a in before["functions"].items():
        b = after["functions"][f]
        if {k: v for k, v in a.items() if k != "body"} != {k: v for k, v in b.items() if k != "body"}:
            return {"status": "REJECT", "changed": changed, "reason": "protected function metadata"}
    return {"status": "REJECT" if set(changed) - set(allowed) else "ALLOW", "changed": changed,
            "unauthorized": sorted(set(changed) - set(allowed))}


def impact(graphs, changed):
    """Union before/after direct local call graph; bounded closed fixtures only."""
    edges, unsupported = set(), set()
    admitted = {"function", "block", "binary", "ref", "literal", "call",
                "param", "type_expr"}
    for version in graphs:
        for f, nodes in version.items():
            for n in nodes.values():
                # Type/parameter nodes do not contribute dependencies. Record
                # unseen computational constructs as unsupported, fail closed.
                if n["kind"] not in admitted:
                    unsupported.add(n["kind"])
                if n["kind"] == "call":
                    callee = f.rsplit(".", 1)[0] + "." + n["fields"]["name"]
                    if callee not in version:
                        unsupported.add("unresolved:" + callee)
                    else:
                        edges.add((f, callee))
    reached = set(changed)
    while True:
        expanded = reached | {caller for caller, callee in edges if callee in reached}
        if expanded == reached:
            break
        reached = expanded
    return {"potentially_impacted": sorted(reached), "direct_calls": sorted(edges),
            "complete_for_fixture": not unsupported, "unsupported": sorted(unsupported),
            "claim": "potential reachability, not proof of changed behavior"}


def decide(scope, evidence, strength, *, require_strength, coverage=True):
    if scope["status"] == "REJECT" or evidence["confirmed_failure"]:
        return {"verdict": "REJECT", "reason": "confirmed scope or required behavior violation"}
    if scope["status"] != "ALLOW" or not evidence["bound_complete"] or not coverage:
        return {"verdict": "UNKNOWN", "reason": "incomplete or unbound evidence"}
    if require_strength and strength == "proof":
        return {"verdict": "UNKNOWN", "reason": "required checked semantic proof unavailable"}
    return {"verdict": "ALLOW", "reason": "registered bounded observations and structural policy satisfied"}
