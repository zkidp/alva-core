"""Public, upstream-grounded task statements, selected before any pilot turn."""

TASKS = [
    {"id": "CACHE-EXPIRY-ERROR", "repo": "tkem/cachetools", "commit": "9976f1a8076631560f49c5b0dfda7e4d00ee0a4a",
     "issue": "https://github.com/tkem/cachetools/issues/440", "package": "cachetools", "prefix": "src/cachetools/",
     "editable": ["cachetools/__init__.py"],
     "statement": "Fix TTLCache insertion when computing expiration raises (for example datetime.max plus a positive timedelta). Propagate the original arithmetic exception without inserting an unusable entry or corrupting the cache. A failed overwrite must preserve the previous value; a failed new insertion must not evict an existing live entry. Keep ordinary TTL expiration, capacity and LRU behavior. Only edit cachetools/__init__.py."},
    {"id": "CACHE-EXPIRE-RESULT", "repo": "tkem/cachetools", "commit": "51ec8b9fecab300c2708d64e4407abe95e29bad1",
     "issue": "https://github.com/tkem/cachetools/issues/323", "package": "cachetools", "prefix": "src/cachetools/",
     "editable": ["cachetools/__init__.py"],
     "statement": "Make TTLCache.expire(time=None) and TLRUCache.expire(time=None) return an iterable of the (key, value) pairs actually removed by this call, so subclasses can observe expiration. An empty/repeated expiration returns an empty iterable. Honor explicit time and timer defaults, never include merely superseded TLRU heap entries, and preserve normal cache operations. This is the requested observability API, not a change to route expiry through popitem. Only edit cachetools/__init__.py."},
    {"id": "BOLTONS-EXPORTS", "repo": "mahmoud/boltons", "commit": "6cac49ce4eba506a3582e8089bcc347c6b2fa70f",
     "issue": "https://github.com/mahmoud/boltons/issues/355", "package": "boltons", "prefix": "boltons/",
     "editable": ["boltons/strutils.py"],
     "statement": "Repair boltons.strutils public wildcard imports. Its __all__ currently names missing attributes. Ensure every declared export exists and `from boltons.strutils import *` works; retain currently declared names that already exist. Do not invent replacement public functions or change existing string/integer-list conversion behavior. Only edit boltons/strutils.py."},
    {"id": "BOLTONS-NAIVE-EPOCH", "repo": "mahmoud/boltons", "commit": "6cac49ce4eba506a3582e8089bcc347c6b2fa70f",
     "issue": "https://github.com/mahmoud/boltons/issues/369", "package": "boltons", "prefix": "boltons/",
     "editable": ["boltons/timeutils.py"],
     "statement": "Remove the import-time deprecated utcfromtimestamp usage in boltons.timeutils on modern Python, without suppressing warnings. Preserve EPOCH_NAIVE as the timezone-naive UTC epoch, EPOCH_AWARE as aware UTC, and timestamp conversion for naive and aware datetime values (including before 1970). Do not remove support for naive datetimes. Only edit boltons/timeutils.py."},
    {"id": "ITER-WEIGHTED-EMPTY", "repo": "more-itertools/more-itertools", "commit": "b21ec4ee8e139ebe297e2221980a694bebb69523",
     "issue": "https://github.com/more-itertools/more-itertools/issues/1318", "package": "more_itertools", "prefix": "more_itertools/",
     "editable": ["more_itertools/more.py"],
     "statement": "Fix sample([], k, weights=[]) for positive k: with strict=False return an empty list, as on the unweighted path; with strict=True keep raising ValueError for insufficient population. Preserve k=0, negative-k rejection, generator inputs and nonempty weighted sampling without changing its algorithm. Only edit more_itertools/more.py."},
    {"id": "ITER-ADJACENT-IDENTITY", "repo": "more-itertools/more-itertools", "commit": "b21ec4ee8e139ebe297e2221980a694bebb69523",
     "issue": "https://github.com/more-itertools/more-itertools/issues/1319", "package": "more_itertools", "prefix": "more_itertools/",
     "editable": ["more_itertools/more.py"],
     "statement": "Make classify_unique's adjacent-uniqueness flag agree with unique_justseen for repeated references to the same non-reflexive key, such as one shared NaN. Identity counts as the same adjacent key; distinct NaN objects remain distinct. Cover ordinary values, key functions and unhashable keys. Preserve the ever-unique flag and laziness. Only edit more_itertools/more.py."},
]

MODEL = "gpt-5.6-sol"
BUDGET = {"fresh_codex_turns": 1, "wall_seconds": 480, "tool_item_observation_limit": 40,
          "guard_calls": 8, "observed_provider_tokens_interrupt_threshold": 120000,
          "reasoning": "low", "concurrency": 1,
          "limitation": "Notification-based interruption is not pre-request token admission; in-flight work/cleanup can exceed thresholds. No unsupported hard provider-request or dollar cap is claimed."}

COMMON = """Work only in this disposable Python project. Implement the task in the authorized source files; tests, LICENSE and metadata are protected. Normal shell, reads, search, exact edits, Git status/diff and local tests are available. Do not install dependencies, use network, delegate, inspect other runs/trajectories/reference fixes, modify the original project or commit Git. Run `python test_pilot.py regression` and `python test_pilot.py task` as useful within the budget. Test outputs are feedback, not permission to weaken tests. Finish with a concise account of changes and checks. This is one bounded exploratory run, not a competition.
"""

ARMS = {
    "A": "Use the ordinary Git diff / local tests workflow. There are no Guard tools in this condition.",
    "B": "Use the optional Python Guard workflow for this prepared candidate: after edits call guard_verify with {}, inspect the actual checks/applicability, and call guard_report with {} before handoff. Ordinary Git diff and local tests remain available. The trusted host owns the approved policy; do not change it. Never apply to the original project.",
}
