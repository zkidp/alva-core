"""Prospective shared study tool contract; no model or execution launcher."""
from copy import deepcopy

NATIVE_TOOLS = ("begin_transaction", "inspect_project", "read_function", "inspect_entity",
                "replace_function_body", "preview_semantic_diff", "check_transaction",
                "commit_transaction", "abort_transaction")
DOCS = ("language.md", "SKILL.md", "references/workflow.md", "references/diagnostics.md",
        "references/examples.md", "maintenance-profile.md")


def string(description):
    return {"type": "string", "minLength": 1, "description": description}


REV = string("Complete revision returned by study_revision; re-read on conflict.")
PATH = string("Exact public input path returned by study_revision.")
SCHEMAS = {
    "revision": ({}, ()),
    "read": ({"revision": REV, "path": PATH,
              "start": {"type": "integer", "minimum": 1},
              "count": {"type": "integer", "minimum": 1, "maximum": 200}}, ("revision", "path")),
    "search": ({"revision": REV, "text": string("Literal source search; no regular expressions.")}, ("revision", "text")),
    "diff": ({"revision": REV}, ("revision",)),
    "doc": ({"path": {"type": "string", "enum": list(DOCS)}}, ("path",)),
    "check": ({}, ()), "test": ({}, ()), "finish": ({}, ()),
    "edit": ({"revision": REV, "path": PATH, "old": string("One unique exact source span."),
              "new": {"type": "string"}}, ("revision", "path", "old", "new")),
    "write": ({"revision": REV, "path": PATH, "content": {"type": "string"}}, ("revision", "path", "content")),
}
DESCRIPTIONS = {
    "revision": "Read current source revision, public input paths and authority mode.",
    "read": "Read public source, up to 200 lines; response gives EOF/next_start. In N this is the original import source, not staged AIR.",
    "search": "Search literal text in public source files.",
    "diff": "Read source Git diff in T or authority summary in N; preview_semantic_diff reviews staged N changes.",
    "doc": "Read an approved public language/skill/profile document. Same bytes available to both conditions.",
    "check": "Check the exact candidate in isolation; diagnostics are bounded. Not behavioral proof.",
    "test": "Run the fixed independent task/regression tests in isolation; no assertions or expected values disclosed.",
    "finish": "Hand off current authority for final evaluation. Does not commit Native staging.",
    "edit": "Replace one unique exact source span at the expected revision. Text condition only.",
    "write": "Replace a complete public source file at the expected revision. Text condition only.",
}


def study_tools(arm):
    if arm not in ("T", "N"):
        raise ValueError("Unknown arm")
    actions = list(SCHEMAS) if arm == "T" else [a for a in SCHEMAS if a not in ("edit", "write")]
    return [{"name": "study_" + action, "description": DESCRIPTIONS[action],
             "inputSchema": {"type": "object", "properties": deepcopy(SCHEMAS[action][0]),
                             "required": list(SCHEMAS[action][1]), "additionalProperties": False}}
            for action in actions]


def decode_call(arm, name, arguments):
    """Closed validation before a future runtime dispatch. No nested JSON args.

    Returns an existing study action and its object arguments. Runtime must
    still enforce input paths, current authority, isolation and task policy.
    """
    tools = {t["name"]: t for t in study_tools(arm)}
    if name not in tools:
        raise ValueError("STUDY_TOOL_NOT_EXPOSED")
    if not isinstance(arguments, dict):
        raise ValueError("STUDY_ARGUMENTS_MUST_BE_OBJECT")
    schema = tools[name]["inputSchema"]
    if set(arguments) - set(schema["properties"]) or not set(schema["required"]) <= set(arguments):
        raise ValueError("STUDY_ARGUMENT_KEYS")
    for key, value in arguments.items():
        rule = schema["properties"][key]
        if rule["type"] == "integer":
            if type(value) is not int or value < rule.get("minimum", value) or value > rule.get("maximum", value):
                raise ValueError("STUDY_INTEGER_RANGE:" + key)
        elif not isinstance(value, str) or len(value) < rule.get("minLength", 0):
            raise ValueError("STUDY_STRING:" + key)
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError("STUDY_ENUM:" + key)
    return name.removeprefix("study_"), deepcopy(arguments)


COMMON_INSTRUCTIONS = """Maintain the supplied ALVA component under the public task and authorized function-body scope.
Only the target body may change; preserve other declarations, signatures, contracts, types, module metadata and manifest.
Both conditions have the same public source, language docs, complete official Skill and references, profile guide, and study checks/tests.
These instructions override conflicting workflow instructions in reference docs: T edits source; N uses only the maintenance Native profile.
Call study tools with a direct object. study_check, study_test and study_finish take exactly {}. There is no nested arguments JSON string.
In T use study_edit or study_write at the current source revision. In N use read_function and replace_function_body with its exact body_revision.
The declaration field from read_function omits the body and is read-only context; edit the separate body fragment. Source reads in N show import source.
N must publish with commit_transaction. Preview/check/finish do not publish, and uncommitted staging is not a completed candidate.
Run the shared check/test as needed; finite tests are not a proof. No task solution, hidden assertions or previous session is available.
One turn; at most 80 total model tool calls, 480 active seconds, 600000 cumulative reported tokens observation, 20 seconds interrupt grace.
Use study_finish for final handoff. No shell, arbitrary files, test changes, scope expansion or operator recovery.
"""
