"""Public black-box task and focused regression checks, run by the independent host.

Copied byte-identically to each candidate as test_pilot.py. Not a hidden oracle.
No reference patch or source-text scoring. A unittest failure is not a host bug.
"""

import importlib
import json
import math
import sys
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TASK = json.loads((Path(__file__).parent / "TASK.json").read_bytes())["id"]


class Timer:
    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value


class Regression(unittest.TestCase):
    def test_existing_behavior(self):
        if TASK.startswith("CACHE"):
            from cachetools import TTLCache, TLRUCache, LRUCache
            timer = Timer()
            for cache in (TTLCache(2, 3, timer=timer), TLRUCache(2, lambda k, v, t: t + 3, timer=timer)):
                timer.value = 0
                cache["a"], cache["b"] = 1, 2
                self.assertEqual(cache["a"], 1)
                cache["c"] = 3
                self.assertNotIn("b", cache)
                self.assertEqual(len(cache), 2)
                timer.value = 3
                self.assertNotIn("a", cache)
                self.assertEqual(len(cache), 0)
            cache = LRUCache(1)
            cache["a"], cache["b"] = 1, 2
            self.assertEqual(list(cache), ["b"])
        elif TASK.startswith("BOLTONS"):
            from boltons import strutils
            self.assertEqual(strutils.slugify("Hello World"), "hello_world")
            self.assertEqual(strutils.parse_int_list("1,3,5-7"), [1, 3, 5, 6, 7])
            self.assertEqual(strutils.format_int_list([1, 2, 3, 5]), "1-3,5")
            from boltons import timeutils
            self.assertEqual(timeutils.dt_to_timestamp(datetime(1970, 1, 1)), 0)
            self.assertEqual(timeutils.dt_to_timestamp(datetime(1970, 1, 1, tzinfo=timezone.utc)), 0)
        else:
            from more_itertools import chunked, sample, classify_unique, unique_justseen
            self.assertEqual(list(chunked(range(5), 2)), [[0, 1], [2, 3], [4]])
            self.assertEqual(list(classify_unique([1, 1, 2, 1])), [(1, True, True), (1, False, False), (2, True, True), (1, True, False)])
            self.assertEqual(list(unique_justseen([1, 1, 2])), [1, 2])
            self.assertEqual(sorted(sample([1, 2, 3], 3, weights=[1, 1, 1])), [1, 2, 3])


