import unittest
from util import *

class UtilTests(unittest.TestCase):
    """"""

    def setUp(self):
        """fixture that runs code before the test_methods execute"""
        pass

    def tearDown(self):
        """fixture that runs the code after the test_methods complete execution"""
        pass

    def test_parse_float_return_float_for_decimal(self):
        val = parse_float("12.768%")
        self.assertEqual(val, 12.768)


    def test_parse_float_return_float_for_money(self):
        val = parse_float("789,098,900")
        self.assertEqual(val, 789098900)


    def test_parse_float_returns_default(self):
        output = parse_float("abcdef")
        self.assertEqual(output,0)

    def test_parse_float_returns_default_for_empty_string(self):
        output = parse_float("")
        self.assertEqual(output,0)


if __name__ == '__main__':
    unittest.main()