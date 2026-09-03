import unittest
from omega.state import validate_transition, is_terminal

class StateTest(unittest.TestCase):
    def test_valid_lifecycle(self):
        validate_transition("PENDING", "PENDING_DISPATCH")
        validate_transition("PENDING_DISPATCH", "QUEUED")
        validate_transition("QUEUED", "RUNNING")
        validate_transition("RUNNING", "PASS")

    def test_cancel_lifecycle(self):
        validate_transition("RUNNING", "CANCEL_REQUESTED")
        validate_transition("CANCEL_REQUESTED", "CANCELLED")

    def test_invalid_terminal_transition(self):
        with self.assertRaises(ValueError):
            validate_transition("FAIL", "PASS")

    def test_terminal_states(self):
        for state in {"PASS", "PARTIAL", "FAIL", "BLOCKED", "CANCELLED"}:
            self.assertTrue(is_terminal(state))

if __name__ == "__main__":
    unittest.main()
