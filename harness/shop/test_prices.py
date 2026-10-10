import unittest
from prices import total


class TestTotal(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(total([(10, 2), (5, 1)]), 25)

    def test_ten_percent_off(self):
        self.assertEqual(total([(10, 2), (5, 1)], discount=10), 22.5)


if __name__ == "__main__":
    unittest.main()
