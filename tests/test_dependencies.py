import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DependencyContractTest(unittest.TestCase):
    def test_arq_uses_a_redis_major_version_it_supports(self):
        for path in (ROOT / "requirements.txt", ROOT / "pyproject.toml"):
            text = path.read_text(encoding="utf-8")
            redis_major = int(re.search(r"redis==([0-9]+)", text).group(1))
            arq_major, arq_minor, arq_patch = (
                int(part)
                for part in re.search(r"arq==([0-9]+)\.([0-9]+)\.([0-9]+)", text).groups()
            )
            self.assertEqual((arq_major, arq_minor, arq_patch), (0, 26, 3))
            self.assertLess(redis_major, 6)


if __name__ == "__main__":
    unittest.main()
