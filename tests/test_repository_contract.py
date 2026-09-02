import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTest(unittest.TestCase):
    def test_host_entrypoints_use_python3_and_a_real_database_initializer(self):
        verify = (ROOT / "verify.sh").read_text(encoding="utf-8")
        upgrade = (ROOT / "upgrade.sh").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("python3 -m compileall", verify)
        self.assertIn("python3 -m omega db-check", verify)
        self.assertIn("alembic upgrade head", upgrade)
        self.assertNotIn("omega init", upgrade)
        self.assertIn("PYTHON ?= python3", makefile)


if __name__ == "__main__":
    unittest.main()