class TaskTests(unittest.TestCase):
    def test_requested_behavior(self):
        if TASK == "CACHE-EXPIRY-ERROR":
            from cachetools import TTLCache
            class BrokenDelta:
                fail = False
                def __radd__(self, value):
                    if self.fail:
                        raise OverflowError("public arithmetic failure")
                    return value + 3
            delta = BrokenDelta()
            cache = TTLCache(1, delta, timer=Timer())
            cache["old"] = 10
            # Use the public custom-TTL operand protocol, not private cache fields.
            delta.fail = True
            with self.assertRaises(OverflowError):
                cache["new"] = 20
            self.assertNotIn("new", cache)
            self.assertEqual(cache["old"], 10)
            with self.assertRaises(OverflowError):
                cache["old"] = 30
            self.assertEqual(cache["old"], 10)
            overflow = TTLCache(1, timedelta(days=1), timer=lambda: datetime.max)
            with self.assertRaises(OverflowError):
                overflow["bad"] = 1
            self.assertNotIn("bad", overflow)
            self.assertEqual(len(overflow), 0)
        elif TASK == "CACHE-EXPIRE-RESULT":
            from cachetools import TTLCache, TLRUCache
            timer = Timer()
            for cache in (TTLCache(5, 2, timer=timer), TLRUCache(5, lambda k, v, t: t + 2, timer=timer)):
                timer.value = 0
                self.assertEqual(list(cache.expire()), [])
                cache["a"], cache["b"] = 1, 2
                timer.value = 1
                cache["c"] = 3
                self.assertCountEqual(list(cache.expire(2)), [("a", 1), ("b", 2)])
                self.assertEqual(cache["c"], 3)
                self.assertEqual(list(cache.expire(2)), [])
                timer.value = 3
                self.assertEqual(list(cache.expire()), [("c", 3)])
            timer.value = 0
            cache = TLRUCache(5, lambda k, v, t: t + 2, timer=timer)
            cache["x"] = 1
            timer.value = 1
            cache["x"] = 2
            self.assertEqual(list(cache.expire(2)), [])
            self.assertEqual(list(cache.expire(3)), [("x", 2)])
        elif TASK == "BOLTONS-EXPORTS":
            from boltons import strutils
            namespace = {}
            exec("from boltons.strutils import *", namespace)
            self.assertTrue(all(hasattr(strutils, name) for name in strutils.__all__))
            baseline = json.loads((Path(__file__).parent / "TASK.json").read_bytes())["existing_exports"]
            self.assertTrue(set(baseline) <= set(strutils.__all__))
            self.assertTrue(all(name in namespace for name in baseline))
        elif TASK == "BOLTONS-NAIVE-EPOCH":
            from boltons import timeutils
            with warnings.catch_warnings():
                warnings.simplefilter("error", DeprecationWarning)
                importlib.reload(timeutils)
            self.assertEqual(timeutils.EPOCH_NAIVE, datetime(1970, 1, 1))
            self.assertIsNone(timeutils.EPOCH_NAIVE.tzinfo)
            self.assertEqual(timeutils.EPOCH_AWARE.utcoffset(), timedelta(0))
            for value, expected in ((datetime(1969, 12, 31, 23, 59, 59), -1),
                                    (datetime(2000, 1, 1), 946684800),
                                    (datetime(1970, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))), 0)):
                self.assertEqual(timeutils.dt_to_timestamp(value), expected)
        elif TASK == "ITER-WEIGHTED-EMPTY":
            from more_itertools import sample
            for k in (1, 2, 10):
                self.assertEqual(sample([], k, weights=[]), [])
                self.assertEqual(sample(iter([]), k, weights=iter([]), strict=False), [])
                with self.assertRaises(ValueError):
                    sample([], k, weights=[], strict=True)
            self.assertEqual(sample([], 0, weights=[]), [])
            with self.assertRaises(ValueError):
                sample([], -1, weights=[])
            self.assertEqual(sample([9], 1, weights=[1]), [9])
        elif TASK == "ITER-ADJACENT-IDENTITY":
            from more_itertools import classify_unique, unique_justseen
            nan = float("nan")
            for values, key in (([nan, nan], None), ([1, 2, 3], lambda x: nan),
                                ([[1], [1], [2]], None), ([float("nan"), float("nan")], None)):
                rows = list(classify_unique(values, key=key))
                adjacent = [value for value, flag, _ in rows if flag]
                expected = list(unique_justseen(values, key=key))
                self.assertEqual(len(adjacent), len(expected))
                self.assertTrue(all(a is b for a, b in zip(adjacent, expected)))
            rows = list(classify_unique([nan, nan]))
            self.assertEqual([(a, b) for _, a, b in rows], [(True, True), (False, False)])
            consumed = []
            def source():
                for value in (nan, nan, 5):
                    consumed.append(value)
                    yield value
            it = classify_unique(source())
            next(it)
            self.assertEqual(len(consumed), 1)
        else:
            self.fail("unknown frozen task")


if __name__ == "__main__":
    group = sys.argv.pop(1) if len(sys.argv) > 1 else "all"
    cls = {"task": TaskTests, "regression": Regression}.get(group)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(cls) if cls else unittest.TestSuite(
        [unittest.defaultTestLoader.loadTestsFromTestCase(Regression), unittest.defaultTestLoader.loadTestsFromTestCase(TaskTests)])
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if outcome.wasSuccessful() else 1)
