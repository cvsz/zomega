import unittest
from omega.key_service import ALLOWED_SCOPES

class KeyLifecycleContractTest(unittest.TestCase):
    def test_control_plane_scopes_exist(self):
        self.assertIn("keys:read", ALLOWED_SCOPES)
        self.assertIn("keys:write", ALLOWED_SCOPES)
        self.assertIn("audit:read", ALLOWED_SCOPES)

if __name__ == "__main__":
    unittest.main()
