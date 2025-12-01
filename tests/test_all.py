import unittest

from companion.__main__ import main
from companion.extension import sum_as_string


class TestClass(unittest.TestCase):
    def test_sum(self) -> None:
        self.assertEqual(sum_as_string(1, 2), "3")

    def test_main(self) -> None:
        self.assertEqual(main(), 0)
