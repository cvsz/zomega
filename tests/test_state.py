import unittest
from omega.state import validate_transition

class StateTest(unittest.TestCase):
    def test_valid(self):
        validate_transition("PENDING", "RUNNING")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            validate_transition("FAIL", "PASS")

if __name__ == "__main__":
    unittest.main()
