"""Public task adaptations; references are host-only qualification witnesses."""
TASKS = [
    dict(id=41, feature="scalar_arithmetic", argument="n", alva_type="(prim i64)",
         returns="(prim i64)", stub="(int 0)", py_stub="0",
         task="Two sets of n cars move in opposite directions on an infinite straight road. Every pair from opposite sets meets once; cars continue unchanged. Return the collision count. n is an integer in [0,10000].",
         vectors=[(0,0),(1,1),(2,4),(3,9),(10,100),(101,10201),(10000,100000000)],
         expr=["bin","*",["ref","n"],["ref","n"]], py="return n * n"),
    dict(id=23, feature="string_length", argument="s", alva_type="(prim string)",
         returns="(prim i64)", stub="(int 0)", py_stub="0",
         task="Return the length of the input ASCII string s. Empty input has length zero. Inputs contain only ASCII characters and have length at most 64.",
         vectors=[("",0),("abc",3),("a b",3),("\n\t",2),("a"*64,64),("1234567",7)],
         expr=["call","len",["ref","s"]], py="return len(s)"),
    dict(id=42, feature="vector_mapping", argument="xs", alva_type="(vec (prim i64))",
         returns="(vec (prim i64))", stub="(vec (prim i64))", py_stub="[]",
         task="Return a new list with each integer from xs incremented by one, preserving order and duplicates. Empty input returns empty. At most 16 integers, each in [-1000,1000].",
         vectors=[([],[]),([1,2,3],[2,3,4]),([-1,0,1],[0,1,2]),([5,5],[6,6]),([-1000,1000],[-999,1001]),(list(range(16)),list(range(1,17)))],
         expr=["if",["bin","==",["call","len",["ref","xs"]],["int",0]],["vec"],
               ["call","append",["call","solve",["call","slice",["ref","xs"],["int",0],["bin","-",["call","len",["ref","xs"]],["int",1]]]],
                ["bin","+",["call","get",["ref","xs"],["bin","-",["call","len",["ref","xs"]],["int",1]]],["int",1]]]],
         py="return [x + 1 for x in xs]"),
    dict(id=3, feature="prefix_state", argument="xs", alva_type="(vec (prim i64))",
         returns="(prim bool)", stub="(bool false)", py_stub="False",
         task="Starting with balance zero, apply the integer deposits/withdrawals xs in order. Return true if any running balance is negative, even if it later recovers; otherwise false. Empty input returns false. At most 16 integers, each in [-1000,1000].",
         vectors=[([],False),([1,2,3],False),([1,2,-4,5],True),([-1,5],True),([2,-2],False),([0,0],False),([5,-2,-3,-1,2],True),([1,-1,1],False)],
         expr=["fold","i","found","(prim bool)",["int",0],["call","len",["ref","xs"]],["bool",False],
               ["if",["ref","found"],["bool",True],
                ["bin","<",["fold","j","total","(prim i64)",["int",0],["bin","+",["ref","i"],["int",1]],["int",0],
                              ["bin","+",["ref","total"],["call","get",["ref","xs"],["ref","j"]]]],["int",0]]]],
         py="balance = 0\nfor x in xs:\n    balance += x\n    if balance < 0:\n        return True\nreturn False"),
]


def sexpr(e):
    op, *a = e
    if op == "int": return f"(int {a[0]})"
    if op == "bool": return f"(bool {str(a[0]).lower()})"
    if op == "ref": return f"(ref {a[0]})"
    if op == "vec": return "(vec (prim i64))"
    if op == "call": return f"(call {a[0]} {' '.join(map(sexpr,a[1:]))})"
    if op == "bin": return f"({a[0]} {sexpr(a[1])} {sexpr(a[2])})"
    if op == "if": return f"(if {' '.join(map(sexpr,a))})"
    if op == "fold":
        i, acc, ty, start, end, init, body = a
        return f"(fold {i} (range {sexpr(start)} {sexpr(end)}) (acc {acc} {ty} {sexpr(init)}) {sexpr(body)})"
    raise ValueError(op)


def source(t, expr=None):
    body = t["stub"] if expr is None else sexpr(expr)
    return f'(module (name "bench") (version "0.1.0") (export solve)\n(fn solve (params (param {t["argument"]} {t["alva_type"]})) (returns {t["returns"]}) (pure) (body {body})))\n'
