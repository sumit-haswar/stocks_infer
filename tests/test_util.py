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
        self.assertEqual(output,None)

    def test_get_currency_from_number_million(self):
        output = get_currency_from_number(8940000)
        self.assertEqual(output, "8.94M")

    def test_get_currency_from_number_billion(self):
        output = get_currency_from_number(58280000000)
        self.assertEqual(output, "58.28B")

    def test_get_currency_from_number_trillion(self):
        output = get_currency_from_number(1170000000000)
        self.assertEqual(output, "1.17T")

    def test_get_currency_from_number(self):
        output = get_currency_from_number(56548)
        self.assertEqual(output, "56548")


if __name__ == '__main__':
    unittest.main()