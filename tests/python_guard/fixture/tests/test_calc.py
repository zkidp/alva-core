import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calc import total


class TotalTests(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total([2, 3]), 5)

    def test_empty(self):
        self.assertEqual(total([]), 0)
