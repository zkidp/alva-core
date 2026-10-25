import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cart import total


class CartTests(unittest.TestCase):
    def test_existing_totals(self):
        self.assertEqual(total([]), 0)
        self.assertEqual(total([2, 3, 9007199254740993]), 9007199254740998)

    def test_reject_negative(self):
        with self.assertRaises(ValueError):
            total([1, -2])

    def test_reject_non_integer(self):
        for value in (True, 1.5, "2", None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                total([value])
